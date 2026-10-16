from datetime import datetime, timezone

from extensions import db


class ContactMessage(db.Model):
    __tablename__ = "contact_messages"

    STATUS_PENDING = "PENDING"
    STATUS_IN_PROGRESS = "IN_PROGRESS"
    STATUS_ACCEPTED = "ACCEPTED"
    STATUS_REJECTED = "REJECTED"
    STATUS_APPROVED = STATUS_ACCEPTED
    STATUS_DECLINED = STATUS_REJECTED

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    phone = db.Column(db.String(50), nullable=True)
    subject = db.Column(db.String(200), nullable=True)
    message = db.Column(db.Text, nullable=False)
    request_fingerprint = db.Column(db.String(64), nullable=True, index=True)
    submission_token = db.Column(db.String(36), nullable=True, unique=True, index=True)
    notification_email_submitted = db.Column(db.Boolean, default=False, nullable=False)
    confirmation_email_submitted = db.Column(db.Boolean, default=False, nullable=False)

    status = db.Column(db.String(20), default=STATUS_PENDING, nullable=False, index=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    archived_at = db.Column(db.DateTime, nullable=True, index=True)
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)
    priority = db.Column(db.String(16), nullable=False, default="NORMAL")
    admin_note = db.Column(db.Text, nullable=True)
    internal_note = db.Column(db.Text, nullable=True)

    # Guards against duplicate approval/decline emails if an admin double-clicks.
    decision_email_sent = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    reviewed_at = db.Column(db.DateTime, nullable=True)
    activities = db.relationship(
        "ContactMessageActivity",
        back_populates="contact_message",
        cascade="all, delete-orphan",
        order_by=lambda: (ContactMessageActivity.created_at, ContactMessageActivity.id),
    )

    def __repr__(self):
        return f"<ContactMessage {self.id} {self.status}>"


class ContactMessageActivity(db.Model):
    __tablename__ = "contact_message_activities"

    TYPE_BUSINESS_NOTIFICATION = "BUSINESS_NOTIFICATION"
    TYPE_SUBMISSION_CONFIRMATION = "SUBMISSION_CONFIRMATION"
    TYPE_ADMIN_REPLY = "ADMIN_REPLY"
    TYPE_REQUEST_ACCEPTED = "REQUEST_ACCEPTED"
    TYPE_REQUEST_REJECTED = "REQUEST_REJECTED"
    TYPE_STATUS_CHANGED = "STATUS_CHANGED"
    TYPE_NOTE_UPDATED = "NOTE_UPDATED"
    TYPE_PRIORITY_CHANGED = "PRIORITY_CHANGED"
    TYPE_ARCHIVED = "ARCHIVED"
    TYPE_RESTORED = "RESTORED"
    TYPE_TRASHED = "TRASHED"

    EMAIL_SENDING = "SENDING"
    EMAIL_ACCEPTED = "ACCEPTED"
    EMAIL_FAILED = "FAILED"
    EMAIL_NOT_APPLICABLE = "NOT_APPLICABLE"

    id = db.Column(db.Integer, primary_key=True)
    contact_message_id = db.Column(
        db.Integer,
        db.ForeignKey("contact_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = db.Column(db.String(32), nullable=False, index=True)
    body = db.Column(db.Text, nullable=True)
    recipient_email = db.Column(db.String(255), nullable=True)
    email_subject = db.Column(db.String(200), nullable=True)
    email_status = db.Column(db.String(16), nullable=False, default=EMAIL_SENDING, index=True)
    attempt_count = db.Column(db.Integer, nullable=False, default=0)
    request_token = db.Column(db.String(36), nullable=True, unique=True)
    admin_username = db.Column(db.String(150), nullable=True)
    provider_message_id = db.Column(db.String(255), nullable=True)
    last_error = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_attempt_at = db.Column(db.DateTime, nullable=True)
    accepted_at = db.Column(db.DateTime, nullable=True)

    contact_message = db.relationship("ContactMessage", back_populates="activities")

    def __repr__(self):
        return f"<ContactMessageActivity {self.id} {self.event_type} {self.email_status}>"
