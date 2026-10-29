import os
import uuid
from datetime import date
from pathlib import Path

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
    abort,
    make_response,
    send_from_directory,
)
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from app import db
from app.models import (
    Admin,
    Service,
    Project,
    ContactEnquiry,
    Job,
    JobApplication,
    SiteSetting,
)

admin_bp = Blueprint("admin", __name__)

ALLOWED_RESUME_EXTENSIONS = {"pdf", "doc", "docx"}


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def save_changes():
    """Commit database changes and handle database errors."""
    try:
        db.session.commit()
        return True
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Database operation failed.")
        flash("A database error occurred. Please try again.", "error")
        return False


def get_form_value(name, default=""):
    """Return a stripped form value."""
    return request.form.get(name, default).strip()


def parse_integer(value, default=0):
    """Convert a form value to an integer."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_boolean(value):
    """Convert an HTML checkbox value to a boolean."""
    return value in {"1", "true", "True", "yes", "on"}


def parse_date(value):
    """Convert an HTML date input into a Python date."""
    if not value:
        return None

    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def generate_slug(title):
    """Generate a basic URL slug from a title."""
    slug = "-".join(title.lower().split())

    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-")
    slug = "".join(char for char in slug if char in allowed)

    return slug.strip("-")


def unique_slug(model, title, record_id=None):
    """Generate a unique slug for a model."""
    base_slug = generate_slug(title) or "item"
    slug = base_slug
    counter = 2

    while True:
        query = model.query.filter_by(slug=slug)

        if record_id is not None:
            query = query.filter(model.id != record_id)

        if query.first() is None:
            return slug

        slug = f"{base_slug}-{counter}"
        counter += 1


def save_uploaded_image(field_name="image"):
    """
    Save an optional image upload.

    Returns the saved filename, None if no file was uploaded,
    or False if validation fails.
    """
    uploaded_file = request.files.get(field_name)

    if not uploaded_file or not uploaded_file.filename:
        return None

    filename = secure_filename(uploaded_file.filename)

    if not filename or "." not in filename:
        flash("Please select a valid image file.", "error")
        return False

    extension = filename.rsplit(".", 1)[1].lower()

    if extension not in {"jpg", "jpeg", "png", "webp"}:
        flash("Images must be JPG, JPEG, PNG, or WEBP files.", "error")
        return False

    uploaded_file.stream.seek(0, os.SEEK_END)
    file_size = uploaded_file.stream.tell()
    uploaded_file.stream.seek(0)

    if file_size == 0 or file_size > 5 * 1024 * 1024:
        flash("Image must be between 1 byte and 5 MB.", "error")
        return False

    upload_folder = os.path.join(
        current_app.static_folder,
        "uploads",
        "images",
    )

    Path(upload_folder).mkdir(parents=True, exist_ok=True)

    stored_filename = f"{uuid.uuid4().hex}.{extension}"
    uploaded_file.save(os.path.join(upload_folder, stored_filename))

    return stored_filename


## =========================================================
# ADMIN AUTHENTICATION
# =========================================================

from flask import flash, render_template, redirect, url_for, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    """Authenticate an administrator using username or email."""

    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        username_or_email = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get("password", "")

        if not username_or_email or not password:
            flash("Please enter your username/email and password.", "error")
            return render_template("admin/login.html")

        # Find admin using either username or email.
        admin = Admin.query.filter(
            or_(
                Admin.username == username_or_email,
                Admin.email == username_or_email.lower(),
            )
        ).first()

        # Verify the admin account and password.
        if (
            admin
            and admin.is_active
            and check_password_hash(admin.password_hash, password)
        ):
            login_user(admin)

            next_page = request.args.get("next", "")

            # Prevent external redirects.
            if (
                next_page.startswith("/")
                and not next_page.startswith("//")
                and "\\" not in next_page
            ):
                return redirect(next_page)

            flash("Login successful!", "success")
            return redirect(url_for("admin.dashboard"))

        flash("Invalid username/email or password.", "error")

    return render_template("admin/login.html")


@admin_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """Log out the administrator."""

    logout_user()
    flash("You have been logged out.", "success")

    return redirect(url_for("admin.login"))
# =========================================================
# ADMIN DASHBOARD
# =========================================================

@admin_bp.route("/")
@admin_bp.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    """Display website statistics."""

    if request.method == "POST":
        funding_secured = get_form_value("funding_secured")

        if not funding_secured:
            flash("Enter a funding amount or value.", "error")
            return redirect(url_for("admin.dashboard"))

        if len(funding_secured) > 100:
            flash("Funding value must be 100 characters or fewer.", "error")
            return redirect(url_for("admin.dashboard"))

        setting = db.session.get(SiteSetting, "funding_secured")

        if setting is None:
            setting = SiteSetting(key="funding_secured", value=funding_secured)
            db.session.add(setting)
        else:
            setting.value = funding_secured

        if save_changes():
            flash("Homepage funding metric updated.", "success")

        return redirect(url_for("admin.dashboard"))

    funding_setting = db.session.get(SiteSetting, "funding_secured")
    funding_secured = funding_setting.value if funding_setting else "$90m"

    stats = {
        "services": Service.query.count(),
        "active_services": Service.query.filter_by(is_active=True).count(),
        "projects": Project.query.count(),
        "active_projects": Project.query.filter_by(is_active=True).count(),
        "enquiries": ContactEnquiry.query.count(),
        "new_enquiries": ContactEnquiry.query.filter_by(
            status="new"
        ).count(),
        "jobs": Job.query.count(),
        "active_jobs": Job.query.filter_by(is_active=True).count(),
        "applications": JobApplication.query.count(),
        "new_applications": JobApplication.query.filter_by(
            status="new"
        ).count(),
    }

    recent_enquiries = (
        ContactEnquiry.query
        .order_by(ContactEnquiry.created_at.desc())
        .limit(5)
        .all()
    )

    recent_applications = (
        JobApplication.query
        .order_by(JobApplication.created_at.desc())
        .limit(5)
        .all()
    )

    response = make_response(
        render_template(
            "admin/dashboard.html",
            stats=stats,
            service_count=stats["services"],
            project_count=stats["projects"],
            enquiry_count=stats["enquiries"],
            new_enquiry_count=stats["new_enquiries"],
            job_count=stats["jobs"],
            application_count=stats["applications"],
            funding_secured=funding_secured,
            recent_enquiries=recent_enquiries,
            recent_applications=recent_applications,
        )
    )
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    return response


# =========================================================
# SERVICE MANAGEMENT
# =========================================================

@admin_bp.route("/services", methods=["GET", "POST"])
@login_required
def services():
    """List services and create a new service."""

    if request.method == "POST":
        title = get_form_value("title")
        short_description = get_form_value("short_description")
        description = get_form_value("description")
        icon = get_form_value("icon")
        image_url = get_form_value("image_url")

        if not title:
            flash("Service title is required.", "error")
            return redirect(url_for("admin.services"))

        if len(title) > 150:
            flash("Service title must be 150 characters or fewer.", "error")
            return redirect(url_for("admin.services"))

        uploaded_image = save_uploaded_image()

        if uploaded_image is False:
            return redirect(url_for("admin.services"))

        if uploaded_image:
            image_url = f"/static/uploads/images/{uploaded_image}"

        service = Service(
            title=title,
            slug=unique_slug(Service, title),
            short_description=short_description,
            description=description,
            icon=icon,
            image_url=image_url,
            is_active=parse_boolean(request.form.get("is_active")),
            display_order=parse_integer(
                request.form.get("display_order")
            ),
        )

        db.session.add(service)

        if save_changes():
            flash("Service created successfully.", "success")

        return redirect(url_for("admin.services"))

    all_services = Service.query.order_by(
        Service.display_order.asc(),
        Service.id.desc(),
    ).all()

    return render_template(
        "admin/services.html",
        services=all_services,
    )


@admin_bp.route("/services/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_service(item_id):
    """Edit an existing service."""

    service = db.session.get(Service, item_id)

    if service is None:
        abort(404)

    if request.method == "POST":
        title = get_form_value("title")

        if not title:
            flash("Service title is required.", "error")
            return render_template(
                "admin/service_edit.html",
                service=service,
            )

        if len(title) > 150:
            flash("Service title must be 150 characters or fewer.", "error")
            return render_template(
                "admin/service_edit.html",
                service=service,
            )

        uploaded_image = save_uploaded_image()

        if uploaded_image is False:
            return render_template(
                "admin/service_edit.html",
                service=service,
            )

        service.title = title
        service.slug = unique_slug(Service, title, service.id)
        service.short_description = get_form_value("short_description")
        service.description = get_form_value("description")
        service.icon = get_form_value("icon")
        service.is_active = parse_boolean(request.form.get("is_active"))
        service.display_order = parse_integer(
            request.form.get("display_order")
        )

        if uploaded_image:
            service.image_url = f"/static/uploads/images/{uploaded_image}"
        else:
            service.image_url = get_form_value("image_url")

        if save_changes():
            flash("Service updated successfully.", "success")
            return redirect(url_for("admin.services"))

    return render_template(
        "admin/service_edit.html",
        service=service,
    )


@admin_bp.route("/services/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_service(item_id):
    """Delete a service."""

    service = db.session.get(Service, item_id)

    if service is None:
        abort(404)

    db.session.delete(service)

    if save_changes():
        flash("Service deleted successfully.", "success")

    return redirect(url_for("admin.services"))


# =========================================================
# PROJECT MANAGEMENT
# =========================================================

@admin_bp.route("/projects", methods=["GET", "POST"])
@login_required
def projects():
    """List projects and create new projects."""

    if request.method == "POST":
        title = get_form_value("title")

        if not title:
            flash("Project title is required.", "error")
            return redirect(url_for("admin.projects"))

        if len(title) > 150:
            flash("Project title must be 150 characters or fewer.", "error")
            return redirect(url_for("admin.projects"))

        uploaded_image = save_uploaded_image()

        if uploaded_image is False:
            return redirect(url_for("admin.projects"))

        image_url = get_form_value("image_url")

        if uploaded_image:
            image_url = f"/static/uploads/images/{uploaded_image}"

        project = Project(
            title=title,
            slug=unique_slug(Project, title),
            category=get_form_value("category"),
            short_description=get_form_value("short_description"),
            description=get_form_value("description"),
            image_url=image_url,
            project_url=get_form_value("project_url"),
            technologies=get_form_value("technologies"),
            is_featured=parse_boolean(request.form.get("is_featured")),
            is_active=parse_boolean(request.form.get("is_active")),
            display_order=parse_integer(
                request.form.get("display_order")
            ),
        )

        db.session.add(project)

        if save_changes():
            flash("Project created successfully.", "success")

        return redirect(url_for("admin.projects"))

    all_projects = Project.query.order_by(
        Project.display_order.asc(),
        Project.id.desc(),
    ).all()

    return render_template(
        "admin/projects.html",
        projects=all_projects,
    )


@admin_bp.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
@login_required
def project_edit(project_id):
    """Edit a project."""

    project = db.session.get(Project, project_id)

    if project is None:
        abort(404)

    if request.method == "POST":
        title = get_form_value("title")

        if not title:
            flash("Project title is required.", "error")
            return render_template(
                "admin/projects.html",
                projects=Project.query.order_by(Project.id.desc()).all(),
            )

        if len(title) > 150:
            flash("Project title must be 150 characters or fewer.", "error")
            return redirect(url_for("admin.projects"))

        uploaded_image = save_uploaded_image()

        if uploaded_image is False:
            return redirect(url_for("admin.projects"))

        project.title = title
        project.slug = unique_slug(Project, title, project.id)
        project.category = get_form_value("category")
        project.short_description = get_form_value("short_description")
        project.description = get_form_value("description")
        project.project_url = get_form_value("project_url")
        project.technologies = get_form_value("technologies")
        project.is_featured = parse_boolean(
            request.form.get("is_featured")
        )
        project.is_active = parse_boolean(
            request.form.get("is_active")
        )
        project.display_order = parse_integer(
            request.form.get("display_order")
        )

        if uploaded_image:
            project.image_url = f"/static/uploads/images/{uploaded_image}"
        else:
            project.image_url = get_form_value("image_url")

        if save_changes():
            flash("Project updated successfully.", "success")

        return redirect(url_for("admin.projects"))

    # Reuse the project list template for the edit form.
    all_projects = Project.query.order_by(Project.id.desc()).all()

    return render_template(
        "admin/projects.html",
        projects=all_projects,
        edit_project=project,
    )


@admin_bp.route("/projects/<int:item_id>/toggle", methods=["POST"])
@login_required
def toggle_project(item_id):
    """Activate or hide a project."""

    project = db.session.get(Project, item_id)

    if project is None:
        abort(404)

    project.is_active = not project.is_active

    if save_changes():
        flash(
            "Project activated." if project.is_active else "Project hidden.",
            "success",
        )

    return redirect(url_for("admin.projects"))


@admin_bp.route("/projects/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_project(item_id):
    """Delete a project."""

    project = db.session.get(Project, item_id)

    if project is None:
        abort(404)

    db.session.delete(project)

    if save_changes():
        flash("Project deleted successfully.", "success")

    return redirect(url_for("admin.projects"))


# =========================================================
# CONTACT ENQUIRIES
# =========================================================

@admin_bp.route("/enquiries", methods=["GET"])
@login_required
def enquiries():
    """List contact enquiries with optional search and status filtering."""

    search = request.args.get("q", "").strip()[:100]
    status = request.args.get("status", "").strip()

    query = ContactEnquiry.query

    if search:
        term = f"%{search}%"

        query = query.filter(
            or_(
                ContactEnquiry.name.ilike(term),
                ContactEnquiry.email.ilike(term),
                ContactEnquiry.subject.ilike(term),
                ContactEnquiry.company.ilike(term),
            )
        )

    if status in {"new", "read", "replied", "closed"}:
        query = query.filter_by(status=status)

    all_enquiries = query.order_by(
        ContactEnquiry.created_at.desc()
    ).all()

    return render_template(
        "admin/enquiries.html",
        enquiries=all_enquiries,
        search=search,
        selected_status=status,
    )


@admin_bp.route(
    "/enquiries/<int:item_id>/status",
    methods=["POST"],
)
@login_required
def enquiry_status(item_id):
    """Update an enquiry status to match the admin list actions."""

    enquiry = db.session.get(ContactEnquiry, item_id)

    if enquiry is None:
        abort(404)

    status = get_form_value("status")
    status_aliases = {
        "new": "new",
        "read": "read",
        "replied": "replied",
        "closed": "closed",
        "in_progress": "read",
        "contacted": "replied",
    }

    if status not in status_aliases:
        flash("Invalid enquiry status.", "error")
        return redirect(url_for("admin.enquiries"))

    enquiry.status = status_aliases[status]
    enquiry.admin_notes = get_form_value("admin_notes")

    if save_changes():
        flash("Enquiry updated successfully.", "success")

    return redirect(url_for("admin.enquiries"))


@admin_bp.route(
    "/enquiries/<int:enquiry_id>/update",
    methods=["POST"],
)
@login_required
def enquiry_update(enquiry_id):
    """Update an enquiry's status and internal notes."""

    enquiry = db.session.get(ContactEnquiry, enquiry_id)

    if enquiry is None:
        abort(404)

    status = get_form_value("status")
    allowed_statuses = {"new", "read", "replied", "closed"}

    if status not in allowed_statuses:
        flash("Invalid enquiry status.", "error")
        return redirect(url_for("admin.enquiries"))

    enquiry.status = status
    enquiry.admin_notes = get_form_value("admin_notes")

    if save_changes():
        flash("Enquiry updated successfully.", "success")

    return redirect(url_for("admin.enquiries"))


