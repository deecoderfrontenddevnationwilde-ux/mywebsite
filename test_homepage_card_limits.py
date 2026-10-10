import os
import tempfile
import unittest

from app import create_app
from config import Config
from extensions import db
from models import FeaturedProject, News, Product, ProductVideo


class HomepageCardLimitTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = os.path.join(self.temp_dir.name, "homepage.sqlite3")
        self.upload_folder = os.path.join(self.temp_dir.name, "uploads")

        class TestConfig(Config):
            TESTING = True
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{self.database_path}"
            UPLOAD_FOLDER = self.upload_folder

        self.app = create_app(TestConfig)
        with self.app.app_context():
            db.create_all()
            db.session.add_all(
                [
                    FeaturedProject(
                        title=f"Project {number}",
                        short_description=f"Project description {number}",
                        display_order=number,
                    )
                    for number in range(1, 6)
                ]
            )
            db.session.add_all(
                [
                    Product(
                        name=f"Product {number}",
                        slug=f"product-{number}",
                        description=f"Product description {number}",
                        featured=True,
                        published=True,
                    )
                    for number in range(1, 6)
                ]
            )
            db.session.add_all(
                [
                    News(
                        title=f"News {number}",
                        slug=f"news-{number}",
                        summary=f"News summary {number}",
                        content=f"News article content {number}",
                        published=True,
                    )
                    for number in range(1, 6)
                ]
            )
            db.session.add_all(
                [
                    ProductVideo(
                        title=f"Video {number}",
                        description=f"Video description {number}",
                        video_path=f"videos/video-{number}.mp4",
                    )
                    for number in range(1, 6)
                ]
            )
            db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def test_each_homepage_section_shows_three_and_listing_pages_keep_all_items(self):
        homepage = self.client.get("/")
        self.assertEqual(homepage.status_code, 200)
        html = homepage.data
        sections = {
            "projects": (
                b"<!-- PROJECTS -->",
                b"<!-- PRICING -->",
                b'class="project-card reveal"',
                b"View All Projects",
                b'href="/projects"',
            ),
            "news": (
                b' id="latest-news"',
                b"<!-- FEATURED PRODUCTS",
                b'class="project-card reveal"',
                b"View All News",
                b'href="/news"',
            ),
            "products": (
                b' id="featured-products"',
                b"<!-- PRODUCT VIDEO PREVIEWS",
                b'class="project-card reveal"',
                b"View All Products",
                b'href="/products"',
            ),
            "videos": (
                b' id="product-videos"',
                b"<!-- TESTIMONIALS -->",
                b'class="product-video-card reveal"',
                b"View All Videos",
                b'href="/videos"',
            ),
        }
        expected_titles = {
            "projects": b"Project ",
            "news": b"News ",
            "products": b"Product ",
            "videos": b"Video ",
        }
        for section_name, (start, end, card, label, link) in sections.items():
            with self.subTest(section=section_name):
                content = html.split(start, 1)[1].split(end, 1)[0]
                self.assertEqual(content.count(card), 3)
                self.assertIn(label, content)
                self.assertIn(link, content)
                self.assertEqual(sum(
                    f"<h3>{expected_titles[section_name].decode()}{number}</h3>".encode() in content
                    for number in range(1, 6)
                ), 3)

        listing_cases = (
            ("/projects", "Project"),
            ("/products", "Product"),
            ("/news", "News"),
            ("/videos", "Video"),
        )
        for route, title_prefix in listing_cases:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                for number in range(1, 6):
                    self.assertIn(f"<h3>{title_prefix} {number}</h3>".encode(), response.data)
