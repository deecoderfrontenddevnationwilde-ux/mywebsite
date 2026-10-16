import os
import shutil
import uuid
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urlparse

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, send_from_directory, url_for
from werkzeug.datastructures import FileStorage
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_, case, or_
from email_validator import EmailNotValidError, validate_email

from extensions import db
from models import (
    AdminUser,
    ContactMessage,
    ContactMessageActivity,
    FeaturedProject,
    News,
    Product,
    ProductVideo,
    ServiceOffer,
    Subscriber,
)
from auth import login_admin, logout_admin, login_required, get_current_admin
from utils import delete_uploaded_file, make_unique_slug, save_uploaded_image, save_uploaded_video
from services.email_service import (
    send_new_news_notification,
    send_new_contact_notification,
    send_contact_submission_confirmation,
    send_contact_approval_notification,
    send_contact_declined_notification,
    send_contact_admin_reply,
)
from services.contact_workflow import attempt_contact_email, get_or_create_email_activity

admin_bp = Blueprint("admin", __name__)


# ---------------------------------------------------------------- AUTH ----

@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if get_current_admin():
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        admin_user = AdminUser.query.filter_by(username=username).first()

        if admin_user and admin_user.is_active and admin_user.check_password(password):
            admin_user.last_login_at = datetime.now(timezone.utc)
            db.session.commit()
            login_admin(admin_user)
            flash("Welcome back!", "success")
            return redirect(url_for("admin.dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("admin/login.html")


@admin_bp.route("/logout")
def logout():
    logout_admin()
    flash("You have been logged out.", "success")
    return redirect(url_for("admin.login"))


# ----------------------------------------------------------- DASHBOARD ----

@admin_bp.route("/")
@admin_bp.route("/dashboard")
@login_required
def dashboard():
    stats = {
        "total_offers": ServiceOffer.query.count(),
        "active_offers": ServiceOffer.query.filter_by(active=True).count(),
        "total_projects": FeaturedProject.query.count(),
        "active_projects": FeaturedProject.query.filter_by(active=True).count(),
        "total_news": News.query.count(),
        "published_news": News.query.filter_by(published=True).count(),
        "total_products": Product.query.count(),
        "published_products": Product.query.filter_by(published=True).count(),
        "total_product_videos": ProductVideo.query.count(),
        "total_subscribers": Subscriber.query.filter_by(subscribed=True).count(),
        "pending_messages": ContactMessage.query.filter_by(status=ContactMessage.STATUS_PENDING).count(),
        "in_progress_messages": ContactMessage.query.filter_by(status=ContactMessage.STATUS_IN_PROGRESS).count(),
        "accepted_messages": ContactMessage.query.filter_by(status=ContactMessage.STATUS_ACCEPTED).count(),
        "rejected_messages": ContactMessage.query.filter_by(status=ContactMessage.STATUS_REJECTED).count(),
    }
    recent_messages = (
        ContactMessage.query.filter(ContactMessage.archived_at.is_(None))
        .order_by(ContactMessage.created_at.desc())
        .limit(5)
        .all()
    )
    return render_template("admin/dashboard.html", stats=stats, recent_messages=recent_messages)


# ------------------------------------------------------- CONTENT SECTIONS ----

def _optional_url(value: str, label: str):
    value = (value or "").strip()
    if value and urlparse(value).scheme not in {"http", "https"}:
        raise ValueError(f"{label} must be a full http:// or https:// URL.")
    return value or None


@admin_bp.route("/offers")
@login_required
def offers_index():
    offers = ServiceOffer.query.order_by(ServiceOffer.display_order, ServiceOffer.id).all()
    return render_template("admin/offers_list.html", offers=offers)


@admin_bp.route("/offers/new", methods=["GET", "POST"])
@login_required
def offers_new():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        if not title or not description:
            flash("Title and description are required.", "error")
            return render_template("admin/offer_form.html", offer=None, form=request.form)
        try:
            link_url = _optional_url(request.form.get("link_url"), "Button URL")
            display_order = int(request.form.get("display_order") or 0)
        except ValueError as error:
            flash(str(error) if "URL" in str(error) else "Display order must be a whole number.", "error")
            return render_template("admin/offer_form.html", offer=None, form=request.form)
        offer = ServiceOffer(
            title=title,
            description=description,
            icon=(request.form.get("icon") or "").strip() or None,
            link_url=link_url,
            link_label=(request.form.get("link_label") or "").strip() or None,
            display_order=display_order,
            active=request.form.get("active") == "on",
        )
        db.session.add(offer)
        db.session.commit()
        flash("Offer created.", "success")
        return redirect(url_for("admin.offers_index"))
    return render_template("admin/offer_form.html", offer=None, form={})


@admin_bp.route("/offers/<int:offer_id>/edit", methods=["GET", "POST"])
@login_required
def offers_edit(offer_id):
    offer = ServiceOffer.query.get_or_404(offer_id)
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        if not title or not description:
            flash("Title and description are required.", "error")
            return render_template("admin/offer_form.html", offer=offer, form=request.form)
        try:
            link_url = _optional_url(request.form.get("link_url"), "Button URL")
            display_order = int(request.form.get("display_order") or 0)
        except ValueError as error:
            flash(str(error) if "URL" in str(error) else "Display order must be a whole number.", "error")
            return render_template("admin/offer_form.html", offer=offer, form=request.form)
        offer.title = title
        offer.description = description
        offer.icon = (request.form.get("icon") or "").strip() or None
        offer.link_url = link_url
        offer.link_label = (request.form.get("link_label") or "").strip() or None
        offer.display_order = display_order
        offer.active = request.form.get("active") == "on"
        db.session.commit()
        flash("Offer updated.", "success")
        return redirect(url_for("admin.offers_index"))
    return render_template("admin/offer_form.html", offer=offer, form=None)


@admin_bp.route("/offers/<int:offer_id>/delete", methods=["POST"])
@login_required
def offers_delete(offer_id):
    offer = ServiceOffer.query.get_or_404(offer_id)
    db.session.delete(offer)
    db.session.commit()
    flash("Offer deleted.", "success")
    return redirect(url_for("admin.offers_index"))


@admin_bp.route("/projects")
@login_required
def projects_index():
    projects = FeaturedProject.query.order_by(FeaturedProject.display_order, FeaturedProject.id).all()
    return render_template("admin/projects_list.html", projects=projects)


@admin_bp.route("/projects/new", methods=["GET", "POST"])
@login_required
def projects_new():
    if request.method == "POST":
        project, error = _project_from_request()
        if error:
            return render_template("admin/project_form.html", project=None, form=request.form)
        db.session.add(project)
        db.session.commit()
        flash("Featured project created.", "success")
        return redirect(url_for("admin.projects_index"))
    return render_template("admin/project_form.html", project=None, form={})


@admin_bp.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
@login_required
def projects_edit(project_id):
    project = FeaturedProject.query.get_or_404(project_id)
    if request.method == "POST":
        updated, error = _project_from_request(project)
        if error:
            return render_template("admin/project_form.html", project=project, form=request.form)
        db.session.commit()
        flash("Featured project updated.", "success")
        return redirect(url_for("admin.projects_index"))
    return render_template("admin/project_form.html", project=project, form=None)


@admin_bp.route("/projects/<int:project_id>/delete", methods=["POST"])
@login_required
def projects_delete(project_id):
    project = FeaturedProject.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    flash("Featured project deleted.", "success")
    return redirect(url_for("admin.projects_index"))


def _project_from_request(project=None):
    title = (request.form.get("title") or "").strip()
    short_description = (request.form.get("short_description") or "").strip()
    if not title or not short_description:
        flash("Title and short description are required.", "error")
        return None, "Project title and short description are required."
    try:
        project_url = _optional_url(request.form.get("project_url"), "Project URL")
        github_url = _optional_url(request.form.get("github_url"), "GitHub URL")
        display_order = int(request.form.get("display_order") or 0)
        image_path = save_uploaded_image(
            request.files.get("image"),
            "projects",
            max_size_bytes=current_app.config["MAX_UPLOAD_MB"] * 1024 * 1024,
        )
    except ValueError as error:
        flash(str(error) if "URL" in str(error) or "image" in str(error).lower() else "Display order must be a whole number.", "error")
        return None, str(error)
    if project is None:
        project = FeaturedProject()
    project.title = title
    project.short_description = short_description
    project.description = (request.form.get("description") or "").strip() or None
    project.category = (request.form.get("category") or "").strip() or None
    project.project_url = project_url
    project.github_url = github_url
    project.display_order = display_order
    project.active = request.form.get("active") == "on"
    if image_path:
        project.image = image_path
    return project, None


# ---------------------------------------------------------------- NEWS ----

@admin_bp.route("/news")
@login_required
def news_index():
    articles = News.query.order_by(News.created_at.desc()).all()
    return render_template("admin/news_list.html", articles=articles)


@admin_bp.route("/news/new", methods=["GET", "POST"])
@login_required
def news_new():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        summary = (request.form.get("summary") or "").strip()
        content = request.form.get("content") or ""
        author = (request.form.get("author") or "").strip()
        publish = request.form.get("published") == "on"

        if not title or not summary or not content:
            flash("Title, summary, and content are required.", "error")
            return render_template("admin/news_form.html", article=None, form=request.form)

        try:
            image_path = save_uploaded_image(
                request.files.get("featured_image"),
                "news",
                max_size_bytes=current_app.config["MAX_UPLOAD_MB"] * 1024 * 1024,
            )
        except ValueError as e:
            flash(str(e), "error")
            return render_template("admin/news_form.html", article=None, form=request.form)

        article = News(
            title=title,
            slug=make_unique_slug(title, News),
            summary=summary,
            content=content,
            author=author or get_current_admin().username,
            featured_image=image_path,
            published=publish,
        )
        if publish:
            article.published_at = datetime.now(timezone.utc)

        db.session.add(article)
        db.session.commit()

        _maybe_notify_subscribers_of_news(article)

        flash("News article created.", "success")
        return redirect(url_for("admin.news_index"))

    return render_template("admin/news_form.html", article=None, form={})


@admin_bp.route("/news/<int:article_id>/edit", methods=["GET", "POST"])
@login_required
def news_edit(article_id):
    article = News.query.get_or_404(article_id)

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        summary = (request.form.get("summary") or "").strip()
        content = request.form.get("content") or ""
        author = (request.form.get("author") or "").strip()
        publish = request.form.get("published") == "on"

        if not title or not summary or not content:
            flash("Title, summary, and content are required.", "error")
            return render_template("admin/news_form.html", article=article, form=request.form)

        try:
            image_path = save_uploaded_image(
                request.files.get("featured_image"),
                "news",
                max_size_bytes=current_app.config["MAX_UPLOAD_MB"] * 1024 * 1024,
            )
        except ValueError as e:
            flash(str(e), "error")
            return render_template("admin/news_form.html", article=article, form=request.form)

        was_published = article.published

        if title != article.title:
            article.slug = make_unique_slug(title, News, exclude_id=article.id)
        article.title = title
        article.summary = summary
        article.content = content
        article.author = author or article.author
        if image_path:
            article.featured_image = image_path

        # Publishing transition handling: only treat this as a fresh publish
        # (eligible for a notification) if it was NOT already published.
        if publish and not was_published:
            article.published_at = datetime.now(timezone.utc)
            article.notification_sent = False  # allow a notification for this new publish cycle
        if not publish and was_published:
            article.notification_sent = False  # reset so a future re-publish can notify again

        article.published = publish
        db.session.commit()

        if publish and not was_published:
            _maybe_notify_subscribers_of_news(article)

        flash("News article updated.", "success")
        return redirect(url_for("admin.news_index"))

    return render_template("admin/news_form.html", article=article, form=None)


@admin_bp.route("/news/<int:article_id>/delete", methods=["POST"])
@login_required
def news_delete(article_id):
    article = News.query.get_or_404(article_id)
    db.session.delete(article)
    db.session.commit()
    flash("News article deleted.", "success")
    return redirect(url_for("admin.news_index"))


def _maybe_notify_subscribers_of_news(article: News) -> None:
    """
    Send the "new article" email to all active subscribers, but only once
    per publish cycle (guarded by News.notification_sent).
    """
    if not article.published or article.notification_sent:
        return
    subscribers = Subscriber.query.filter_by(subscribed=True).all()
    for subscriber in subscribers:
        send_new_news_notification(subscriber, article)
    article.notification_sent = True
    db.session.commit()


# ------------------------------------------------------------ PRODUCTS ----

@admin_bp.route("/products")
@login_required
def products_index():
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template("admin/products_list.html", products=products)


@admin_bp.route("/products/new", methods=["GET", "POST"])
@login_required
def products_new():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        description = request.form.get("description") or ""
        short_description = (request.form.get("short_description") or "").strip()
        price_raw = (request.form.get("price") or "").strip()
        category = (request.form.get("category") or "").strip()
        stock_status = request.form.get("stock_status") or "in_stock"
        featured = request.form.get("featured") == "on"
        publish = request.form.get("published") == "on"
        notify = request.form.get("notify_on_publish") == "on"

        if not name or not description:
            flash("Name and description are required.", "error")
            return render_template("admin/product_form.html", product=None, form=request.form)
        if stock_status not in {"in_stock", "out_of_stock"}:
            flash("Choose a valid product availability status.", "error")
            return render_template("admin/product_form.html", product=None, form=request.form)

        price = None
        if price_raw:
            try:
                price = float(price_raw)
            except ValueError:
                flash("Price must be a number.", "error")
                return render_template("admin/product_form.html", product=None, form=request.form)

        try:
            image_path = save_uploaded_image(
                request.files.get("image"),
                "products",
                max_size_bytes=current_app.config["MAX_UPLOAD_MB"] * 1024 * 1024,
            )
        except ValueError as e:
            flash(str(e), "error")
            return render_template("admin/product_form.html", product=None, form=request.form)

        product = Product(
            name=name,
            slug=make_unique_slug(name, Product),
            description=description,
            short_description=short_description,
            price=price,
            category=category or None,
            stock_status=stock_status,
            image=image_path,
            featured=featured,
            published=publish,
            notify_on_publish=notify,
        )
        if publish:
            product.published_at = datetime.now(timezone.utc)

        db.session.add(product)
        db.session.commit()

        _maybe_notify_subscribers_of_product(product)

        flash("Product created.", "success")
        return redirect(url_for("admin.products_index"))

    return render_template("admin/product_form.html", product=None, form={})


@admin_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def products_edit(product_id):
    product = Product.query.get_or_404(product_id)

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        description = request.form.get("description") or ""
        short_description = (request.form.get("short_description") or "").strip()
        price_raw = (request.form.get("price") or "").strip()
        category = (request.form.get("category") or "").strip()
        stock_status = request.form.get("stock_status") or "in_stock"
        featured = request.form.get("featured") == "on"
        publish = request.form.get("published") == "on"
        notify = request.form.get("notify_on_publish") == "on"

        if not name or not description:
            flash("Name and description are required.", "error")
            return render_template("admin/product_form.html", product=product, form=request.form)
        if stock_status not in {"in_stock", "out_of_stock"}:
            flash("Choose a valid product availability status.", "error")
            return render_template("admin/product_form.html", product=product, form=request.form)

        price = product.price
        if price_raw:
            try:
                price = float(price_raw)
            except ValueError:
                flash("Price must be a number.", "error")
                return render_template("admin/product_form.html", product=product, form=request.form)
        else:
            price = None

        try:
            image_path = save_uploaded_image(
                request.files.get("image"),
                "products",
                max_size_bytes=current_app.config["MAX_UPLOAD_MB"] * 1024 * 1024,
            )
        except ValueError as e:
            flash(str(e), "error")
            return render_template("admin/product_form.html", product=product, form=request.form)

        was_published = product.published

        if name != product.name:
            product.slug = make_unique_slug(name, Product, exclude_id=product.id)
        product.name = name
        product.description = description
        product.short_description = short_description
        product.price = price
        product.category = category or None
        product.stock_status = stock_status
        product.featured = featured
        product.notify_on_publish = notify
        if image_path:
            product.image = image_path

        if publish and not was_published:
            product.published_at = datetime.now(timezone.utc)
            product.notification_sent = False
        if not publish and was_published:
            product.notification_sent = False

        product.published = publish
        db.session.commit()

        if publish and not was_published:
            _maybe_notify_subscribers_of_product(product)

        flash("Product updated.", "success")
        return redirect(url_for("admin.products_index"))

    return render_template("admin/product_form.html", product=product, form=None)


@admin_bp.route("/products/<int:product_id>/delete", methods=["POST"])
@login_required
def products_delete(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash("Product deleted.", "success")
    return redirect(url_for("admin.products_index"))


# ------------------------------------------------------ PRODUCT VIDEOS ----

@admin_bp.route("/videos")
@login_required
def videos_index():
    videos = ProductVideo.query.order_by(ProductVideo.created_at.desc(), ProductVideo.id.desc()).all()
    return render_template("admin/videos_list.html", videos=videos)


@admin_bp.route("/videos/add", methods=["GET", "POST"])
@admin_bp.route("/videos/new", methods=["GET", "POST"])
@login_required
def videos_new():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        video_upload = request.files.get("video")

        if not title or len(title) > 200 or not description:
            flash("Enter a title (up to 200 characters) and a short description.", "error")
            return render_template("admin/video_form.html", video=None, form=request.form)
        if not video_upload or not video_upload.filename:
            flash("Choose an MP4 or WEBM video to upload.", "error")
            return render_template("admin/video_form.html", video=None, form=request.form)

        saved_paths = []
        try:
            thumbnail_path = save_uploaded_image(
                request.files.get("thumbnail"),
                "video-thumbnails",
                max_size_bytes=current_app.config["MAX_UPLOAD_MB"] * 1024 * 1024,
            )
            if thumbnail_path:
                saved_paths.append(thumbnail_path)
            video_path = save_uploaded_video(video_upload)
            saved_paths.append(video_path)
        except ValueError as error:
            _remove_video_uploads(saved_paths)
            flash(str(error), "error")
            return render_template("admin/video_form.html", video=None, form=request.form)
        except OSError:
            _remove_video_uploads(saved_paths)
            current_app.logger.exception("Could not store uploaded product video media.")
            flash("The upload could not be stored. Check available storage and try again.", "error")
            return render_template("admin/video_form.html", video=None, form=request.form)

        product_video = ProductVideo(
            title=title,
            description=description,
            video_path=video_path,
            thumbnail_path=thumbnail_path,
        )
        db.session.add(product_video)
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            _remove_video_uploads(saved_paths)
            current_app.logger.exception("Could not save product video record.")
            flash("The video could not be saved. Please try again.", "error")
            return render_template("admin/video_form.html", video=None, form=request.form)

        flash("Product video uploaded.", "success")
        return redirect(url_for("admin.videos_index"))

    return render_template("admin/video_form.html", video=None, form={})


def _video_staging_directory(upload_id):
    try:
        normalized_id = str(uuid.UUID(upload_id))
    except (ValueError, AttributeError, TypeError):
        return None
    return os.path.join(current_app.config["UPLOAD_FOLDER"], ".video-staging", normalized_id)


@admin_bp.route("/videos/upload-chunk", methods=["POST"])
@login_required
def videos_upload_chunk():
    upload_id = request.form.get("upload_id", "")
    staging_dir = _video_staging_directory(upload_id)
    if staging_dir is None:
        return jsonify(success=False, message="Invalid upload session."), 400

    try:
        chunk_index = int(request.form.get("chunk_index", ""))
    except ValueError:
        return jsonify(success=False, message="Invalid video chunk index."), 400
    chunk_size = current_app.config["VIDEO_UPLOAD_CHUNK_MB"] * 1024 * 1024
    max_size = current_app.config["MAX_VIDEO_UPLOAD_MB"] * 1024 * 1024
    max_chunks = (max_size + chunk_size - 1) // chunk_size
    if chunk_index < 0 or chunk_index >= max_chunks:
        return jsonify(success=False, message="Video upload exceeds the configured size limit."), 413

    chunk = request.files.get("chunk")
    if not chunk or not chunk.filename:
        return jsonify(success=False, message="The video upload chunk is missing."), 400

    os.makedirs(staging_dir, exist_ok=True)
    chunk_path = os.path.join(staging_dir, f"{chunk_index:08d}.part")
    chunk.stream.seek(0, os.SEEK_END)
    chunk_length = chunk.stream.tell()
    chunk.stream.seek(0)
    existing_size = sum(
        os.path.getsize(os.path.join(staging_dir, name))
        for name in os.listdir(staging_dir)
        if name.endswith(".part") and name != os.path.basename(chunk_path)
    )
    if chunk_length == 0:
        return jsonify(success=False, message="The video upload chunk is empty."), 400
    if chunk_length > chunk_size or existing_size + chunk_length > max_size:
        return jsonify(success=False, message=f"Video exceeds the {current_app.config['MAX_VIDEO_UPLOAD_MB']} MB upload limit."), 413

    try:
        chunk.save(chunk_path)
    except OSError:
        current_app.logger.exception("Could not store video upload chunk.")
        return jsonify(success=False, message="The video chunk could not be stored. Check available storage."), 500
    return jsonify(success=True, chunk_index=chunk_index)


@admin_bp.route("/videos/upload-complete", methods=["POST"])
@login_required
def videos_upload_complete():
    payload = request.form
    upload_id = payload.get("upload_id", "")
    original_filename = payload.get("filename", "")
    video_id = payload.get("video_id", type=int)
    staging_dir = _video_staging_directory(upload_id)
    if staging_dir is None:
        return jsonify(success=False, message="Invalid upload session."), 400
    if not isinstance(original_filename, str) or not original_filename or len(original_filename) > 255:
        return jsonify(success=False, message="Invalid video filename."), 400

    title = (payload.get("title") or "").strip()
    description = (payload.get("description") or "").strip()
    if not title or len(title) > 200 or not description:
        return jsonify(success=False, message="Enter a title (up to 200 characters) and a short description."), 400
    product_video = ProductVideo.query.get(video_id) if video_id is not None else None
    if video_id is not None and product_video is None:
        return jsonify(success=False, message="The product video to update was not found."), 404

    try:
        chunk_count = int(payload.get("chunk_count", 0))
    except (TypeError, ValueError):
        return jsonify(success=False, message="Invalid video upload details."), 400
    chunk_size = current_app.config["VIDEO_UPLOAD_CHUNK_MB"] * 1024 * 1024
    max_size = current_app.config["MAX_VIDEO_UPLOAD_MB"] * 1024 * 1024
    if chunk_count < 1 or chunk_count > (max_size + chunk_size - 1) // chunk_size:
        return jsonify(success=False, message=f"Video exceeds the {current_app.config['MAX_VIDEO_UPLOAD_MB']} MB upload limit."), 413

    assembled_path = os.path.join(staging_dir, "assembled-upload")
    total_size = 0
    saved_paths = []
    previous_video_path = product_video.video_path if product_video else None
    previous_thumbnail_path = product_video.thumbnail_path if product_video else None
    try:
        with open(assembled_path, "wb") as assembled:
            for index in range(chunk_count):
                chunk_path = os.path.join(staging_dir, f"{index:08d}.part")
                if not os.path.isfile(chunk_path):
                    return jsonify(success=False, message=f"Video upload is incomplete (missing chunk {index + 1})."), 400
                chunk_length = os.path.getsize(chunk_path)
                if chunk_length > chunk_size or total_size + chunk_length > max_size:
                    return jsonify(success=False, message=f"Video exceeds the {current_app.config['MAX_VIDEO_UPLOAD_MB']} MB upload limit."), 413
                total_size += chunk_length
                with open(chunk_path, "rb") as part:
                    shutil.copyfileobj(part, assembled)
        with open(assembled_path, "rb") as stream:
            video_path = save_uploaded_video(FileStorage(stream=stream, filename=original_filename))
        saved_paths.append(video_path)
        thumbnail_path = save_uploaded_image(
            request.files.get("thumbnail"),
            "video-thumbnails",
            max_size_bytes=current_app.config["MAX_UPLOAD_MB"] * 1024 * 1024,
        )
        if thumbnail_path:
            saved_paths.append(thumbnail_path)
        if product_video is None:
            product_video = ProductVideo(
                title=title,
                description=description,
                video_path=video_path,
                thumbnail_path=thumbnail_path,
            )
            db.session.add(product_video)
        else:
            product_video.title = title
            product_video.description = description
            product_video.video_path = video_path
            if thumbnail_path:
                product_video.thumbnail_path = thumbnail_path
            elif payload.get("remove_thumbnail") == "on":
                product_video.thumbnail_path = None
        db.session.commit()
    except ValueError as error:
        db.session.rollback()
        _remove_video_uploads(saved_paths)
        current_app.logger.info("Rejected chunked product video upload: %s", error)
        return jsonify(success=False, message=str(error)), 400
    except OSError:
        db.session.rollback()
        _remove_video_uploads(saved_paths)
        current_app.logger.exception("Could not store chunked product video upload.")
        return jsonify(success=False, message="The video could not be stored. Check available storage and try again."), 500
    except SQLAlchemyError:
        db.session.rollback()
        _remove_video_uploads(saved_paths)
        current_app.logger.exception("Could not save chunked product video record.")
        return jsonify(success=False, message="The video could not be saved. Please try again."), 500
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)

    if previous_video_path and previous_video_path != product_video.video_path:
        _remove_video_upload(previous_video_path)
    if previous_thumbnail_path and previous_thumbnail_path != product_video.thumbnail_path:
        _remove_video_upload(previous_thumbnail_path)
    success_message = "Product video updated." if video_id is not None else "Product video uploaded."
    flash(success_message, "success")
    return jsonify(success=True, message=success_message, redirect_url=url_for("admin.videos_index"))


@admin_bp.route("/videos/upload-abort", methods=["POST"])
@login_required
def videos_upload_abort():
    staging_dir = _video_staging_directory(request.form.get("upload_id", ""))
    if staging_dir is None:
        return jsonify(success=False, message="Invalid upload session."), 400
    try:
        shutil.rmtree(staging_dir, ignore_errors=False)
    except FileNotFoundError:
        pass
    except OSError:
        current_app.logger.exception("Could not clean up an abandoned video upload.")
        return jsonify(success=False, message="Could not clean up the incomplete video upload."), 500
    return jsonify(success=True)


@admin_bp.route("/videos/<int:video_id>/edit", methods=["GET", "POST"])
@login_required
def videos_edit(video_id):
    video = ProductVideo.query.get_or_404(video_id)
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        video_upload = request.files.get("video")
        thumbnail_upload = request.files.get("thumbnail")

        if not title or len(title) > 200 or not description:
            flash("Enter a title (up to 200 characters) and a short description.", "error")
            return render_template("admin/video_form.html", video=video, form=request.form)

        saved_paths = []
        try:
            thumbnail_path = save_uploaded_image(
                thumbnail_upload,
                "video-thumbnails",
                max_size_bytes=current_app.config["MAX_UPLOAD_MB"] * 1024 * 1024,
            )
            if thumbnail_path:
                saved_paths.append(thumbnail_path)
            video_path = save_uploaded_video(video_upload)
            if video_path:
                saved_paths.append(video_path)
        except ValueError as error:
            _remove_video_uploads(saved_paths)
            flash(str(error), "error")
            return render_template("admin/video_form.html", video=video, form=request.form)
        except OSError:
            _remove_video_uploads(saved_paths)
            current_app.logger.exception("Could not store updated product video media.")
            flash("The upload could not be stored. Check available storage and try again.", "error")
            return render_template("admin/video_form.html", video=video, form=request.form)

        previous_video_path = video.video_path
        previous_thumbnail_path = video.thumbnail_path
        video.title = title
        video.description = description
        if video_path:
            video.video_path = video_path
        if thumbnail_path:
            video.thumbnail_path = thumbnail_path
        elif request.form.get("remove_thumbnail") == "on":
            video.thumbnail_path = None

        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            _remove_video_uploads(saved_paths)
            current_app.logger.exception("Could not update product video record %s.", video_id)
            flash("The video details could not be saved. Please try again.", "error")
            return render_template(
                "admin/video_form.html",
                video=ProductVideo.query.get_or_404(video_id),
                form=request.form,
            )

        cleanup_ok = True
        if video_path and not _remove_video_upload(previous_video_path):
            cleanup_ok = False
        if video.thumbnail_path != previous_thumbnail_path and previous_thumbnail_path:
            if not _remove_video_upload(previous_thumbnail_path):
                cleanup_ok = False
        if cleanup_ok:
            flash("Product video updated.", "success")
        else:
            flash("Product video updated, but an old media file could not be removed.", "error")
        return redirect(url_for("admin.videos_index"))

    return render_template("admin/video_form.html", video=video, form=None)


@admin_bp.route("/videos/<int:video_id>/delete", methods=["POST"])
@login_required
def videos_delete(video_id):
    video = ProductVideo.query.get_or_404(video_id)
    media_paths = [video.video_path, video.thumbnail_path]
    db.session.delete(video)
    db.session.commit()
    if _remove_video_uploads(media_paths):
        flash("Product video deleted.", "success")
    else:
        flash("Product video deleted, but one or more media files could not be removed.", "error")
    return redirect(url_for("admin.videos_index"))


def _remove_video_upload(relative_path):
    return delete_uploaded_file(relative_path)


def _remove_video_uploads(relative_paths):
    cleanup_ok = True
    for relative_path in relative_paths:
        if not _remove_video_upload(relative_path):
            cleanup_ok = False
    return cleanup_ok


def _maybe_notify_subscribers_of_product(product: Product) -> None:
    """Products only email subscribers if the admin explicitly enabled it."""
    if not product.published or not product.notify_on_publish or product.notification_sent:
        return
    from services.email_service import send_email, _company_name, _site_url  # local import to avoid cycle

    subscribers = Subscriber.query.filter_by(subscribed=True).all()
    product_link = f"{_site_url()}/products/{product.slug}"
    for subscriber in subscribers:
        html = (
            f"<p>New product from {_company_name()}: <strong>{product.name}</strong></p>"
            f"<p>{product.short_description or ''}</p>"
            f"<p><a href='{product_link}'>View product</a></p>"
        )
        send_email(subscriber.email, f"New Product from {_company_name()}: {product.name}", html)
    product.notification_sent = True
    db.session.commit()


# --------------------------------------------------------- SUBSCRIBERS ----

@admin_bp.route("/subscribers")
@login_required
def subscribers_index():
    search = (request.args.get("q") or "").strip()
    query = Subscriber.query
    if search:
        query = query.filter(Subscriber.email.ilike(f"%{search}%"))
    subscribers = query.order_by(Subscriber.created_at.desc()).all()
    return render_template("admin/subscribers_list.html", subscribers=subscribers, search=search)


@admin_bp.route("/subscribers/<int:subscriber_id>/deactivate", methods=["POST"])
@login_required
def subscriber_deactivate(subscriber_id):
    subscriber = Subscriber.query.get_or_404(subscriber_id)
    subscriber.subscribed = False
    subscriber.unsubscribed_at = datetime.now(timezone.utc)
    db.session.commit()
    flash("Subscriber deactivated.", "success")
    return redirect(url_for("admin.subscribers_index"))


@admin_bp.route("/subscribers/<int:subscriber_id>/delete", methods=["POST"])
@login_required
def subscriber_delete(subscriber_id):
    subscriber = Subscriber.query.get_or_404(subscriber_id)
    db.session.delete(subscriber)
    db.session.commit()
    flash("Subscriber removed.", "success")
    return redirect(url_for("admin.subscribers_index"))


# ------------------------------------------------------------ MESSAGES ----

def _attempt_admin_message_email(message, activity):
    senders = {
        ContactMessageActivity.TYPE_BUSINESS_NOTIFICATION:
            lambda: send_new_contact_notification(message),
        ContactMessageActivity.TYPE_SUBMISSION_CONFIRMATION:
            lambda: send_contact_submission_confirmation(message),
        ContactMessageActivity.TYPE_ADMIN_REPLY:
            lambda: send_contact_admin_reply(
                message,
                activity.body or "",
                recipient_email=activity.recipient_email,
                subject=activity.email_subject,
            ),
        ContactMessageActivity.TYPE_REQUEST_ACCEPTED:
            lambda: send_contact_approval_notification(message),
        ContactMessageActivity.TYPE_REQUEST_REJECTED:
            lambda: send_contact_declined_notification(message),
    }
    sender = senders.get(activity.event_type)
    if sender is None:
        return False
    accepted = attempt_contact_email(activity, sender)
    if accepted:
        if activity.event_type == ContactMessageActivity.TYPE_BUSINESS_NOTIFICATION:
            message.notification_email_submitted = True
        elif activity.event_type == ContactMessageActivity.TYPE_SUBMISSION_CONFIRMATION:
            message.confirmation_email_submitted = True
        elif activity.event_type in {
            ContactMessageActivity.TYPE_REQUEST_ACCEPTED,
            ContactMessageActivity.TYPE_REQUEST_REJECTED,
        }:
            message.decision_email_sent = True
        try:
            db.session.commit()
        except SQLAlchemyError as exc:
            db.session.rollback()
            current_app.logger.error(
                "Could not update contact message email flags (%s)", type(exc).__name__
            )
            return False
    return accepted


def _update_internal_note(message, raw_note):
    note = (raw_note or "").strip()
    if not note or note == (message.internal_note or ""):
        return
    message.internal_note = note
    db.session.add(
        ContactMessageActivity(
            contact_message=message,
            event_type=ContactMessageActivity.TYPE_NOTE_UPDATED,
            body=note,
            email_status=ContactMessageActivity.EMAIL_NOT_APPLICABLE,
            admin_username=get_current_admin().username,
        )
    )


@admin_bp.route("/messages")
@login_required
def messages_index():
    folder = (request.args.get("folder") or "").lower()
    if folder not in {"all", "inbox", "archive", "trash"}:
        folder = "archive" if request.args.get("archived") == "1" else "inbox"
    tab = (request.args.get("tab") or "all").lower()
    if tab not in {
        "all", "new", "read", "replied", "pending", "approved", "declined",
    }:
        tab = "all"
    status_filter = (request.args.get("status") or "ALL").upper()
    if status_filter == "APPROVED":
        status_filter = ContactMessage.STATUS_ACCEPTED
    elif status_filter == "DECLINED":
        status_filter = ContactMessage.STATUS_REJECTED
    read_filter = (request.args.get("read") or "all").lower()
    if read_filter not in {"all", "read", "unread"}:
        read_filter = "all"
    if status_filter not in {
        "ALL", ContactMessage.STATUS_PENDING, ContactMessage.STATUS_IN_PROGRESS,
        ContactMessage.STATUS_ACCEPTED, ContactMessage.STATUS_REJECTED,
    }:
        status_filter = "ALL"
    priority_filter = (request.args.get("priority") or "all").upper()
    if priority_filter not in {"ALL", "LOW", "NORMAL", "HIGH", "URGENT"}:
        priority_filter = "ALL"
    search = (request.args.get("q") or "").strip()[:200]
    sort_order = (request.args.get("sort") or "newest").lower()
    query = ContactMessage.query
    if folder == "trash":
        query = query.filter(ContactMessage.deleted_at.is_not(None))
    else:
        query = query.filter(ContactMessage.deleted_at.is_(None))
        if folder == "archive":
            query = query.filter(ContactMessage.archived_at.is_not(None))
        elif folder == "inbox":
            query = query.filter(ContactMessage.archived_at.is_(None))

    reply_exists = ContactMessage.activities.any(
        and_(
            ContactMessageActivity.event_type == ContactMessageActivity.TYPE_ADMIN_REPLY,
            ContactMessageActivity.email_status == ContactMessageActivity.EMAIL_ACCEPTED,
        )
    )
    if folder != "trash":
        tab_filters = {
            "new": ContactMessage.is_read.is_(False),
            "read": ContactMessage.is_read.is_(True),
            "replied": reply_exists,
            "pending": ContactMessage.status == ContactMessage.STATUS_PENDING,
            "approved": ContactMessage.status == ContactMessage.STATUS_ACCEPTED,
            "declined": ContactMessage.status == ContactMessage.STATUS_REJECTED,
        }
        if tab in tab_filters:
            query = query.filter(tab_filters[tab])

    if tab == "all" and status_filter in (
        ContactMessage.STATUS_PENDING,
        ContactMessage.STATUS_IN_PROGRESS,
        ContactMessage.STATUS_ACCEPTED,
        ContactMessage.STATUS_REJECTED,
    ):
        query = query.filter_by(status=status_filter)
    if tab == "all" and read_filter == "read":
        query = query.filter_by(is_read=True)
    elif tab == "all" and read_filter == "unread":
        query = query.filter_by(is_read=False)
    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                ContactMessage.name.ilike(term),
                ContactMessage.email.ilike(term),
                ContactMessage.subject.ilike(term),
                ContactMessage.message.ilike(term),
            )
        )
    if priority_filter != "ALL":
        query = query.filter_by(priority=priority_filter)

    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    parsed_from = None
    parsed_to = None
    try:
        parsed_from = date.fromisoformat(date_from) if date_from else None
        parsed_to = date.fromisoformat(date_to) if date_to else None
    except ValueError:
        flash("Enter valid dates for the message filter.", "error")
        date_from = ""
        date_to = ""
        parsed_from = None
        parsed_to = None
    if parsed_from and parsed_to and parsed_from > parsed_to:
        flash("The start date must be on or before the end date.", "error")
        parsed_from = parsed_to = None
        date_from = date_to = ""
    if parsed_from:
        query = query.filter(
            ContactMessage.created_at >= datetime.combine(parsed_from, time.min)
        )
    if parsed_to:
        query = query.filter(
            ContactMessage.created_at < datetime.combine(parsed_to + timedelta(days=1), time.min)
        )
    if sort_order == "oldest":
        order = ContactMessage.created_at.asc()
    elif sort_order == "priority":
        order = case(
            (ContactMessage.priority == "URGENT", 0),
            (ContactMessage.priority == "HIGH", 1),
            (ContactMessage.priority == "NORMAL", 2),
            else_=3,
        )
    else:
        sort_order = "newest"
        order = ContactMessage.created_at.desc()
    page_number = request.args.get("page", 1, type=int)
    pagination = query.order_by(order, ContactMessage.id.desc()).paginate(
        page=max(page_number or 1, 1), per_page=20, error_out=False
    )
    filters = {
        "status": status_filter,
        "read": read_filter,
        "archived": folder == "archive",
        "q": search,
        "sort": sort_order,
        "date_from": date_from,
        "date_to": date_to,
        "priority": priority_filter,
        "folder": folder,
        "tab": tab,
    }
    stats_query = ContactMessage.query.filter(ContactMessage.deleted_at.is_(None))
    stats = {
        "total": stats_query.count(),
        "new": stats_query.filter(ContactMessage.is_read.is_(False)).count(),
        "read": stats_query.filter(ContactMessage.is_read.is_(True)).count(),
        "replied": stats_query.filter(reply_exists).count(),
        "approved": stats_query.filter_by(status=ContactMessage.STATUS_ACCEPTED).count(),
        "declined": stats_query.filter_by(status=ContactMessage.STATUS_REJECTED).count(),
        "pending": stats_query.filter_by(status=ContactMessage.STATUS_PENDING).count(),
        "archived": stats_query.filter(ContactMessage.archived_at.is_not(None)).count(),
        "trash": ContactMessage.query.filter(ContactMessage.deleted_at.is_not(None)).count(),
    }
    page_message_ids = [message.id for message in pagination.items]
    replied_ids = set()
    if page_message_ids:
        replied_ids = {
            message_id for (message_id,) in db.session.query(
                ContactMessageActivity.contact_message_id
            ).filter(
                ContactMessageActivity.contact_message_id.in_(page_message_ids),
                ContactMessageActivity.event_type == ContactMessageActivity.TYPE_ADMIN_REPLY,
                ContactMessageActivity.email_status == ContactMessageActivity.EMAIL_ACCEPTED,
            ).distinct()
        }
    return render_template(
        "admin/messages_list.html",
        messages=pagination.items,
        pagination=pagination,
        status_filter=status_filter,
        filters=filters,
        folder=folder,
        tab=tab,
        stats=stats,
        replied_ids=replied_ids,
    )


