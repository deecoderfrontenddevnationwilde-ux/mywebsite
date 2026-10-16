"""Store optional phone numbers from contact form submissions.

Revision ID: 20261016_contact_phone
Revises: 20261011_contact_safety
Create Date: 2026-10-16
"""

from alembic import op
import sqlalchemy as sa


revision = "20261016_contact_phone"
down_revision = "20261011_contact_safety"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table("contact_messages"):
        raise RuntimeError(
            "Cannot add contact_messages.phone because contact_messages does not exist."
        )
    columns = {column["name"] for column in inspector.get_columns("contact_messages")}
    if "phone" not in columns:
        op.add_column(
            "contact_messages",
            sa.Column("phone", sa.String(length=50), nullable=True),
        )


def downgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if inspector.has_table("contact_messages"):
        columns = {column["name"] for column in inspector.get_columns("contact_messages")}
        if "phone" in columns:
            op.drop_column("contact_messages", "phone")
