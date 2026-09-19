import secrets
from datetime import datetime, timezone

from extensions import db


class Subscriber(db.Model):
    __tablename__ = "subscribers"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    subscribed = db.Column(db.Boolean, default=True, nullable=False)
    # Used to build a one-click, no-login unsubscribe link in emails.
    unsubscribe_token = db.Column(
        db.String(64), unique=True, nullable=False, default=lambda: secrets.token_urlsafe(32)
    )
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    unsubscribed_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Subscriber {self.email}>"
