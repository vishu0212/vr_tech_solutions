"""Career and job application routes for VR Tech Solutions."""

import os
import uuid
from datetime import date
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename

from app import db
from app.models import Job, JobApplication


careers_bp = Blueprint("careers", __name__)

ALLOWED_RESUME_EXTENSIONS = {"pdf", "doc", "docx"}
MAX_RESUME_SIZE = 5 * 1024 * 1024  # 5 MB


def allowed_resume(filename):
    """Check whether a resume uses an allowed file extension."""
    if not filename or "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_RESUME_EXTENSIONS


def get_resume_upload_folder():
    """Create and return the private resume upload directory."""
    upload_folder = current_app.config.get(
        "RESUME_UPLOAD_FOLDER",
        os.path.join(current_app.instance_path, "resumes"),
    )

    Path(upload_folder).mkdir(parents=True, exist_ok=True)
    return upload_folder


def get_form_value(*names):
    """Support both old and new application-form field names."""
    for name in names:
        value = request.form.get(name)
        if value is not None:
            return value.strip()
    return ""


def render_application(job, status=200):
    """Render the application template with the selected job."""
    return render_template("main/apply.html", job=job), status


def application_error(job, message, status=400):
    """Show a validation message and redisplay the form."""
    flash(message, "error")
    return render_application(job, status)


@careers_bp.route("/careers")
def careers():
    """Display active job vacancies with optional searching."""
    query = request.args.get("q", "").strip()

    if len(query) > 100:
        flash("Your job search must be 100 characters or fewer.", "error")
        query = query[:100]

    jobs_query = Job.query.filter(
        Job.is_active.is_(True),
        or_(
            Job.closing_date.is_(None),
            Job.closing_date >= date.today(),
        ),
    )

    if query:
        search_term = f"%{query}%"

        jobs_query = jobs_query.filter(
            (Job.title.ilike(search_term))
            | (Job.department.ilike(search_term))
            | (Job.location.ilike(search_term))
        )

    jobs = jobs_query.order_by(Job.id.desc()).all()

    return render_template(
        "main/careers.html",
        jobs=jobs,
        query=query,
    )


@careers_bp.route("/careers/<slug>")
def job_detail(slug):
    """Redirect a vacancy URL to its application form."""
    job = Job.query.filter_by(
        slug=slug,
        is_active=True,
    ).first_or_404()

    # The application form must post to the /apply endpoint.
    return redirect(url_for("careers.apply", slug=job.slug))