@admin_bp.route(
    "/enquiries/<int:enquiry_id>/delete",
    methods=["POST"],
)
@login_required
def enquiry_delete(enquiry_id):
    """Delete a contact enquiry."""

    enquiry = db.session.get(ContactEnquiry, enquiry_id)

    if enquiry is None:
        abort(404)

    db.session.delete(enquiry)

    if save_changes():
        flash("Enquiry deleted successfully.", "success")

    return redirect(url_for("admin.enquiries"))


# =========================================================
# JOB VACANCY MANAGEMENT
# =========================================================

@admin_bp.route("/jobs", methods=["GET", "POST"])
@login_required
def jobs():
    """List job vacancies and create a new vacancy."""

    if request.method == "POST":
        title = get_form_value("title")

        if not title:
            flash("Job title is required.", "error")
            return redirect(url_for("admin.jobs"))

        if len(title) > 150:
            flash("Job title must be 150 characters or fewer.", "error")
            return redirect(url_for("admin.jobs"))

        job = Job(
            title=title,
            slug=unique_slug(Job, title),
            department=get_form_value("department"),
            location=get_form_value("location"),
            employment_type=get_form_value("employment_type"),
            experience=get_form_value("experience"),
            salary_range=get_form_value("salary_range"),
            short_description=get_form_value("short_description"),
            description=get_form_value("description"),
            requirements=get_form_value("requirements"),
            is_active=parse_boolean(request.form.get("is_active")),
            closing_date=parse_date(
                request.form.get("closing_date")
            ),
        )

        db.session.add(job)

        if save_changes():
            flash("Job vacancy created successfully.", "success")

        return redirect(url_for("admin.jobs"))

    all_jobs = Job.query.order_by(Job.id.desc()).all()

    return render_template(
        "admin/jobs.html",
        jobs=all_jobs,
    )


