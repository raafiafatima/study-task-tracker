"""Study Task Tracker - Flask API.

All state lives in PostgreSQL, so any number of copies of this container can
serve the same data. Database settings come from environment variables only.
Nothing in this file logs or returns credentials, hostnames or driver messages.
"""
import logging
import os

import psycopg
from flask import Flask, jsonify, request
from psycopg.rows import dict_row

MAX_TITLE_LENGTH = 120

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024  # a task title never needs more
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tasks-api")


def connect():
    """Open a short-lived connection using DB_* environment variables."""
    kwargs = {
        "host": os.environ["DB_HOST"],
        "port": int(os.environ.get("DB_PORT", "5432")),
        "dbname": os.environ["DB_NAME"],
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
        "sslmode": os.environ.get("DB_SSLMODE", "prefer"),
        "connect_timeout": int(os.environ.get("DB_CONNECT_TIMEOUT", "5")),
        "application_name": "study-task-tracker-api",
        "row_factory": dict_row,
    }
    root_cert = os.environ.get("DB_SSLROOTCERT")
    if root_cert:
        kwargs["sslrootcert"] = root_cert
    return psycopg.connect(**kwargs)


def task_json(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "created_at": row["created_at"].isoformat(),
    }


def error(status, message):
    return jsonify({"error": message}), status


def db_failure(exc):
    # Log only the exception class: driver messages can contain host details.
    log.error("Database operation failed: %s", type(exc).__name__)
    return error(503, "The database is unavailable. Please try again shortly.")


@app.after_request
def no_store(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
def health():
    try:
        with connect() as conn:
            conn.execute("SELECT 1 FROM tasks LIMIT 1")
    except (psycopg.Error, KeyError, ValueError) as exc:
        log.error("Health check failed: %s", type(exc).__name__)
        return jsonify({"status": "unavailable"}), 503
    return jsonify({"status": "ok"}), 200


@app.get("/api/tasks")
def list_tasks():
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT id, title, created_at FROM tasks "
                "ORDER BY created_at DESC, id DESC"
            ).fetchall()
    except (psycopg.Error, KeyError, ValueError) as exc:
        return db_failure(exc)
    return jsonify([task_json(r) for r in rows]), 200


@app.post("/api/tasks")
def create_task():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error(400, "Request body must be a JSON object with a title.")
    title = payload.get("title")
    if not isinstance(title, str):
        return error(400, "Title is required and must be text.")
    title = title.strip()
    if not title:
        return error(400, "Title cannot be empty.")
    if len(title) > MAX_TITLE_LENGTH:
        return error(400, f"Title must be {MAX_TITLE_LENGTH} characters or fewer.")
    try:
        with connect() as conn:
            row = conn.execute(
                "INSERT INTO tasks (title) VALUES (%s) "
                "RETURNING id, title, created_at",
                (title,),
            ).fetchone()
    except (psycopg.Error, KeyError, ValueError) as exc:
        return db_failure(exc)
    return jsonify(task_json(row)), 201


@app.errorhandler(404)
def not_found(_):
    return error(404, "Not found.")


@app.errorhandler(405)
def method_not_allowed(_):
    return error(405, "Method not allowed.")


@app.errorhandler(413)
def too_large(_):
    return error(400, "Request body is too large.")


@app.errorhandler(Exception)
def unexpected(exc):
    log.error("Unhandled error: %s", type(exc).__name__)
    return error(500, "Something went wrong on the server.")
