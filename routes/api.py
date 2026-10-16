import hashlib
import hmac
import re
import uuid
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify, current_app
from email_validator import validate_email, EmailNotValidError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from wtforms.validators import ValidationError
from flask_wtf.csrf import validate_csrf

from extensions import db
from models import News, Product, Subscriber, ContactMessage, ContactMessageActivity
from services.email_service import (
    send_contact_submission_confirmation,
    send_new_contact_notification,
    send_new_subscription_notification,
    send_subscription_confirmation,
)
from services.contact_workflow import attempt_contact_email, get_or_create_email_activity

api_bp = Blueprint("api", __name__)

CONTACT_RATE_LIMIT = 5
CONTACT_RATE_WINDOW = timedelta(hours=1)


def _news_to_dict(n: News) -> dict:
    return {
        "id": n.id,
        "title": n.title,
        "slug": n.slug,
        "summary": n.summary,
        "featured_image": n.featured_image,
        "author": n.author,
        "published_at": n.published_at.isoformat() if n.published_at else None,
    }


def _product_to_dict(p: Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "slug": p.slug,
        "short_description": p.short_description,
        "price": str(p.price) if p.price is not None else None,
        "image": p.image,
        "category": p.category,
        "featured": p.featured,
        "stock_status": p.stock_status,
    }


@api_bp.route("/news")
def api_news_list():
    articles = (
        News.query.filter_by(published=True)
        .order_by(News.published_at.desc())
        .limit(50)
        .all()
    )
    return jsonify({"news": [_news_to_dict(n) for n in articles]})


@api_bp.route("/news/<slug>")
def api_news_detail(slug):
    article = News.query.filter_by(slug=slug, published=True).first()
    if not article:
        return jsonify({"error": "Article not found"}), 404
    data = _news_to_dict(article)
    data["content"] = article.content
    return jsonify(data)


@api_bp.route("/products")
def api_products_list():
    products = Product.query.filter_by(published=True).order_by(Product.created_at.desc()).limit(50).all()
    return jsonify({"products": [_product_to_dict(p) for p in products]})


@api_bp.route("/products/<slug>")
def api_product_detail(slug):
    product = Product.query.filter_by(slug=slug, published=True).first()
    if not product:
        return jsonify({"error": "Product not found"}), 404
    data = _product_to_dict(product)
    data["description"] = product.description
    return jsonify(data)


@api_bp.route("/subscribe", methods=["POST"])
def api_subscribe():
    payload = request.get_json(silent=True) or request.form
    email = (payload.get("email") or "").strip()

    if not email:
        return jsonify({"success": False, "message": "Please enter an email address."}), 400

    try:
        valid = validate_email(email, check_deliverability=False)
        email = valid.normalized
    except EmailNotValidError:
        return jsonify({"success": False, "message": "Please enter a valid email address."}), 400

    existing = Subscriber.query.filter_by(email=email).first()
    if existing:
        if existing.subscribed:
            return jsonify(
                {"success": True, "message": "You're already subscribed! We'll keep you updated."}
            )
        # Re-subscribe someone who previously unsubscribed
        existing.subscribed = True
        existing.unsubscribed_at = None
        db.session.commit()
        if not send_subscription_confirmation(existing):
            current_app.logger.warning("Subscriber confirmation email failed for subscriber id=%s", existing.id)
        if not send_new_subscription_notification(existing):
            current_app.logger.warning("Subscriber admin notification email failed for subscriber id=%s", existing.id)
        return jsonify(
            {"success": True, "message": "You're subscribed! We'll keep you updated with our latest news and products."}
        )

    subscriber = Subscriber(email=email)
    db.session.add(subscriber)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to save subscriber")
        return jsonify({"success": False, "message": "Something went wrong. Please try again."}), 500

    if not send_subscription_confirmation(subscriber):
        current_app.logger.warning("Subscriber confirmation email failed for subscriber id=%s", subscriber.id)
    if not send_new_subscription_notification(subscriber):
        current_app.logger.warning("Subscriber admin notification email failed for subscriber id=%s", subscriber.id)
    return jsonify(
        {"success": True, "message": "You're subscribed! We'll keep you updated with our latest news and products."}
    )


