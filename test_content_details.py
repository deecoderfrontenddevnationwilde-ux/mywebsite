import os
import tempfile
import unittest
from datetime import datetime, timezone

from app import create_app
from config import Config
from extensions import db
from models import News, Product


class SharedContentDetailTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = os.path.join(self.temp_dir.name, "content.sqlite3")

        class TestConfig(Config):
            TESTING = True
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{database_path}"
            UPLOAD_FOLDER = os.path.join(self.temp_dir.name, "uploads")

        self.app = create_app(TestConfig)
        with self.app.app_context():
            db.create_all()
            db.session.add_all(
                [
                    News(
                        title="Newest article",
                        slug="newest-article",
                        summary="Newest summary",
                        content="<p>Newest article body marker.</p>",
                        author="A. Writer",
                        published=True,
                        published_at=datetime(2026, 3, 3, tzinfo=timezone.utc),
                    ),
                    News(
                        title="Middle article",
                        slug="middle-article",
                        summary="Middle summary",
                        content="<h2>Middle article body marker</h2><p>More words.</p>",
                        author="B. Writer",
                        published=True,
                        published_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
                    ),
                    News(
                        title="Oldest article",
                        slug="oldest-article",
                        summary="Oldest summary",
                        content="<p>Oldest article body marker.</p>",
                        published=True,
                        published_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
                    ),
                    Product(
                        name="First product",
                        slug="first-product",
                        description="<p>First product description marker.</p>",
                        short_description="First product summary",
                        price=0,
                        category="Tools",
                        stock_status="in_stock",
                        published=True,
                    ),
                    Product(
                        name="Second product",
                        slug="second-product",
                        description="<p>Second product description marker.</p>",
                        short_description="Second product summary",
                        category="Tools",
                        stock_status="out_of_stock",
                        published=True,
                    ),
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

    def test_news_details_render_the_correct_story_and_adjacent_navigation(self):
        newest = self.client.get("/news/newest-article")
        middle = self.client.get("/news/middle-article")
        oldest = self.client.get("/news/oldest-article")

        self.assertEqual(newest.status_code, 200)
        self.assertIn(b"Newest article body marker.", newest.data)
        self.assertNotIn(b"Newer story", newest.data)
        self.assertIn(b"Older story", newest.data)

        self.assertEqual(middle.status_code, 200)
        self.assertIn(b"Middle article body marker", middle.data)
        self.assertIn(b"Newest article", middle.data)
        self.assertIn(b"Oldest article", middle.data)
        self.assertIn(b"min read", middle.data)
        self.assertIn(b"Share this story", middle.data)

        self.assertEqual(oldest.status_code, 200)
        self.assertIn(b"Oldest article body marker.", oldest.data)
        self.assertIn(b"Newer story", oldest.data)
        self.assertNotIn(b"Older story", oldest.data)

    def test_product_details_use_the_shared_layout_and_only_existing_product_data(self):
        first = self.client.get("/products/first-product")
        second = self.client.get("/products/second-product")

        self.assertEqual(first.status_code, 200)
        self.assertIn(b'class="content-detail-page content-detail-product"', first.data)
        self.assertIn(b'class="content-detail-layout"', first.data)
        self.assertIn(b"First product description marker.", first.data)
        self.assertIn(b"$0.00", first.data)
        self.assertIn(b"Enquire about this product", first.data)
        self.assertNotIn(b"discount", first.data.lower())

        self.assertEqual(second.status_code, 200)
        self.assertIn(b"Second product description marker.", second.data)
        self.assertIn(b"Out Of Stock", second.data)
        self.assertIn(b"Related", second.data)
        self.assertNotIn(b"First product description marker.", second.data)

    def test_homepage_and_collection_cards_link_to_unique_details(self):
        homepage = self.client.get("/")
        news = self.client.get("/news")
        products = self.client.get("/products")

        for response in (homepage, news):
            self.assertIn(b'href="/news/newest-article"', response.data)
            self.assertIn(b'href="/news/middle-article"', response.data)

        for response in (homepage, products):
            self.assertIn(b'href="/products/first-product"', response.data)
            self.assertIn(b'href="/products/second-product"', response.data)

    def test_unknown_or_unpublished_content_returns_not_found(self):
        self.assertEqual(self.client.get("/news/missing-article").status_code, 404)
        self.assertEqual(self.client.get("/products/missing-product").status_code, 404)


if __name__ == "__main__":
    unittest.main()
