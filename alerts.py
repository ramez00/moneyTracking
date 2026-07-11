"""Visitor email alerts for the landing page.

Sends an email (IP, approximate location, timestamp, user-agent) to a
configured address whenever the landing page is visited, throttled per IP
and run off the request thread so it never delays the response.

Note: IP-based geolocation is approximate (city-level at best, often wrong
for mobile/VPN/corporate networks) — do not treat it as a precise address.
"""
import json
import logging
import os
import smtplib
import threading
import time
import urllib.error
import urllib.request
from email.message import EmailMessage

logger = logging.getLogger("alerts")


def _load_dotenv():
    """Load KEY=VALUE pairs from a .env file next to this module.

    Minimal stdlib-only loader (no python-dotenv dependency, per
    CLAUDE.md's no-new-packages rule). Real environment variables always
    take precedence over .env values.
    """
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.isfile(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

ALERT_TO = os.environ.get("ALERT_EMAIL_TO")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")

THROTTLE_SECONDS = 60 * 60  # 1 email per IP per hour

_last_alert_by_ip = {}
_throttle_lock = threading.Lock()


def get_client_ip(request):
    """Best-effort real client IP behind a reverse proxy / load balancer."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    return request.remote_addr or "unknown"


def _should_send(ip):
    now = time.monotonic()
    with _throttle_lock:
        last_sent = _last_alert_by_ip.get(ip)
        if last_sent is not None and (now - last_sent) < THROTTLE_SECONDS:
            return False
        _last_alert_by_ip[ip] = now
        return True


def _lookup_location(ip):
    if ip in ("unknown", "127.0.0.1", "::1"):
        return "local/unknown"

    url = f"http://ip-api.com/json/{ip}?fields=status,city,regionName,country"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        logger.warning("alerts: geolocation lookup failed for %s: %s", ip, e)
        return "lookup failed"

    if data.get("status") != "success":
        return "unavailable"

    parts = [p for p in (data.get("city"), data.get("regionName"), data.get("country")) if p]
    return ", ".join(parts) if parts else "unavailable"


def _send_email(ip, location, timestamp, user_agent):
    missing = [
        name
        for name, value in (
            ("ALERT_EMAIL_TO", ALERT_TO),
            ("SMTP_USER", SMTP_USER),
            ("SMTP_PASSWORD", SMTP_PASSWORD),
        )
        if not value
    ]
    if missing:
        logger.warning("alerts: skipping email, missing env vars: %s", ", ".join(missing))
        return

    message = EmailMessage()
    message["Subject"] = "Spendly landing page visit"
    message["From"] = SMTP_USER
    message["To"] = ALERT_TO
    message.set_content(
        "New landing page visit\n\n"
        f"IP address: {ip}\n"
        f"Approximate location: {location} (city-level estimate, not exact)\n"
        f"Timestamp: {timestamp}\n"
        f"User-agent: {user_agent}\n"
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=5) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(message)

    logger.info("alerts: visit alert email sent for %s", ip)


def _run(ip, timestamp, user_agent):
    location = _lookup_location(ip)
    try:
        _send_email(ip, location, timestamp, user_agent)
    except (smtplib.SMTPException, OSError) as e:
        logger.warning("alerts: failed to send visit alert email for %s: %s", ip, e)


def send_visit_alert(request):
    """Fire-and-forget visitor alert; throttled per IP, non-blocking."""
    ip = get_client_ip(request)

    if not _should_send(ip):
        return

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    user_agent = request.headers.get("User-Agent", "unknown")

    threading.Thread(
        target=_run, args=(ip, timestamp, user_agent), daemon=True
    ).start()