@admin_bp.route("/messages/<int:message_id>")
@login_required
def message_detail(message_id):
    message = ContactMessage.query.get_or_404(message_id)
    if not message.is_read:
        message.is_read = True
        db.session.add(
            ContactMessageActivity(
                contact_message=message,
                event_type=ContactMessageActivity.TYPE_STATUS_CHANGED,
                body="Marked as read",
                email_status=ContactMessageActivity.EMAIL_NOT_APPLICABLE,
                admin_username=get_current_admin().username,
            )
        )
        db.session.commit()
    return render_template(
        "admin/message_detail.html",
        message=message,
        activities=message.activities,
        reply_token=str(uuid.uuid4()),
        accept_token=str(uuid.uuid4()),
        reject_token=str(uuid.uuid4()),
    )


@admin_bp.route("/messages/<int:message_id>/read", methods=["POST"])
@login_required
def message_set_read(message_id):
    message = ContactMessage.query.get_or_404(message_id)
    is_read = request.form.get("is_read") == "1"
    if message.is_read != is_read:
        message.is_read = is_read
        db.session.add(
            ContactMessageActivity(
                contact_message=message,
                event_type=ContactMessageActivity.TYPE_STATUS_CHANGED,
                body="Marked as read" if is_read else "Marked as unread",
                email_status=ContactMessageActivity.EMAIL_NOT_APPLICABLE,
                admin_username=get_current_admin().username,
            )
        )
    db.session.commit()
    flash("Message marked as read." if message.is_read else "Message marked as unread.", "success")
    if not message.is_read:
        return redirect(url_for("admin.messages_index", archived="1" if message.archived_at else None))
    return redirect(url_for("admin.message_detail", message_id=message.id))