@careers_bp.route(
    "/careers/<slug>/apply",
    methods=["GET", "POST"],
)
def apply(slug):
    """Display the form and process job application submissions."""
    job = Job.query.filter_by(
        slug=slug,
        is_active=True,
    ).first_or_404()

    # Do not accept applications after the closing date.
    if job.closing_date and job.closing_date < date.today():
        flash(
            "The application deadline for this job has passed.",
            "error",
        )
        return redirect(url_for("careers.careers"))

    if request.method == "GET":
        return render_application(job)

    # Accept existing field names and the new apply.html field names.
    full_name = get_form_value("full_name", "name")
    email = get_form_value("email").lower()
    phone = get_form_value("phone")
    current_location = get_form_value(
        "current_location",
        "location",
    )
    experience = get_form_value("experience")
    skills = get_form_value("skills")
    portfolio_url = get_form_value("portfolio_url")
    cover_letter = get_form_value("cover_letter")
    consent = get_form_value("consent")

    resume = request.files.get("resume")

    # Required fields.
    # Phone remains required to preserve the original application logic.
    if not full_name or not email or not phone:
        return application_error(
            job,
            "Please provide your full name, email address, and phone number.",
        )

    if len(full_name) > 150:
        return application_error(
            job,
            "Name must be 150 characters or fewer.",
        )

    # Basic email validation.
    if (
        len(email) > 150
        or "@" not in email
        or email.startswith("@")
        or email.endswith("@")
        or "." not in email.rsplit("@", 1)[-1]
    ):
        return application_error(
            job,
            "Please enter a valid email address.",
        )

    if len(phone) > 30:
        return application_error(
            job,
            "Phone must be 30 characters or fewer.",
        )

    if len(current_location) > 150:
        return application_error(
            job,
            "Location must be 150 characters or fewer.",
        )

    if len(experience) > 100:
        return application_error(
            job,
            "Experience must be 100 characters or fewer.",
        )

    if len(skills) > 500:
        return application_error(
            job,
            "Skills must be 500 characters or fewer.",
        )

    if len(portfolio_url) > 500:
        return application_error(
            job,
            "Portfolio URL must be 500 characters or fewer.",
        )

    if portfolio_url and not portfolio_url.lower().startswith(
        ("https://", "http://")
    ):
        return application_error(
            job,
            "Portfolio URL must begin with http:// or https://.",
        )

    if len(cover_letter) > 10000:
        return application_error(
            job,
            "Cover letter must be 10,000 characters or fewer.",
        )

    # Require the consent checkbox in the current apply.html template.
    if consent != "yes":
        return application_error(
            job,
            "Please confirm that your information may be used "
            "to respond to your application.",
        )

    # Resume is mandatory.
    if not resume or not resume.filename:
        return application_error(
            job,
            "Please upload your resume.",
        )

    # Sanitize the name and validate the extension.
    original_filename = secure_filename(resume.filename)

    if not original_filename or not allowed_resume(original_filename):
        return application_error(
            job,
            "Upload your resume as a PDF, DOC, or DOCX file.",
        )

    # Enforce size limits before saving the file.
    try:
        resume.stream.seek(0, os.SEEK_END)
        resume_size = resume.stream.tell()
        resume.stream.seek(0)
    except (OSError, AttributeError):
        return application_error(
            job,
            "We could not read the uploaded resume. Please try again.",
        )

    if resume_size == 0:
        return application_error(
            job,
            "The uploaded resume is empty.",
        )

    if resume_size > MAX_RESUME_SIZE:
        return application_error(
            job,
            "Resume size must not exceed 5 MB.",
        )

    extension = original_filename.rsplit(".", 1)[1].lower()
    stored_filename = f"{uuid.uuid4().hex}.{extension}"

    try:
        upload_folder = get_resume_upload_folder()
        resume_path = os.path.join(
            upload_folder,
            stored_filename,
        )
    except OSError:
        current_app.logger.exception(
            "Could not create the resume upload directory."
        )
        return application_error(
            job,
            "Resume uploads are temporarily unavailable. Please try again.",
            500,
        )

    # JobApplication's existing schema has no dedicated skills or portfolio
    # columns. Preserve those form values in the cover_letter field.
    supplemental_details = []

    if skills:
        supplemental_details.append(f"Skills: {skills}")

    if portfolio_url:
        supplemental_details.append(
            f"Portfolio / LinkedIn: {portfolio_url}"
        )

    stored_cover_letter = cover_letter

    if supplemental_details:
        extra_details = "\n\n".join(supplemental_details)

        if stored_cover_letter:
            stored_cover_letter = (
                f"{stored_cover_letter}\n\n{extra_details}"
            )
        else:
            stored_cover_letter = extra_details

    if len(stored_cover_letter) > 10000:
        return application_error(
            job,
            "Your introduction, skills, and portfolio details are too long "
            "when combined.",
        )

    try:
        # Save with a random filename in the private upload folder.
        resume.save(resume_path)

        application = JobApplication(
            # Always associate the submission with the job from the URL.
            job_id=job.id,
            full_name=full_name,
            email=email,
            phone=phone,
            current_location=current_location or None,
            experience=experience or None,
            cover_letter=stored_cover_letter or None,
            resume_filename=stored_filename,
            status="new",
        )

        db.session.add(application)
        db.session.commit()

        flash(
            "Your application has been submitted successfully!",
            "success",
        )

        return redirect(url_for("careers.careers"))

    except (SQLAlchemyError, OSError):
        db.session.rollback()

        # Remove the uploaded resume if the database operation failed.
        try:
            if os.path.exists(resume_path):
                os.remove(resume_path)
        except OSError:
            current_app.logger.exception(
                "Could not remove an incomplete resume upload."
            )

        current_app.logger.exception(
            "Failed to process a job application."
        )

        flash(
            "We could not submit your application. Please try again later.",
            "error",
        )
        return render_application(job, 500)