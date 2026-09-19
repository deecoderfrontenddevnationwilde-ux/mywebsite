from datetime import datetime, timezone

from extensions import db


class ServiceOffer(db.Model):
    __tablename__ = "service_offers"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    icon = db.Column(db.String(100), nullable=True)
    link_url = db.Column(db.String(500), nullable=True)
    link_label = db.Column(db.String(100), nullable=True)
    display_order = db.Column(db.Integer, default=0, nullable=False, index=True)
    active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self):
        return f"<ServiceOffer {self.title}>"
