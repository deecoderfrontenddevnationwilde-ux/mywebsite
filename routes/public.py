from datetime import datetime, timezone
import re

from flask import Blueprint, render_template, abort, request, send_from_directory, current_app
from sqlalchemy import func, or_

from extensions import db
from models import FeaturedProject, News, Product, ProductVideo, ServiceOffer, Subscriber

public_bp = Blueprint("public", __name__)


@public_bp.route("/uploads/<path:filename>")
def uploaded_file(filename):
    """Serve user-uploaded news/product images (stored outside static/)."""
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@public_bp.route("/")
def home():
    service_offers = ServiceOffer.query.filter_by(active=True).order_by(ServiceOffer.display_order, ServiceOffer.id).all()
    featured_projects = (
        FeaturedProject.query.filter_by(active=True)
        .order_by(FeaturedProject.display_order, FeaturedProject.id)
        .limit(3)
        .all()
    )
    latest_news = (
        News.query.filter_by(published=True)
        .order_by(News.published_at.desc(), News.created_at.desc())
        .limit(3)
        .all()
    )
    featured_products = (
        Product.query.filter_by(published=True, featured=True)
        .order_by(Product.created_at.desc())
        .limit(3)
        .all()
    )
    product_videos = (
        ProductVideo.query.order_by(ProductVideo.created_at.desc(), ProductVideo.id.desc())
        .limit(3)
        .all()
    )
    if len(featured_products) < 3:
        # Fall back to the latest published products if not enough are featured
        extra = (
            Product.query.filter_by(published=True)
            .order_by(Product.created_at.desc())
            .limit(3)
            .all()
        )
        seen_ids = {p.id for p in featured_products}
        for p in extra:
            if p.id not in seen_ids:
                featured_products.append(p)
            if len(featured_products) >= 3:
                break

    return render_template(
        "index.html",
        latest_news=latest_news,
        featured_products=featured_products,
        product_videos=product_videos,
        service_offers=service_offers,
        featured_projects=featured_projects,
    )


@public_bp.route("/about")
def about():
    return render_template("about.html")


@public_bp.route("/contact")
def contact():
    return render_template("contact.html")


@public_bp.route("/terms")
def terms():
    return render_template("terms.html")


@public_bp.route("/privacy")
def privacy():
    return render_template("privacy.html")


@public_bp.route("/news")
def news_list():
    page = request.args.get("page", 1, type=int)
    pagination = (
        News.query.filter_by(published=True)
        .order_by(News.published_at.desc(), News.created_at.desc())
        .paginate(page=page, per_page=9, error_out=False)
    )
    return render_template("news.html", pagination=pagination, articles=pagination.items)


@public_bp.route("/news/<slug>")
def news_detail(slug):
    article = News.query.filter_by(slug=slug, published=True).first()
    if not article:
        abort(404)
    publication_date = func.coalesce(News.published_at, News.created_at)
    article_date = article.published_at or article.created_at
    newer_article = (
        News.query.filter(
            News.published.is_(True),
            or_(
                publication_date > article_date,
                (publication_date == article_date) & (News.id > article.id),
            ),
        )
        .order_by(publication_date.asc(), News.id.asc())
        .first()
    )
    older_article = (
        News.query.filter(
            News.published.is_(True),
            or_(
                publication_date < article_date,
                (publication_date == article_date) & (News.id < article.id),
            ),
        )
        .order_by(publication_date.desc(), News.id.desc())
        .first()
    )
    related = (
        News.query.filter(News.published.is_(True), News.id != article.id)
        .order_by(publication_date.desc(), News.id.desc())
        .limit(3)
        .all()
    )
    word_count = len(re.sub(r"<[^>]+>", " ", article.content or "").split())
    reading_minutes = max(1, (word_count + 219) // 220)
    return render_template(
        "article.html",
        article=article,
        related=related,
        newer_article=newer_article,
        older_article=older_article,
        reading_minutes=reading_minutes,
    )


@public_bp.route("/projects")
def projects_list():
    page = request.args.get("page", 1, type=int)
    pagination = (
        FeaturedProject.query.filter_by(active=True)
        .order_by(FeaturedProject.display_order, FeaturedProject.id)
        .paginate(page=page, per_page=9, error_out=False)
    )
    return render_template(
        "projects.html",
        pagination=pagination,
        projects=pagination.items,
    )


@public_bp.route("/products")
def products_list():
    page = request.args.get("page", 1, type=int)
    category = request.args.get("category")
    query = Product.query.filter_by(published=True)
    if category:
        query = query.filter_by(category=category)
    pagination = query.order_by(Product.created_at.desc()).paginate(page=page, per_page=9, error_out=False)

    categories = [
        c[0]
        for c in db.session.query(Product.category)
        .filter(Product.published.is_(True), Product.category.isnot(None))
        .distinct()
        .all()
    ]
    return render_template(
        "products.html",
        pagination=pagination,
        products=pagination.items,
        categories=categories,
        active_category=category,
    )


@public_bp.route("/videos")
def video_list():
    page = request.args.get("page", 1, type=int)
    pagination = (
        ProductVideo.query.order_by(ProductVideo.created_at.desc(), ProductVideo.id.desc())
        .paginate(page=page, per_page=9, error_out=False)
    )
    return render_template(
        "videos.html",
        pagination=pagination,
        videos=pagination.items,
    )


@public_bp.route("/products/<slug>")
def product_detail(slug):
    product = Product.query.filter_by(slug=slug, published=True).first()
    if not product:
        abort(404)
    related = (
        Product.query.filter(
            Product.published.is_(True),
            Product.id != product.id,
            Product.category == product.category,
        )
        .order_by(Product.created_at.desc(), Product.id.desc())
        .limit(3)
        .all()
    )
    return render_template("product.html", product=product, related=related)


@public_bp.route("/unsubscribe/<token>")
def unsubscribe(token):
    subscriber = Subscriber.query.filter_by(unsubscribe_token=token).first()
    if subscriber and subscriber.subscribed:
        subscriber.subscribed = False
        subscriber.unsubscribed_at = datetime.now(timezone.utc)
        db.session.commit()
    return render_template("unsubscribe.html", success=bool(subscriber))