@admin_bp.route("/messages/<int:message_id>/status", methods=["POST"])
@login_required
def message_set_work_status(message_id):
    message = ContactMessage.query.get_or_404(message_id)
    new_status = (request.form.get("status") or "").upper()
    allowed_statuses = {
        ContactMessage.STATUS_PENDING,
        ContactMessage.STATUS_IN_PROGRESS,
    }
    if new_status not in allowed_statuses:
        flash("Select a valid message workflow status.", "error")
        return redirect(url_for("admin.message_detail", message_id=message.id))
    if message.status not in allowed_statuses:
        flash("A decided request cannot be moved back into the active workflow.", "error")
        return redirect(url_for("admin.message_detail", message_id=message.id))
    if message.status != new_status:
        previous_status = message.status
        message.status = new_status
        db.session.add(
            ContactMessageActivity(
                contact_message=message,
                event_type=ContactMessageActivity.TYPE_STATUS_CHANGED,
                body=f"Request status changed from {previous_status.replace('_', ' ').title()} to {new_status.replace('_', ' ').title()}",
                email_status=ContactMessageActivity.EMAIL_NOT_APPLICABLE,
                admin_username=get_current_admin().username,
            )
        )
        db.session.commit()
    flash("Message workflow status updated.", "success")
    return redirect(url_for("admin.message_detail", message_id=message.id))


