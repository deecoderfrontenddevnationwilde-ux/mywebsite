from datetime import datetime, timezone
from urllib.parse import urlparse

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app

from extensions import db
from models import AdminUser, ContactMessage, FeaturedProject, News, Product, ServiceOffer, Subscriber
from auth import login_admin, logout_admin, login_required, get_current_admin
from utils import make_unique_slug, save_uploaded_image
from services.email_service import (
    send_new_news_notification,
    send_contact_approval_notification,
    send_contact_declined_notification,
)

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
        "total_subscribers": Subscriber.query.filter_by(subscribed=True).count(),
        "pending_messages": ContactMessage.query.filter_by(status=ContactMessage.STATUS_PENDING).count(),
        "approved_messages": ContactMessage.query.filter_by(status=ContactMessage.STATUS_APPROVED).count(),
        "declined_messages": ContactMessage.query.filter_by(status=ContactMessage.STATUS_DECLINED).count(),
    }
    recent_messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).limit(5).all()
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
        return None, ""
    try:
        project_url = _optional_url(request.form.get("project_url"), "Project URL")
        github_url = _optional_url(request.form.get("github_url"), "GitHub URL")
        display_order = int(request.form.get("display_order") or 0)
        image_path = save_uploaded_image(request.files.get("image"), "projects")
    except ValueError as error:
        flash(str(error) if "URL" in str(error) or "image" in str(error).lower() else "Display order must be a whole number.", "error")
        return None, ""
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
            image_path = save_uploaded_image(request.files.get("featured_image"), "news")
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
            image_path = save_uploaded_image(request.files.get("featured_image"), "news")
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
        featured = request.form.get("featured") == "on"
        publish = request.form.get("published") == "on"
        notify = request.form.get("notify_on_publish") == "on"

        if not name or not description:
            flash("Name and description are required.", "error")
            return render_template("admin/product_form.html", product=None, form=request.form)

        price = None
        if price_raw:
            try:
                price = float(price_raw)
            except ValueError:
                flash("Price must be a number.", "error")
                return render_template("admin/product_form.html", product=None, form=request.form)

        try:
            image_path = save_uploaded_image(request.files.get("image"), "products")
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
        featured = request.form.get("featured") == "on"
        publish = request.form.get("published") == "on"
        notify = request.form.get("notify_on_publish") == "on"

        if not name or not description:
            flash("Name and description are required.", "error")
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
            image_path = save_uploaded_image(request.files.get("image"), "products")
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

@admin_bp.route("/messages")
@login_required
def messages_index():
    status_filter = request.args.get("status", ContactMessage.STATUS_PENDING)
    query = ContactMessage.query
    if status_filter in (ContactMessage.STATUS_PENDING, ContactMessage.STATUS_APPROVED, ContactMessage.STATUS_DECLINED):
        query = query.filter_by(status=status_filter)
    messages = query.order_by(ContactMessage.created_at.desc()).all()
    return render_template("admin/messages_list.html", messages=messages, status_filter=status_filter)


@admin_bp.route("/messages/<int:message_id>")
@login_required
def message_detail(message_id):
    message = ContactMessage.query.get_or_404(message_id)
    return render_template("admin/message_detail.html", message=message)


@admin_bp.route("/messages/<int:message_id>/approve", methods=["POST"])
@login_required
def message_approve(message_id):
    message = ContactMessage.query.get_or_404(message_id)
    admin_note = (request.form.get("admin_note") or "").strip()

    already_decided = message.status == ContactMessage.STATUS_APPROVED

    message.status = ContactMessage.STATUS_APPROVED
    if admin_note:
        message.admin_note = admin_note
    message.reviewed_at = datetime.now(timezone.utc)
    db.session.commit()

    # Guard against duplicate emails if the admin clicks the button repeatedly.
    if not already_decided and not message.decision_email_sent:
        if send_contact_approval_notification(message):
            message.decision_email_sent = True
            db.session.commit()

    flash("Message approved.", "success")
    return redirect(url_for("admin.messages_index"))


@admin_bp.route("/messages/<int:message_id>/decline", methods=["POST"])
@login_required
def message_decline(message_id):
    message = ContactMessage.query.get_or_404(message_id)
    admin_note = (request.form.get("admin_note") or "").strip()

    already_decided = message.status == ContactMessage.STATUS_DECLINED

    message.status = ContactMessage.STATUS_DECLINED
    if admin_note:
        message.admin_note = admin_note
    message.reviewed_at = datetime.now(timezone.utc)
    db.session.commit()

    if not already_decided and not message.decision_email_sent:
        if send_contact_declined_notification(message):
            message.decision_email_sent = True
            db.session.commit()

    flash("Message declined.", "success")
    return redirect(url_for("admin.messages_index"))


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
