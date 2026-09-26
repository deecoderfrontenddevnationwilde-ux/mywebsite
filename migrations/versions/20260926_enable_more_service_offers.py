"""Ensure the three additional homepage offers are available.

Revision ID: 20260926_more_offers
Revises: 1d2745b83511
Create Date: 2026-09-26
"""

from alembic import op
import sqlalchemy as sa


revision = "20260926_more_offers"
down_revision = "1d2745b83511"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    service_offers = sa.Table(
        "service_offers",
        sa.MetaData(),
        autoload_with=connection,
    )
    offers = [
        {
            "title": "Business Process Automation",
            "description": "Streamlined operations through workflow automation, smart task routing, and digital system orchestration that saves time and removes bottlenecks.",
            "icon": "ri-layout-grid-line",
            "display_order": 90,
        },
        {
            "title": "Cloud Infrastructure & Deployment",
            "description": "Scalable cloud setup, deployment pipelines, and infrastructure optimization designed for reliability, speed, and future growth.",
            "icon": "ri-cloud-line",
            "display_order": 100,
        },
        {
            "title": "Brand Strategy & Positioning",
            "description": "Clear positioning, messaging frameworks, and digital brand guidance that help your business stand out and convert more customers.",
            "icon": "ri-bullseye-line",
            "display_order": 110,
        },
    ]

    for offer in offers:
        existing = connection.execute(
            sa.select(service_offers.c.id).where(service_offers.c.title == offer["title"])
        ).first()
        if existing:
            connection.execute(
                sa.update(service_offers)
                .where(service_offers.c.id == existing.id)
                .values(active=True)
            )
        else:
            connection.execute(sa.insert(service_offers).values(**offer, active=True))


def downgrade():
    pass