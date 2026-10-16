"""Add contact inbox priority, trash, internal notes, and reply metadata.

Revision ID: 20261016_contact_management
Revises: 20261016_contact_workflow
Create Date: 2026-10-16
"""

from alembic import op
import sqlalchemy as sa


revision = "20261016_contact_management"
down_revision = "20261016_contact_workflow"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("contact_messages") as batch_op:
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column("priority", sa.String(length=16), nullable=False, server_default="NORMAL")
        )
        batch_op.add_column(sa.Column("internal_note", sa.Text(), nullable=True))
        batch_op.create_index("ix_contact_messages_deleted_at", ["deleted_at"], unique=False)

    with op.batch_alter_table("contact_messages") as batch_op:
        batch_op.alter_column("priority", server_default=None)

    with op.batch_alter_table("contact_message_activities") as batch_op:
        batch_op.add_column(sa.Column("recipient_email", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("email_subject", sa.String(length=200), nullable=True))


def downgrade():
    with op.batch_alter_table("contact_message_activities") as batch_op:
        batch_op.drop_column("email_subject")
        batch_op.drop_column("recipient_email")

    with op.batch_alter_table("contact_messages") as batch_op:
        batch_op.drop_index("ix_contact_messages_deleted_at")
        batch_op.drop_column("internal_note")
        batch_op.drop_column("priority")
        batch_op.drop_column("deleted_at")
