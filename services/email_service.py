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
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

from flask import current_app, render_template

logger = logging.getLogger(__name__)


class EmailError(Exception):
    pass


def send_email(to_address: str, subject: str, html_body: str, text_body: str | None = None) -> bool:
    """
    Send one email via Gmail SMTP.

    Returns True on success, False on failure. Failures are logged on the
    server and never surfaced to end users as raw errors.
    """
    gmail_address = current_app.config.get("GMAIL_ADDRESS")
    gmail_password = current_app.config.get("GMAIL_APP_PASSWORD")

    if not gmail_address or not gmail_password:
        logger.warning(
            "Email not sent (GMAIL_ADDRESS / GMAIL_APP_PASSWORD not configured): "
            "subject=%r to=%r",
            subject,
            to_address,
        )
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{current_app.config.get('COMPANY_NAME', 'Website')} <{gmail_address}>"
    msg["To"] = to_address

    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        smtp_class = smtplib.SMTP_SSL if current_app.config.get("SMTP_USE_SSL") else smtplib.SMTP
        with smtp_class(current_app.config["SMTP_HOST"], current_app.config["SMTP_PORT"], timeout=15) as server:
            if not current_app.config.get("SMTP_USE_SSL"):
                server.starttls()
            server.login(gmail_address, gmail_password)
            server.sendmail(gmail_address, [to_address], msg.as_string())
        logger.info("Email sent successfully: subject=%r to=%r", subject, to_address)
        return True
    except Exception:
        logger.exception("Failed to send email to %s (subject=%r)", to_address, subject)
        return False


def _notification_email() -> str | None:
    recipient = current_app.config.get("NOTIFICATION_EMAIL")
    if not recipient:
        logger.error("Admin notification email is not configured")
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
    recipient = _notification_email()
    if not recipient:
        return False
    name = escape(contact_message.name)
    email = escape(contact_message.email)
    subject_text = contact_message.subject or "(no subject)"
    subject = escape(subject_text)
    message = escape(contact_message.message).replace("\n", "<br>")
    return send_email(
        recipient,
        f"New contact form message: {subject_text}",
        (
            "<p>A new contact form message was received.</p>"
            f"<p><strong>Name:</strong> {name}<br>"
            f"<strong>Email:</strong> {email}<br>"
            f"<strong>Subject:</strong> {subject}</p>"
            f"<p>{message}</p>"
        ),
        text_body=(
            "A new contact form message was received.\n"
            f"Name: {contact_message.name}\nEmail: {contact_message.email}\n"
            f"Subject: {subject_text}\n\n{contact_message.message}"
        ),
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


def send_contact_approval_notification(contact_message) -> bool:
    html = render_template(
        "emails/contact_approved.html",
        company_name=_company_name(),
        contact=contact_message,
    )
    return send_email(
        contact_message.email,
        f"Your message has been approved — {_company_name()}",
        html,
        text_body="Your message has been reviewed by our team and approved. We will get back to you as soon as possible.",
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
        text_body="Your message has been reviewed and declined by the admin.",
    )