@admin_bp.route("/messages/<int:message_id>/archive", methods=["POST"])
@login_required
def message_archive(message_id):
    message = ContactMessage.query.get_or_404(message_id)
    archive = request.form.get("archived") == "1"
    if message.deleted_at:
        flash("Restore this message from Trash before archiving it.", "error")
        return redirect(url_for("admin.message_detail", message_id=message.id))
    if archive != (message.archived_at is not None):
        message.archived_at = datetime.now(timezone.utc) if archive else None
        db.session.add(
            ContactMessageActivity(
                contact_message=message,
                event_type=(
                    ContactMessageActivity.TYPE_ARCHIVED if archive
                    else ContactMessageActivity.TYPE_RESTORED
                ),
                body="Message archived" if archive else "Message restored to inbox",
                email_status=ContactMessageActivity.EMAIL_NOT_APPLICABLE,
                admin_username=get_current_admin().username,
            )
        )
    db.session.commit()
    flash("Message archived." if archive else "Message restored to the inbox.", "success")
    return redirect(
        url_for("admin.messages_index", archived="1") if archive
        else url_for("admin.messages_index")
    )


@admin_bp.route("/messages/<int:message_id>/trash", methods=["POST"])
@login_required
def message_trash(message_id):
    message = ContactMessage.query.get_or_404(message_id)
    if message.deleted_at is None:
        message.deleted_at = datetime.now(timezone.utc)
        db.session.add(
            ContactMessageActivity(
                contact_message=message,
                event_type=ContactMessageActivity.TYPE_TRASHED,
                body="Message moved to Trash",
                email_status=ContactMessageActivity.EMAIL_NOT_APPLICABLE,
                admin_username=get_current_admin().username,
            )
        )
        db.session.commit()
        flash("Message moved to Trash. You can restore it before permanent deletion.", "success")
    return redirect(url_for("admin.messages_index", folder="trash"))


