"""
Minimal session-based admin authentication.

We use Flask's signed, server-verified session cookie (SECRET_KEY-signed)
rather than a third-party auth library, since only one role (admin) exists.
Passwords are always hashed with Werkzeug (see models/admin.py).
"""

from functools import wraps

from flask import session, redirect, url_for, flash, g

from models import AdminUser


def login_admin(admin_user) -> None:
    session.clear()
    session["admin_id"] = admin_user.id
    session.permanent = True


def logout_admin() -> None:
    session.clear()


def get_current_admin():
    if "admin_id" not in session:
        return None
    if "_admin_cache" not in g:
        g._admin_cache = AdminUser.query.get(session["admin_id"])
    return g._admin_cache


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        admin = get_current_admin()
        if admin is None or not admin.is_active:
            flash("Please log in to access the admin dashboard.", "error")
            return redirect(url_for("admin.login"))
        return view_func(*args, **kwargs)

    return wrapped
