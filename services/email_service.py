"""
Reusable email service.

All outgoing email goes through send_email() here, using Gmail SMTP with
credentials read from environment variables (never hard-coded, never sent
to the browser). To swap providers later (e.g. SendGrid, SES), only this
file needs to change — callers just use the send_* functions below.

For the first version this sends synchronously over SMTP. That is fine for
low volume; if the site expects heavy traffic, wrap calls to send_email()
in a background task queue (Celery/RQ) later without changing the public
functions in this file.
"""

from __future__ import annotations

import logging
import re
import ssl
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

from flask import current_app, render_template

logger = logging.getLogger(__name__)


class EmailError(Exception):
    pass


def send_email(
    to_address: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
    *,
    reply_to: str | None = None,
) -> bool:
    """
    Send one email via Gmail SMTP.

    Returns True on success, False on failure. Failures are logged on the
    server and never surfaced to end users as raw errors.
    """
    gmail_address = current_app.config.get("GMAIL_ADDRESS")
    gmail_password = current_app.config.get("GMAIL_APP_PASSWORD")

    if not gmail_address or not gmail_password:
        logger.error("Email not sent because SMTP credentials are not configured")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{current_app.config.get('COMPANY_NAME', 'Website')} <{gmail_address}>"
    msg["To"] = to_address
    if reply_to:
        msg["Reply-To"] = reply_to

    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    phase = "connect"
    try:
        with _open_smtp_server() as server:
            phase = "authentication"
            server.login(gmail_address, gmail_password)
            phase = "message submission"
            refused_recipients = server.sendmail(gmail_address, [to_address], msg.as_string())
            if refused_recipients:
                logger.error("SMTP refused an email recipient (%s)", len(refused_recipients))
                return False
        logger.info("SMTP accepted an email for delivery")
        return True
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        logger.error("SMTP %s failed (%s)", phase, type(exc).__name__)
        return False


def _open_smtp_server():
    host = current_app.config["SMTP_HOST"]
    port = current_app.config["SMTP_PORT"]
    timeout = current_app.config.get("SMTP_TIMEOUT", 20)
    tls_context = ssl.create_default_context()
    if current_app.config.get("SMTP_USE_SSL"):
        return smtplib.SMTP_SSL(host, port, timeout=timeout, context=tls_context)

    server = smtplib.SMTP(host, port, timeout=timeout)
    try:
        server.ehlo()
        server.starttls(context=tls_context)
        server.ehlo()
    except (OSError, smtplib.SMTPException, ValueError):
        server.close()
        raise
    return server


def check_smtp_connection() -> bool:
    """Verify SMTP connectivity and authentication without sending a message."""
    gmail_address = current_app.config.get("GMAIL_ADDRESS")
    gmail_password = current_app.config.get("GMAIL_APP_PASSWORD")
    if not gmail_address or not gmail_password:
        logger.error("SMTP check unavailable because credentials are not configured")
        return False

    phase = "connect"
    try:
        with _open_smtp_server() as server:
            phase = "authentication"
            server.login(gmail_address, gmail_password)
        return True
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        logger.error("SMTP connectivity check failed during %s (%s)", phase, type(exc).__name__)
        return False


def _notification_email() -> str | None:
    recipient = current_app.config.get("NOTIFICATION_EMAIL")
    if not recipient:
        logger.error("Admin notification email is not configured")
    return recipient


def _contact_notification_email() -> str | None:
    recipient = current_app.config.get("CONTACT_NOTIFICATION_EMAIL")
    if not recipient:
        logger.error("Contact notification email is not configured")
    return recipient


def send_new_subscription_notification(subscriber) -> bool:
    recipient = _notification_email()
    if not recipient:
        return False
    return send_email(
        recipient,
        f"New newsletter subscription: {subscriber.email}",
        f"<p>A new newsletter subscription was received.</p><p>Email: {subscriber.email}</p>",
        text_body=f"A new newsletter subscription was received.\nEmail: {subscriber.email}",
    )


