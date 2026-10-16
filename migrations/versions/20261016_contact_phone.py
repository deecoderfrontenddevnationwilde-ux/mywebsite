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
    with op.batch_alter_table("contact_messages") as batch_op:
        batch_op.add_column(sa.Column("phone", sa.String(length=50), nullable=True))


def downgrade():
    with op.batch_alter_table("contact_messages") as batch_op:
        batch_op.drop_column("phone")