@admin_bp.route("/messages/<int:message_id>/restore", methods=["POST"])
@login_required
def message_restore(message_id):
    message = ContactMessage.query.get_or_404(message_id)
    if message.deleted_at is None:
        flash("This message is not in Trash.", "error")
    else:
        message.deleted_at = None
        db.session.add(
            ContactMessageActivity(
                contact_message=message,
                event_type=ContactMessageActivity.TYPE_RESTORED,
                body="Message restored from Trash",
                email_status=ContactMessageActivity.EMAIL_NOT_APPLICABLE,
                admin_username=get_current_admin().username,
            )
        )
        db.session.commit()
        flash("Message restored.", "success")
    return redirect(url_for("admin.messages_index", folder="trash"))


@admin_bp.route("/messages/<int:message_id>/delete-permanently", methods=["POST"])
@login_required
def message_delete_permanently(message_id):
    message = ContactMessage.query.get_or_404(message_id)
    if message.deleted_at is None:
        flash("Move the message to Trash before permanently deleting it.", "error")
        return redirect(url_for("admin.message_detail", message_id=message.id))
    db.session.delete(message)
    db.session.commit()
    flash("Message permanently deleted.", "success")
    return redirect(url_for("admin.messages_index", folder="trash"))


@admin_bp.route("/messages/bulk", methods=["POST"])
@login_required
def messages_bulk_action():
    raw_ids = request.form.getlist("message_ids")
    action = (request.form.get("action") or "").strip().lower()
    folder = (request.form.get("folder") or "inbox").lower()
    tab = (request.form.get("tab") or "all").lower()
    if folder not in {"all", "inbox", "archive", "trash"}:
        folder = "inbox"
    if tab not in {"all", "new", "read", "replied", "pending", "approved", "declined"}:
        tab = "all"
    list_url = url_for("admin.messages_index", folder=folder, tab=tab)
    if not raw_ids or len(raw_ids) > 100:
        flash("Select between 1 and 100 messages for a bulk action.", "error")
        return redirect(list_url)
    try:
        message_ids = {int(value) for value in raw_ids}
    except (TypeError, ValueError):
        flash("The selected message list is invalid.", "error")
        return redirect(list_url)
    if len(message_ids) != len(raw_ids):
        flash("The selected message list contains duplicates.", "error")
        return redirect(list_url)

    selected = ContactMessage.query.filter(ContactMessage.id.in_(message_ids)).all()
    if len(selected) != len(message_ids):
        flash("One or more selected messages could not be found. No changes were made.", "error")
        return redirect(list_url)

    now = datetime.now(timezone.utc)
    admin_name = get_current_admin().username
    activity_messages = []
    if action == "archive" and all(m.deleted_at is None for m in selected):
        for message in selected:
            if message.archived_at is None:
                message.archived_at = now
                activity_messages.append((message, ContactMessageActivity.TYPE_ARCHIVED, "Bulk archived"))
    elif action == "restore_archive" and all(
        m.deleted_at is None and m.archived_at is not None for m in selected
    ):
        for message in selected:
            message.archived_at = None
            activity_messages.append((message, ContactMessageActivity.TYPE_RESTORED, "Restored to inbox"))
    elif action == "trash" and all(m.deleted_at is None for m in selected):
        for message in selected:
            message.deleted_at = now
            activity_messages.append((message, ContactMessageActivity.TYPE_TRASHED, "Bulk moved to Trash"))
    elif action == "restore_trash" and all(m.deleted_at is not None for m in selected):
        for message in selected:
            message.deleted_at = None
            activity_messages.append((message, ContactMessageActivity.TYPE_RESTORED, "Restored from Trash"))
    elif action == "delete_permanently" and all(m.deleted_at is not None for m in selected):
        for message in selected:
            db.session.delete(message)
    elif action in {"read", "unread"} and all(m.deleted_at is None for m in selected):
        value = action == "read"
        for message in selected:
            if message.is_read != value:
                message.is_read = value
                activity_messages.append(
                    (message, ContactMessageActivity.TYPE_STATUS_CHANGED,
                     "Marked as read" if value else "Marked as unread")
                )
    elif action in {"approve", "decline"} and all(m.deleted_at is None for m in selected):
        new_status = (
            ContactMessage.STATUS_ACCEPTED if action == "approve"
            else ContactMessage.STATUS_REJECTED
        )
        for message in selected:
            if message.status != new_status:
                previous_status = message.status
                message.status = new_status
                message.reviewed_at = now
                activity_messages.append(
                    (
                        message,
                        ContactMessageActivity.TYPE_STATUS_CHANGED,
                        f"Bulk decision changed from {previous_status.replace('_', ' ').title()} "
                        f"to {new_status.replace('_', ' ').title()}; no email was sent",
                    )
                )
    else:
        flash("That action is not valid for the selected messages. No changes were made.", "error")
        return redirect(list_url)

    for message, event_type, body in activity_messages:
        db.session.add(
            ContactMessageActivity(
                contact_message=message,
                event_type=event_type,
                body=body,
                email_status=ContactMessageActivity.EMAIL_NOT_APPLICABLE,
                admin_username=admin_name,
            )
        )
    db.session.commit()
    if action == "delete_permanently":
        flash(f"Permanently deleted {len(selected)} message(s).", "success")
    elif action in {"approve", "decline"}:
        flash(f"Updated {len(selected)} message(s). No decision emails were sent.", "success")
    else:
        flash(f"Updated {len(selected)} message(s).", "success")
    return redirect(list_url)


