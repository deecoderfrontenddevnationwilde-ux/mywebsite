from datetime import datetime, timezone

from extensions import db


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    short_description = db.Column(db.String(300), nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=True)
    image = db.Column(db.String(255), nullable=True)
    category = db.Column(db.String(100), nullable=True, index=True)
    stock_status = db.Column(db.String(20), default="in_stock", nullable=False)

    featured = db.Column(db.Boolean, default=False, nullable=False, index=True)
    published = db.Column(db.Boolean, default=False, nullable=False, index=True)
    notify_on_publish = db.Column(db.Boolean, default=False, nullable=False)
    notification_sent = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    published_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Product {self.slug}>"
