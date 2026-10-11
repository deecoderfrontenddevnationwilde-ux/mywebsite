"""Store contact rate-limit and idempotency state.

Revision ID: 20261011_contact_safety
Revises: 20261010_product_videos
Create Date: 2026-10-11
"""

from alembic import op
import sqlalchemy as sa


revision = "20261011_contact_safety"
down_revision = "20261010_product_videos"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("contact_messages") as batch_op:
        batch_op.add_column(sa.Column("request_fingerprint", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("submission_token", sa.String(length=36), nullable=True))
        batch_op.add_column(
            sa.Column("notification_email_submitted", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("confirmation_email_submitted", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    with op.batch_alter_table("contact_messages") as batch_op:
        batch_op.create_index(
            "ix_contact_messages_request_fingerprint",
            ["request_fingerprint"],
            unique=False,
        )
        batch_op.create_index(
            "ix_contact_messages_submission_token",
            ["submission_token"],
            unique=True,
        )
        batch_op.alter_column("notification_email_submitted", server_default=None)
        batch_op.alter_column("confirmation_email_submitted", server_default=None)


def downgrade():
    with op.batch_alter_table("contact_messages") as batch_op:
        batch_op.drop_index("ix_contact_messages_request_fingerprint")
        batch_op.drop_index("ix_contact_messages_submission_token")
        batch_op.drop_column("confirmation_email_submitted")
        batch_op.drop_column("notification_email_submitted")
        batch_op.drop_column("submission_token")
        batch_op.drop_column("request_fingerprint")
