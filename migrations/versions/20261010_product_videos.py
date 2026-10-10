"""Add persistent product video management.

Revision ID: 20261010_product_videos
Revises: 20260926_more_offers
Create Date: 2026-10-10
"""

from alembic import op
import sqlalchemy as sa


revision = "20261010_product_videos"
down_revision = "20260926_more_offers"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "product_videos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("video_path", sa.String(length=255), nullable=False),
        sa.Column("thumbnail_path", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("product_videos")
