"""
Backend API — FiftyFive Technologies DevOps Intern Assessment
Flask REST API with MySQL health check
"""

import os
import time
import logging
import mysql.connector
from mysql.connector import Error as MySQLError
from flask import Flask, jsonify

# ── Logging (stdout only) ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ── DB config from environment ───────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.environ["DB_HOST"],
    "port":     int(os.environ.get("DB_PORT", 3306)),
    "user":     os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
    "database": os.environ["DB_NAME"],
    "connect_timeout": 5,
}


def get_db_connection():
    """Return a fresh MySQL connection or raise."""
    return mysql.connector.connect(**DB_CONFIG)


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    logger.info("GET / called")
    return jsonify({"status": "ok", "message": "Backend is running"}), 200


@app.route("/health", methods=["GET"])
def health():
    """Return 200 with DB status; DB failure does NOT make this 5xx."""
    logger.info("GET /health called")
    db_status = "ok"
    db_message = "Connected"

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        logger.info("DB health check: OK")
    except MySQLError as exc:
        db_status = "error"
        db_message = str(exc)
        logger.warning("DB health check failed: %s", exc)

    return jsonify({
        "status":   "ok",
        "database": db_status,
        "db_info":  db_message,
    }), 200


# ── Startup: wait for MySQL ───────────────────────────────────────────────────

def wait_for_db(retries: int = 30, delay: int = 2) -> None:
    """Block until MySQL is reachable or retries exhausted."""
    logger.info("Waiting for MySQL at %s:%s…", DB_CONFIG["host"], DB_CONFIG["port"])
    for attempt in range(1, retries + 1):
        try:
            conn = get_db_connection()
            conn.close()
            logger.info("MySQL is ready (attempt %d/%d)", attempt, retries)
            return
        except MySQLError as exc:
            logger.warning(
                "MySQL not ready (attempt %d/%d): %s — retrying in %ds…",
                attempt, retries, exc, delay
            )
            time.sleep(delay)
    logger.error("MySQL did not become ready after %d attempts. Exiting.", retries)
    raise SystemExit(1)


if __name__ == "__main__":
    wait_for_db()
    port = int(os.environ.get("PORT", 5000))
    logger.info("Starting Flask on port %d", port)
    app.run(host="0.0.0.0", port=port)