@admin_bp.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
@login_required
def job_edit(job_id):
    """Edit a job vacancy."""

    job = db.session.get(Job, job_id)

    if job is None:
        abort(404)

    if request.method == "POST":
        title = get_form_value("title")

        if not title:
            flash("Job title is required.", "error")
            return redirect(url_for("admin.jobs"))

        if len(title) > 150:
            flash("Job title must be 150 characters or fewer.", "error")
            return redirect(url_for("admin.jobs"))

        closing_date_value = request.form.get("closing_date", "").strip()
        closing_date = parse_date(closing_date_value)

        if closing_date_value and closing_date is None:
            flash("Please enter a valid closing date.", "error")
            return redirect(url_for("admin.jobs"))

        job.title = title
        job.slug = unique_slug(Job, title, job.id)
        job.department = get_form_value("department")
        job.location = get_form_value("location")
        job.employment_type = get_form_value("employment_type")
        job.experience = get_form_value("experience")
        job.salary_range = get_form_value("salary_range")
        job.short_description = get_form_value("short_description")
        job.description = get_form_value("description")
        job.requirements = get_form_value("requirements")
        job.is_active = parse_boolean(request.form.get("is_active"))
        job.closing_date = closing_date

        if save_changes():
            flash("Job vacancy updated successfully.", "success")

        return redirect(url_for("admin.jobs"))

    return render_template(
        "admin/jobs.html",
        jobs=Job.query.order_by(Job.id.desc()).all(),
        edit_job=job,
    )


