"""WSGI entrypoint for deployment platforms."""

from app import create_app


app = create_app()
