"""Send a diagnostic email through the configured SMTP provider.

Run manually with an optional safe test recipient:

    python test_email.py [test-recipient@example.com]

Without an argument, the message is sent to the configured sender mailbox.
This script does not run or send mail when imported by a test runner.
"""

import os
import smtplib
import ssl
import sys
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def main():
    sender = os.environ.get("GMAIL_ADDRESS")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not sender or not password:
        print("SMTP credentials are not configured.")
        return 1

    recipient = sys.argv[1] if len(sys.argv) > 1 else sender
    message = EmailMessage()
    message["Subject"] = "SMTP configuration test"
    message["From"] = sender
    message["To"] = recipient
    message.set_content("This is a diagnostic message from the website email service.")

    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    use_ssl = os.environ.get("SMTP_USE_SSL", "0") == "1"

    try:
        smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
        with smtp_class(host, port, timeout=15) as server:
            if not use_ssl:
                server.starttls(context=ssl.create_default_context())
            server.login(sender, password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException, ssl.SSLError, ValueError) as exc:
        print(f"SMTP submission failed ({type(exc).__name__}).")
        return 1

    print("SMTP accepted the diagnostic email; inbox delivery was not verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