def send_new_contact_notification(contact_message) -> bool:
    recipient = _contact_notification_email()
    if not recipient:
        return False
    name = escape(contact_message.name)
    email = escape(contact_message.email)
    subject_text = re.sub(r"\s+", " ", contact_message.subject or "(no subject)").strip()
    subject = escape(subject_text)
    message = escape(contact_message.message).replace("\n", "<br>")
    phone = escape(contact_message.phone or "")
    phone_line = f"<br><strong>Phone:</strong> {phone}" if phone else ""
    phone_text = f"Phone: {contact_message.phone}\n" if contact_message.phone else ""
    return send_email(
        recipient,
        f"New contact form message: {subject_text}",
        (
            "<p>A new contact form message was received.</p>"
            f"<p><strong>Name:</strong> {name}<br>"
            f"<strong>Email:</strong> {email}<br>"
            f"<strong>Subject:</strong> {subject}{phone_line}</p>"
            f"<p>{message}</p>"
        ),
        text_body=(
            "A new contact form message was received.\n"
            f"Name: {contact_message.name}\nEmail: {contact_message.email}\n"
            f"{phone_text}Subject: {subject_text}\n\n{contact_message.message}"
        ),
        reply_to=contact_message.email,
    )


def _company_name() -> str:
    return current_app.config.get("COMPANY_NAME", "Our Company")


def _site_url() -> str:
    return current_app.config.get("SITE_URL", "").rstrip("/")


def send_subscription_confirmation(subscriber) -> bool:
    unsubscribe_link = f"{_site_url()}/unsubscribe/{subscriber.unsubscribe_token}"
    html = render_template(
        "emails/subscription_confirmation.html",
        company_name=_company_name(),
        unsubscribe_link=unsubscribe_link,
    )
    return send_email(
        subscriber.email,
        f"You're subscribed to {_company_name()}!",
        html,
        text_body=(
            f"You're subscribed! We'll keep you updated with our latest news and products.\n\n"
            f"Unsubscribe any time: {unsubscribe_link}"
        ),
    )


def send_new_news_notification(subscriber, news_article) -> bool:
    article_link = f"{_site_url()}/news/{news_article.slug}"
    unsubscribe_link = f"{_site_url()}/unsubscribe/{subscriber.unsubscribe_token}"
    html = render_template(
        "emails/news_notification.html",
        company_name=_company_name(),
        article=news_article,
        article_link=article_link,
        unsubscribe_link=unsubscribe_link,
    )
    return send_email(
        subscriber.email,
        f"New Update from {_company_name()}: {news_article.title}",
        html,
        text_body=(
            f"We have just published a new article: {news_article.title}\n\n"
            f"{news_article.summary}\n\nRead the full article: {article_link}\n\n"
            f"Unsubscribe: {unsubscribe_link}"
        ),
    )


def send_contact_submission_confirmation(contact_message) -> bool:
    html = render_template(
        "emails/contact_received.html",
        company_name=_company_name(),
        contact=contact_message,
    )
    return send_email(
        contact_message.email,
        f"We received your message — {_company_name()}",
        html,
        text_body=(
            "Your message has been received and is currently awaiting review. "
            "We'll get back to you soon."
        ),
    )


def send_contact_admin_reply(
    contact_message,
    reply_text: str,
    *,
    recipient_email: str | None = None,
    subject: str | None = None,
) -> bool:
    safe_reply = escape(reply_text).replace("\n", "<br>")
    return send_email(
        recipient_email or contact_message.email,
        subject or f"Reply to your message — {_company_name()}",
        (
            f"<p>Hello {escape(contact_message.name)},</p>"
            f"<p>{safe_reply}</p>"
            f"<p>— The {escape(_company_name())} Team</p>"
        ),
        text_body=(
            f"Hello {contact_message.name},\n\n{reply_text}\n\n"
            f"— The {_company_name()} Team"
        ),
    )


def send_contact_approval_notification(contact_message) -> bool:
    html = render_template(
        "emails/contact_approved.html",
        company_name=_company_name(),
        contact=contact_message,
    )
    return send_email(
        contact_message.email,
        f"Your request has been accepted — {_company_name()}",
        html,
        text_body=(
            "Your request has been reviewed and accepted by our team. "
            "We will get back to you as soon as possible."
            + (f"\n\nA note from our team:\n{contact_message.admin_note}" if contact_message.admin_note else "")
        ),
    )


def send_contact_declined_notification(contact_message) -> bool:
    html = render_template(
        "emails/contact_declined.html",
        company_name=_company_name(),
        contact=contact_message,
    )
    return send_email(
        contact_message.email,
        f"An update on your message — {_company_name()}",
        html,
        text_body=(
            "Your request has been reviewed and we are unable to accept it at this time."
            + (f"\n\nA note from our team:\n{contact_message.admin_note}" if contact_message.admin_note else "")
        ),
    )