@admin_bp.route("/jobs/<int:item_id>/toggle", methods=["POST"])
@login_required
def toggle_job(item_id):
    """Toggle a job listing between active and closed."""

    job = db.session.get(Job, item_id)

    if job is None:
        abort(404)

    job.is_active = not job.is_active

    if save_changes():
        flash("Job listing reopened." if job.is_active else "Job listing closed.", "success")

    return redirect(url_for("admin.jobs"))


@admin_bp.route("/jobs/<int:job_id>/delete", methods=["POST"])
@login_required
def job_delete(job_id):
    """Delete a job vacancy."""

    job = db.session.get(Job, job_id)

    if job is None:
        abort(404)

    # Preserve submitted applications and their records.
    if job.applications:
        flash(
            "This job has applications. Deactivate it instead of deleting it.",
            "error",
        )
        return redirect(url_for("admin.jobs"))

    db.session.delete(job)

    if save_changes():
        flash("Job vacancy deleted successfully.", "success")

    return redirect(url_for("admin.jobs"))


# =========================================================
# JOB APPLICATION MANAGEMENT
# =========================================================

@admin_bp.route("/applications", methods=["GET"])
@login_required
def applications():
    """List job applications."""

    status = request.args.get("status", "").strip()
    search = request.args.get("q", "").strip()[:100]

    query = JobApplication.query

    if status in {"new", "reviewing", "shortlisted", "rejected", "hired"}:
        query = query.filter_by(status=status)

    if search:
        term = f"%{search}%"

        query = query.filter(
            or_(
                JobApplication.full_name.ilike(term),
                JobApplication.email.ilike(term),
                JobApplication.phone.ilike(term),
            )
        )

    all_applications = query.order_by(
        JobApplication.created_at.desc()
    ).all()

    return render_template(
        "admin/applications.html",
        applications=all_applications,
        selected_status=status,
        search=search,
    )


