import re

from flask import Blueprint, request, jsonify, current_app
from email_validator import validate_email, EmailNotValidError

from extensions import db
from models import News, Product, Subscriber, ContactMessage
from services.email_service import (
    send_contact_submission_confirmation,
    send_new_contact_notification,
    send_new_subscription_notification,
    send_subscription_confirmation,
)

api_bp = Blueprint("api", __name__)


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


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@api_bp.route("/contact", methods=["POST"])
def api_contact():
    payload = request.get_json(silent=True) or request.form
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip()
    subject = (payload.get("subject") or payload.get("service") or "").strip()
    message = (payload.get("message") or "").strip()

    errors = {}
    if not name:
        errors["name"] = "Name is required."
    if not email or not _EMAIL_RE.match(email):
        errors["email"] = "A valid email is required."
    if not message:
        errors["message"] = "Message is required."

    if errors:
        return jsonify({"success": False, "message": "Please fix the errors below.", "errors": errors}), 400

    contact_message = ContactMessage(name=name, email=email, subject=subject, message=message)
    db.session.add(contact_message)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to save contact message")
        return jsonify({"success": False, "message": "Something went wrong. Please try again."}), 500

    if not send_contact_submission_confirmation(contact_message):
        current_app.logger.warning("Contact confirmation email failed for message id=%s", contact_message.id)
    if not send_new_contact_notification(contact_message):
        current_app.logger.warning("Contact admin notification email failed for message id=%s", contact_message.id)

    return jsonify(
        {
            "success": True,
            "message": "Your message has been submitted successfully and is waiting for admin approval.",
        }
    )
