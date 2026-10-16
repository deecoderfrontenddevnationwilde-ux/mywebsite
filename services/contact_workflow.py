from datetime import datetime, timedelta, timezone
import logging

from extensions import db
from models import ContactMessageActivity
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)
SENDING_STALE_AFTER = timedelta(minutes=2)


def get_or_create_email_activity(
    contact_message,
    event_type,
    *,
    body=None,
    recipient_email=None,
    email_subject=None,
    request_token=None,
    admin_username=None,
):
    if request_token:
        activity = ContactMessageActivity.query.filter_by(request_token=request_token).first()
        if activity:
            return activity

    activity = ContactMessageActivity.query.filter_by(
        contact_message_id=contact_message.id,
        event_type=event_type,
    ).order_by(ContactMessageActivity.created_at.desc()).first()
    if activity and event_type in {
        ContactMessageActivity.TYPE_BUSINESS_NOTIFICATION,
        ContactMessageActivity.TYPE_SUBMISSION_CONFIRMATION,
    }:
        return activity

    activity = ContactMessageActivity(
        contact_message=contact_message,
        event_type=event_type,
        body=body,
        recipient_email=recipient_email,
        email_subject=email_subject,
        request_token=request_token,
        admin_username=admin_username,
        email_status=ContactMessageActivity.EMAIL_FAILED,
    )
    db.session.add(activity)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if request_token:
            existing = ContactMessageActivity.query.filter_by(request_token=request_token).first()
            if existing:
                return existing
        raise
    return activity


def attempt_contact_email(activity, send):
    if activity.email_status == ContactMessageActivity.EMAIL_ACCEPTED:
        return True

    now = datetime.now(timezone.utc)
    if activity.email_status == ContactMessageActivity.EMAIL_SENDING and activity.last_attempt_at:
        last_attempt = activity.last_attempt_at
        if last_attempt.tzinfo is None:
            last_attempt = last_attempt.replace(tzinfo=timezone.utc)
        if now - last_attempt < SENDING_STALE_AFTER:
            return False

    activity.email_status = ContactMessageActivity.EMAIL_SENDING
    activity.attempt_count += 1
    activity.last_attempt_at = now
    activity.last_error = None
    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error("Could not record contact email attempt (%s)", type(exc).__name__)
        return False

    try:
        accepted = bool(send())
    except Exception as exc:
        logger.error("Contact email attempt raised an error (%s)", type(exc).__name__)
        accepted = False

    activity.email_status = (
        ContactMessageActivity.EMAIL_ACCEPTED if accepted
        else ContactMessageActivity.EMAIL_FAILED
    )
    activity.accepted_at = now if accepted else None
    activity.last_error = None if accepted else "The email service did not accept the message."
    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error("Could not record contact email result (%s)", type(exc).__name__)
        return False
    return accepted
