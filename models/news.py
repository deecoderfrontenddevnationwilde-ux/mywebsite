from datetime import datetime, timezone

from extensions import db


class News(db.Model):
    __tablename__ = "news"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    summary = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text, nullable=False)
    featured_image = db.Column(db.String(255), nullable=True)
    author = db.Column(db.String(120), nullable=True)

    published = db.Column(db.Boolean, default=False, nullable=False, index=True)
    # Tracks whether a "new article" notification has already been sent for the
    # CURRENT publish cycle. Reset to False whenever the article is unpublished,
    # so republishing does not accidentally skip a notification, and toggling
    # publish on/off repeatedly without unpublishing never sends duplicates.
    notification_sent = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    published_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<News {self.slug}>"
