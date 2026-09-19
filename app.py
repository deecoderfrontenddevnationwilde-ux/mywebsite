import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, render_template

load_dotenv()  # reads .env into environment variables before Config is built

from config import Config
from extensions import db, migrate, csrf


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.permanent_session_lifetime = timedelta(hours=8)

    # Ensure instance/ and uploads/ exist
    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)
    os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "news"), exist_ok=True)
    os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "products"), exist_ok=True)
    os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "projects"), exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    from models import (  # noqa: F401
        AdminUser,
        ContactMessage,
        FeaturedProject,
        News,
        Product,
        ServiceOffer,
        Subscriber,
    )

    from routes.public import public_bp
    from routes.admin import admin_bp
    from routes.api import api_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp, url_prefix="/api")
    csrf.exempt(api_bp)  # JSON API uses fetch(); CSRF is handled via same-origin + JSON content-type checks

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(413)
    def too_large(e):
        return render_template("404.html", message="That file is too large to upload."), 413

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("Unhandled server error")
        return render_template("500.html"), 500

    @app.context_processor
    def inject_globals():
        return {
            "company_name": app.config.get("COMPANY_NAME"),
        }

    return app


app = create_app()


@app.cli.command("create-admin")
def create_admin_command():
    """Create an admin user interactively: flask create-admin"""
    import getpass
    from models import AdminUser

    username = input("Admin username: ").strip()
    email = input("Admin email: ").strip()
    password = getpass.getpass("Admin password: ")
    confirm = getpass.getpass("Confirm password: ")

    if password != confirm:
        print("Passwords do not match. Aborted.")
        return
    if len(password) < 8:
        print("Password must be at least 8 characters. Aborted.")
        return
    if AdminUser.query.filter_by(username=username).first():
        print(f"An admin with username '{username}' already exists. Aborted.")
        return

    admin_user = AdminUser(username=username, email=email)
    admin_user.set_password(password)
    db.session.add(admin_user)
    db.session.commit()
    print(f"Admin user '{username}' created successfully.")


if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])