@admin_bp.route("/messages/<int:message_id>/priority", methods=["POST"])
@login_required
def message_set_priority(message_id):
    message = ContactMessage.query.get_or_404(message_id)
    priority = (request.form.get("priority") or "").upper()
    if priority not in {"LOW", "NORMAL", "HIGH", "URGENT"}:
        flash("Choose a valid priority.", "error")
        return redirect(url_for("admin.message_detail", message_id=message.id))
    if message.priority != priority:
        previous = message.priority
        message.priority = priority
        db.session.add(
            ContactMessageActivity(
                contact_message=message,
                event_type=ContactMessageActivity.TYPE_PRIORITY_CHANGED,
                body=f"Priority changed from {previous.title()} to {priority.title()}",
                email_status=ContactMessageActivity.EMAIL_NOT_APPLICABLE,
                admin_username=get_current_admin().username,
            )
        )
        db.session.commit()
    flash("Message priority updated.", "success")
    return redirect(url_for("admin.message_detail", message_id=message.id))


@admin_bp.route("/messages/<int:message_id>/note", methods=["POST"])
@login_required
def message_save_internal_note(message_id):
    message = ContactMessage.query.get_or_404(message_id)
    note = (request.form.get("internal_note") or "").strip()
    if len(note) > 10000:
        flash("Internal notes must be 10,000 characters or fewer.", "error")
        return redirect(url_for("admin.message_detail", message_id=message.id))
    if note != (message.internal_note or ""):
        message.internal_note = note or None
        db.session.add(
            ContactMessageActivity(
                contact_message=message,
                event_type=ContactMessageActivity.TYPE_NOTE_UPDATED,
                body=note or "Internal note cleared",
                email_status=ContactMessageActivity.EMAIL_NOT_APPLICABLE,
                admin_username=get_current_admin().username,
            )
        )
        db.session.commit()
    flash("Internal note saved.", "success")
    return redirect(url_for("admin.message_detail", message_id=message.id))


