"""Add database-backed offers and featured projects.

Revision ID: 20260912_content_management
Revises:
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa


revision = "20260912_content_management"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "service_offers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("icon", sa.String(length=100), nullable=True),
        sa.Column("link_url", sa.String(length=500), nullable=True),
        sa.Column("link_label", sa.String(length=100), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_service_offers_display_order", "service_offers", ["display_order"])
    op.create_index("ix_service_offers_active", "service_offers", ["active"])

    op.create_table(
        "featured_projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("short_description", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("project_url", sa.String(length=500), nullable=True),
        sa.Column("github_url", sa.String(length=500), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_featured_projects_display_order", "featured_projects", ["display_order"])
    op.create_index("ix_featured_projects_active", "featured_projects", ["active"])

    service_table = sa.table(
        "service_offers",
        sa.column("title", sa.String),
        sa.column("description", sa.Text),
        sa.column("icon", sa.String),
        sa.column("display_order", sa.Integer),
        sa.column("active", sa.Boolean),
    )
    op.bulk_insert(service_table, [
        {"title": "Custom Software Development", "description": "High-performance web applications, responsive UIs, APIs, and scalable backend architecture engineered for real-world use.", "icon": "ri-code-s-slash-line", "display_order": 10, "active": True},
        {"title": "Application & Network Security", "description": "Penetration testing, vulnerability assessments, secure code audits, and server hardening so threats are found before attackers do.", "icon": "ri-shield-keyhole-line", "display_order": 20, "active": True},
        {"title": "DevSecOps Integration", "description": "Security tools embedded in the development pipeline for continuous protection, testing, and safer deployments.", "icon": "ri-git-branch-line", "display_order": 30, "active": True},
        {"title": "UI / UX Design", "description": "Clean, intuitive interfaces with strong hierarchy and smooth interactions, from wireframes to polished production design.", "icon": "ri-palette-line", "display_order": 40, "active": True},
        {"title": "E-Commerce & Product Sites", "description": "Conversion-focused storefronts and product experiences with clear navigation, search, and responsive layouts.", "icon": "ri-store-2-line", "display_order": 50, "active": True},
        {"title": "Code Reviews & Audits", "description": "Structured reviews of code quality, security posture, performance, and maintainability with clear, actionable reports.", "icon": "ri-search-eye-line", "display_order": 60, "active": True},
    ])

    project_table = sa.table(
        "featured_projects",
        sa.column("title", sa.String),
        sa.column("short_description", sa.String),
        sa.column("image", sa.String),
        sa.column("category", sa.String),
        sa.column("display_order", sa.Integer),
        sa.column("active", sa.Boolean),
    )
    op.bulk_insert(project_table, [
        {"title": "DeeCoder Portfolio", "short_description": "Personal developer portfolio with grid backdrop, gradient typography, and smooth scroll interactions.", "image": "static:images/port.png", "category": "HTML/CSS · JavaScript · UI Design", "display_order": 10, "active": True},
        {"title": "Florante Online Shopping", "short_description": "Premium lifestyle e-commerce for luxury watches with product hero, search, and polished dark-gold aesthetics.", "image": "static:images/e-com.png", "category": "E-Commerce · UI/UX · Responsive", "display_order": 20, "active": True},
        {"title": "Movie-Zone Streaming App", "short_description": "Streaming-style movie browser with sidebar navigation, poster grid, and bold yellow accent theme.", "image": "static:images/move.png", "category": "Frontend · Grid Layout · Dark UI", "display_order": 30, "active": True},
        {"title": "Premium Brand Showcase", "short_description": "HTML5 and CSS3 layout architecture with polished visual hierarchy and high-fidelity brand presentation.", "image": "static:images/brand-show.png", "category": "HTML5 · CSS3 · Layout", "display_order": 40, "active": True},
        {"title": "Interactive Component Suite", "short_description": "Modern UI component architecture with smooth interactions and reusable, modular structure.", "image": "static:images/interactive.png", "category": "UI Components · JavaScript · Modern UI", "display_order": 50, "active": True},
    ])


def downgrade():
    op.drop_index("ix_featured_projects_active", table_name="featured_projects")
    op.drop_index("ix_featured_projects_display_order", table_name="featured_projects")
    op.drop_table("featured_projects")
    op.drop_index("ix_service_offers_active", table_name="service_offers")
    op.drop_index("ix_service_offers_display_order", table_name="service_offers")
    op.drop_table("service_offers")