@api_bp.route("/contact", methods=["POST"])
def api_contact():
    if not request.is_json:
        return jsonify({"success": False, "message": "Please submit a valid form."}), 415

    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"success": False, "message": "Please submit a valid form."}), 400
    if not isinstance(payload, dict):
        return jsonify({"success": False, "message": "Please submit a valid form."}), 400

    if current_app.config.get("WTF_CSRF_ENABLED", True):
        try:
            validate_csrf(request.headers.get("X-CSRFToken"))
        except ValidationError:
            return jsonify(
                {"success": False, "message": "Please refresh the page and try again."}
            ), 400

    for field in ("name", "email", "subject", "message", "phone"):
        if not isinstance(payload.get(field, ""), str):
            return jsonify({"success": False, "message": "Please submit a valid form."}), 400
    for field in ("service", "website", "contact_reference_code", "submission_token"):
        if payload.get(field) is not None and not isinstance(payload[field], str):
            return jsonify({"success": False, "message": "Please submit a valid form."}), 400

    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip()
    phone_input = payload.get("phone") or ""
    phone = re.sub(r"\s+", " ", phone_input.strip())
    subject_input = payload.get("subject") or ""
    subject = re.sub(r"\s+", " ", subject_input.strip())
    message = (payload.get("message") or "").strip()
    raw_submission_token = payload.get("submission_token", "")
    try:
        submission_token = str(uuid.UUID(raw_submission_token))
    except (AttributeError, ValueError):
        return jsonify({"success": False, "message": "Please refresh the page and try again."}), 400

    # Check only the explicit honeypot; "website" is ignored for older clients
    # where browser autofill could populate the former honeypot input.
    if (payload.get("contact_reference_code") or "").strip():
        return jsonify({"success": False, "message": "Unable to submit this request."}), 400

    errors = {}
    if not name:
        errors["name"] = "Name is required."
    elif len(name) > 150:
        errors["name"] = "Name must be 150 characters or fewer."
    try:
        valid_email = validate_email(email, check_deliverability=False)
        email = valid_email.normalized
    except EmailNotValidError:
        errors["email"] = "A valid email is required."
    if len(email) > 254:
        errors["email"] = "A valid email is required."
    if not subject:
        errors["subject"] = "Subject is required."
    elif len(subject) > 200:
        errors["subject"] = "Subject must be 200 characters or fewer."
    if phone and (len(phone) > 50 or not re.fullmatch(r"[0-9+().\-\s]+", phone)):
        errors["phone"] = "Enter a valid phone number, or leave this field empty."
    if not message:
        errors["message"] = "Message is required."
    elif len(message) > 5000:
        errors["message"] = "Message must be 5000 characters or fewer."

    if errors:
        return jsonify({"success": False, "message": "Please fix the errors below.", "errors": errors}), 400

    existing_message = ContactMessage.query.filter_by(submission_token=submission_token).first()
    if existing_message:
        if (
            existing_message.name != name
            or existing_message.email != email
            or existing_message.phone != (phone or None)
            or existing_message.subject != (subject or None)
            or existing_message.message != message
        ):
            return jsonify(
                {"success": False, "message": "This submission token has already been used."}
            ), 409
        contact_message = existing_message
    else:
        contact_message = None

    # Only a keyed digest is stored; raw client IP addresses are not retained.
    remote_addr = request.remote_addr or "unknown"
    fingerprint = hmac.new(
        current_app.config["SECRET_KEY"].encode("utf-8"),
        remote_addr.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - CONTACT_RATE_WINDOW
    if contact_message is None:
        recent_submissions = ContactMessage.query.filter(
            ContactMessage.request_fingerprint == fingerprint,
            ContactMessage.created_at >= cutoff,
        ).count()
        if recent_submissions >= CONTACT_RATE_LIMIT:
            return jsonify(
                {
                    "success": False,
                    "message": "Too many submissions. Please wait before trying again.",
                }
            ), 429

        contact_message = ContactMessage(
            name=name,
            email=email,
            phone=phone or None,
            subject=subject or None,
            message=message,
            request_fingerprint=fingerprint,
            submission_token=submission_token,
        )
        db.session.add(contact_message)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            contact_message = ContactMessage.query.filter_by(submission_token=submission_token).first()
            if not contact_message:
                current_app.logger.error("Failed to save contact message (integrity error)")
                return jsonify({"success": False, "message": "Something went wrong. Please try again."}), 500
            if (
                contact_message.name != name
                or contact_message.email != email
                or contact_message.phone != (phone or None)
                or contact_message.subject != (subject or None)
                or contact_message.message != message
            ):
                return jsonify(
                    {"success": False, "message": "This submission token has already been used."}
                ), 409
        except SQLAlchemyError as exc:
            db.session.rollback()
            current_app.logger.error("Failed to save contact message (%s)", type(exc).__name__)
            return jsonify({"success": False, "message": "Something went wrong. Please try again."}), 500

    if not contact_message.notification_email_submitted:
        activity = get_or_create_email_activity(
            contact_message,
            ContactMessageActivity.TYPE_BUSINESS_NOTIFICATION,
        )
        if not attempt_contact_email(
            activity,
            lambda: send_new_contact_notification(contact_message),
        ):
            current_app.logger.error(
                "Contact notification email was not accepted by the mail service for message id=%s",
                contact_message.id,
            )
            return jsonify(
                {
                    "success": False,
                    "saved": True,
                    "message": (
                        "Your message was saved, but we couldn't notify our team. "
                        "Please retry shortly or contact us directly if your request is urgent."
                    ),
                }
            ), 503
        contact_message.notification_email_submitted = True
        try:
            db.session.commit()
        except SQLAlchemyError as exc:
            db.session.rollback()
            current_app.logger.error(
                "Failed to record contact notification status (%s)",
                type(exc).__name__,
            )
            return jsonify(
                {
                    "success": False,
                    "saved": True,
                    "message": "Your message was saved, but its notification status could not be recorded.",
                }
            ), 500

    if not contact_message.confirmation_email_submitted:
        activity = get_or_create_email_activity(
            contact_message,
            ContactMessageActivity.TYPE_SUBMISSION_CONFIRMATION,
        )
        if not attempt_contact_email(
            activity,
            lambda: send_contact_submission_confirmation(contact_message),
        ):
            current_app.logger.warning(
                "Contact confirmation email was not accepted by the mail service for message id=%s",
                contact_message.id,
            )
            return jsonify(
                {
                    "success": False,
                    "saved": True,
                    "notification_sent": True,
                    "message": (
                        "Your message was sent to our team, but we couldn't send your "
                        "confirmation email. Please try again shortly."
                    ),
                }
            ), 503
        contact_message.confirmation_email_submitted = True
        try:
            db.session.commit()
        except SQLAlchemyError as exc:
            db.session.rollback()
            current_app.logger.error(
                "Failed to record contact confirmation status (%s)",
                type(exc).__name__,
            )
            return jsonify(
                {
                    "success": False,
                    "saved": True,
                    "message": "Your message was saved, but its notification status could not be recorded.",
                }
            ), 500

    return jsonify(
        {
            "success": True,
            "message": "Your message has been sent to our team, and a confirmation email was accepted for delivery.",
        }
    )