@admin_bp.route("/messages/<int:message_id>/reply", methods=["POST"])
@login_required
def message_reply(message_id):
    message = ContactMessage.query.get_or_404(message_id)
    reply_text = (request.form.get("reply") or "").strip()
    recipient = (request.form.get("recipient_email") or message.email).strip()
    email_subject = (request.form.get("email_subject") or "").strip()
    token = (request.form.get("request_token") or "").strip()
    if not reply_text or len(reply_text) > 10000:
        flash("Reply text is required and must be 10,000 characters or fewer.", "error")
        return redirect(url_for("admin.message_detail", message_id=message.id))
    if len(email_subject) > 200 or "\r" in email_subject or "\n" in email_subject:
        flash("The email subject must be 200 characters or fewer and cannot contain line breaks.", "error")
        return redirect(url_for("admin.message_detail", message_id=message.id))
    try:
        recipient = validate_email(recipient, check_deliverability=False).normalized
    except (EmailNotValidError, TypeError):
        flash("Enter a valid reply recipient email address.", "error")
        return redirect(url_for("admin.message_detail", message_id=message.id))
    if not email_subject:
        flash("An email subject is required.", "error")
        return redirect(url_for("admin.message_detail", message_id=message.id))
    try:
        uuid.UUID(token)
    except (ValueError, AttributeError):
        flash("The reply form expired. Please try again.", "error")
        return redirect(url_for("admin.message_detail", message_id=message.id))

    activity = get_or_create_email_activity(
        message,
        ContactMessageActivity.TYPE_ADMIN_REPLY,
        body=reply_text,
        recipient_email=recipient,
        email_subject=email_subject,
        request_token=token,
        admin_username=get_current_admin().username,
    )
    if (
        activity.contact_message_id != message.id
        or activity.event_type != ContactMessageActivity.TYPE_ADMIN_REPLY
        or activity.body != reply_text
        or activity.recipient_email != recipient
        or activity.email_subject != email_subject
    ):
        flash("This reply request token has already been used.", "error")
        return redirect(url_for("admin.message_detail", message_id=message.id))
    if _attempt_admin_message_email(message, activity):
        flash("Reply accepted by the email service. Inbox delivery is not confirmed.", "success")
    else:
        flash("Reply was saved, but the email service did not accept it. Retry the saved reply below.", "error")
    return redirect(url_for("admin.message_detail", message_id=message.id))


