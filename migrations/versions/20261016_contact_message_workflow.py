"""Add contact inbox workflow and outgoing email history.

Revision ID: 20261016_contact_workflow
Revises: 20261016_contact_phone
Create Date: 2026-10-16
"""

from alembic import op
import sqlalchemy as sa


revision = "20261016_contact_workflow"
down_revision = "20261016_contact_phone"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("contact_messages") as batch_op:
        batch_op.add_column(sa.Column("is_read", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("archived_at", sa.DateTime(), nullable=True))

    op.execute("UPDATE contact_messages SET is_read = FALSE WHERE is_read IS NULL")

    with op.batch_alter_table("contact_messages") as batch_op:
        batch_op.alter_column("is_read", existing_type=sa.Boolean(), nullable=False)
        batch_op.create_index("ix_contact_messages_is_read", ["is_read"], unique=False)
        batch_op.create_index("ix_contact_messages_archived_at", ["archived_at"], unique=False)

    op.execute(
        "UPDATE contact_messages SET status = 'ACCEPTED' WHERE status = 'APPROVED'"
    )
    op.execute(
        "UPDATE contact_messages SET status = 'REJECTED' WHERE status = 'DECLINED'"
    )

    op.create_table(
        "contact_message_activities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contact_message_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("email_status", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("request_token", sa.String(length=36), nullable=True),
        sa.Column("admin_username", sa.String(length=150), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("last_error", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["contact_message_id"], ["contact_messages.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_token"),
    )
    with op.batch_alter_table("contact_message_activities") as batch_op:
        batch_op.create_index(
            "ix_contact_message_activities_contact_message_id",
            ["contact_message_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_contact_message_activities_event_type", ["event_type"], unique=False
        )
        batch_op.create_index(
            "ix_contact_message_activities_email_status", ["email_status"], unique=False
        )

    op.execute(
        """
        INSERT INTO contact_message_activities
            (contact_message_id, event_type, email_status, attempt_count, created_at, accepted_at)
        SELECT id, 'BUSINESS_NOTIFICATION', 'ACCEPTED', 1, created_at, created_at
        FROM contact_messages WHERE notification_email_submitted = TRUE
        """
    )
    op.execute(
        """
        INSERT INTO contact_message_activities
            (contact_message_id, event_type, email_status, attempt_count, created_at, accepted_at)
        SELECT id, 'SUBMISSION_CONFIRMATION', 'ACCEPTED', 1, created_at, created_at
        FROM contact_messages WHERE confirmation_email_submitted = TRUE
        """
    )
    op.execute(
        """
        INSERT INTO contact_message_activities
            (contact_message_id, event_type, body, email_status, attempt_count, created_at, accepted_at)
        SELECT id,
               CASE status WHEN 'ACCEPTED' THEN 'REQUEST_ACCEPTED' ELSE 'REQUEST_REJECTED' END,
               admin_note, 'ACCEPTED', 1,
               COALESCE(reviewed_at, created_at), COALESCE(reviewed_at, created_at)
        FROM contact_messages
        WHERE decision_email_sent = TRUE AND status IN ('ACCEPTED', 'REJECTED')
        """
    )


def downgrade():
    op.drop_table("contact_message_activities")
    with op.batch_alter_table("contact_messages") as batch_op:
        batch_op.drop_index("ix_contact_messages_is_read")
        batch_op.drop_index("ix_contact_messages_archived_at")
        batch_op.drop_column("archived_at")
        batch_op.drop_column("is_read")
    op.execute(
        "UPDATE contact_messages SET status = 'APPROVED' WHERE status = 'ACCEPTED'"
    )
    op.execute(
        "UPDATE contact_messages SET status = 'DECLINED' WHERE status = 'REJECTED'"
    )