@admin_bp.route(
    "/applications/<int:application_id>/update",
    methods=["POST"],
)
@login_required
def application_update(application_id):
    """Update an application's status and admin notes."""

    application = db.session.get(
        JobApplication,
        application_id,
    )

    if application is None:
        abort(404)

    status = get_form_value("status")

    allowed_statuses = {
        "new",
        "reviewing",
        "shortlisted",
        "rejected",
        "hired",
    }

    if status not in allowed_statuses:
        flash("Invalid application status.", "error")
        return redirect(url_for("admin.applications"))

    application.status = status
    application.admin_notes = get_form_value("admin_notes")

    if save_changes():
        flash("Application updated successfully.", "success")

    return redirect(url_for("admin.applications"))


@admin_bp.route(
    "/applications/<int:application_id>/resume",
    methods=["GET"],
)
@login_required
def application_resume(application_id):
    """Allow an authenticated admin to download a submitted resume."""

    application = db.session.get(
        JobApplication,
        application_id,
    )

    if application is None:
        abort(404)

    filename = application.resume_filename

    if (
        not filename
        or secure_filename(filename) != filename
        or "." not in filename
        or filename.rsplit(".", 1)[1].lower()
        not in ALLOWED_RESUME_EXTENSIONS
    ):
        abort(404)

    upload_folder = current_app.config.get(
        "RESUME_UPLOAD_FOLDER",
        os.path.join(current_app.instance_path, "resumes"),
    )

    if not os.path.isfile(os.path.join(upload_folder, filename)):
        abort(404)

    is_pdf = filename.rsplit(".", 1)[1].lower() == "pdf"
    response = send_from_directory(
        upload_folder,
        filename,
        as_attachment=not is_pdf,
        download_name=filename,
    )
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response