@admin_bp.route("/messages/<int:message_id>/activities/<int:activity_id>/retry", methods=["POST"])
@login_required
def message_email_retry(message_id, activity_id):
    message = ContactMessage.query.get_or_404(message_id)
    activity = ContactMessageActivity.query.filter_by(
        id=activity_id,
        contact_message_id=message.id,
    ).first_or_404()
    if activity.email_status not in (
        ContactMessageActivity.EMAIL_FAILED,
        ContactMessageActivity.EMAIL_SENDING,
    ):
        flash("Only failed or interrupted email attempts can be retried.", "error")
    elif _attempt_admin_message_email(message, activity):
        flash("Email submission was accepted by the email service; delivery is not confirmed.", "success")
    else:
        flash("Email retry failed. The email service did not accept the message.", "error")
    return redirect(url_for("admin.message_detail", message_id=message.id))


@admin_bp.route("/messages/<int:message_id>/approve", methods=["POST"])
@login_required
def message_approve(message_id):
    message = ContactMessage.query.get_or_404(message_id)
    admin_note = (request.form.get("admin_note") or "").strip()
    internal_note = request.form.get("internal_note")
    token = (request.form.get("request_token") or "").strip()
    if len(admin_note) > 5000:
        flash("The optional message must be 5,000 characters or fewer.", "error")
        return redirect(url_for("admin.message_detail", message_id=message.id))
    if internal_note is not None and len(internal_note.strip()) > 10000:
        flash("Internal notes must be 10,000 characters or fewer.", "error")
        return redirect(url_for("admin.message_detail", message_id=message.id))
    _update_internal_note(message, internal_note)
    previous_status = message.status
    if not token:
        flash("The decision form expired. Please try again.", "error")
        return redirect(url_for("admin.message_detail", message_id=message.id))
    if token:
        try:
            uuid.UUID(token)
        except ValueError:
            flash("The decision form expired. Please try again.", "error")
            return redirect(url_for("admin.message_detail", message_id=message.id))
        existing = ContactMessageActivity.query.filter_by(request_token=token).first()
        if existing and (
            existing.contact_message_id != message.id
            or existing.event_type != ContactMessageActivity.TYPE_REQUEST_ACCEPTED
        ):
            flash("This decision form has already been used.", "error")
            return redirect(url_for("admin.message_detail", message_id=message.id))

    if message.status != ContactMessage.STATUS_ACCEPTED:
        message.status = ContactMessage.STATUS_ACCEPTED
        message.admin_note = admin_note or None
        message.reviewed_at = datetime.now(timezone.utc)
        db.session.add(
            ContactMessageActivity(
                contact_message=message,
                event_type=ContactMessageActivity.TYPE_STATUS_CHANGED,
                body=(
                    f"Request status changed from {previous_status.replace('_', ' ').title()} "
                    "to Accepted"
                ),
                email_status=ContactMessageActivity.EMAIL_NOT_APPLICABLE,
                admin_username=get_current_admin().username,
            )
        )
    activity = get_or_create_email_activity(
        message,
        ContactMessageActivity.TYPE_REQUEST_ACCEPTED,
        body=admin_note or None,
        request_token=token or None,
        admin_username=get_current_admin().username,
    )
    db.session.commit()
    if (
        activity.contact_message_id != message.id
        or activity.event_type != ContactMessageActivity.TYPE_REQUEST_ACCEPTED
    ):
        flash("This decision form has already been used.", "error")
    elif _attempt_admin_message_email(message, activity):
        flash("Request accepted and acceptance email submission was accepted by the email service.", "success")
    else:
        flash("Request accepted, but the email was not accepted. Retry it from the message history.", "error")
    return redirect(url_for("admin.message_detail", message_id=message.id))


@admin_bp.route("/messages/<int:message_id>/decline", methods=["POST"])
@login_required
def message_decline(message_id):
    message = ContactMessage.query.get_or_404(message_id)
    admin_note = (request.form.get("admin_note") or "").strip()
    internal_note = request.form.get("internal_note")
    token = (request.form.get("request_token") or "").strip()
    if len(admin_note) > 5000:
        flash("The optional explanation must be 5,000 characters or fewer.", "error")
        return redirect(url_for("admin.message_detail", message_id=message.id))
    if internal_note is not None and len(internal_note.strip()) > 10000:
        flash("Internal notes must be 10,000 characters or fewer.", "error")
        return redirect(url_for("admin.message_detail", message_id=message.id))
    _update_internal_note(message, internal_note)
    previous_status = message.status
    if not token:
        flash("The decision form expired. Please try again.", "error")
        return redirect(url_for("admin.message_detail", message_id=message.id))
    if token:
        try:
            uuid.UUID(token)
        except ValueError:
            flash("The decision form expired. Please try again.", "error")
            return redirect(url_for("admin.message_detail", message_id=message.id))
        existing = ContactMessageActivity.query.filter_by(request_token=token).first()
        if existing and (
            existing.contact_message_id != message.id
            or existing.event_type != ContactMessageActivity.TYPE_REQUEST_REJECTED
        ):
            flash("This decision form has already been used.", "error")
            return redirect(url_for("admin.message_detail", message_id=message.id))

    if message.status != ContactMessage.STATUS_REJECTED:
        message.status = ContactMessage.STATUS_REJECTED
        message.admin_note = admin_note or None
        message.reviewed_at = datetime.now(timezone.utc)
        db.session.add(
            ContactMessageActivity(
                contact_message=message,
                event_type=ContactMessageActivity.TYPE_STATUS_CHANGED,
                body=(
                    f"Request status changed from {previous_status.replace('_', ' ').title()} "
                    "to Declined"
                ),
                email_status=ContactMessageActivity.EMAIL_NOT_APPLICABLE,
                admin_username=get_current_admin().username,
            )
        )
    activity = get_or_create_email_activity(
        message,
        ContactMessageActivity.TYPE_REQUEST_REJECTED,
        body=admin_note or None,
        request_token=token or None,
        admin_username=get_current_admin().username,
    )
    db.session.commit()
    if (
        activity.contact_message_id != message.id
        or activity.event_type != ContactMessageActivity.TYPE_REQUEST_REJECTED
    ):
        flash("This decision form has already been used.", "error")
    elif _attempt_admin_message_email(message, activity):
        flash("Request rejected and notification email submission was accepted by the email service.", "success")
    else:
        flash("Request rejected, but the email was not accepted. Retry it from the message history.", "error")
    return redirect(url_for("admin.message_detail", message_id=message.id))


# ------------------------------------------------------------- SETTINGS ----

@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    admin_user = get_current_admin()

    if request.method == "POST":
        current_password = request.form.get("current_password") or ""
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not admin_user.check_password(current_password):
            flash("Current password is incorrect.", "error")
        elif len(new_password) < 8:
            flash("New password must be at least 8 characters.", "error")
        elif new_password != confirm_password:
            flash("New password and confirmation do not match.", "error")
        else:
            admin_user.set_password(new_password)
            db.session.commit()
            flash("Password updated.", "success")

    return render_template("admin/settings.html", admin_user=admin_user)


# --------------------------------------------------------------- FILES ----

@admin_bp.route("/uploads/<path:filename>")
def serve_upload_preview(filename):
    # Admin-side preview helper for freshly uploaded images before saving.
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
