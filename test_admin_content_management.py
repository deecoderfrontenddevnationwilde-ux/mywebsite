import io
import os
import tempfile
import unittest

from app import create_app
from config import Config
from extensions import db
from models import AdminUser, FeaturedProject, News, Product


class AdminContentManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = os.path.join(self.temp_dir.name, "content.sqlite3")
        self.upload_folder = os.path.join(self.temp_dir.name, "uploads")

        class TestConfig(Config):
            TESTING = True
            WTF_CSRF_ENABLED = False
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{self.database_path}"
            UPLOAD_FOLDER = self.upload_folder
            MAX_UPLOAD_MB = 1

        self.app = create_app(TestConfig)
        with self.app.app_context():
            db.create_all()
            admin = AdminUser(username="content-admin", email="content-admin@example.com")
            admin.set_password("test-password")
            db.session.add(admin)
            db.session.commit()
            self.admin_id = admin.id
        self.client = self.app.test_client()
        self.login()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def login(self):
        with self.client.session_transaction() as session:
            session["admin_id"] = self.admin_id

    @staticmethod
    def valid_image(name="cover.png"):
        return (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"image-data"), name)

    def test_admin_content_pages_render_premium_upload_and_management_controls(self):
        expected_form_markers = {
            "/admin/projects/new": (
                b"Project information",
                b"Live project URL",
                b"Drop a cover image here",
                b"CARD PREVIEW",
                b"Active on public website",
            ),
            "/admin/products/new": (
                b"Product information",
                b"Price (USD)",
                b"Availability",
                b"Drop an image or browse",
                b"Published",
                b"CARD PREVIEW",
            ),
            "/admin/news/new": (
                b"ARTICLE CONTENT",
                b"Full article content",
                b"ARTICLE PREVIEW",
                b"Publish article",
                b"Drop a cover image here",
            ),
        }
        for route, markers in expected_form_markers.items():
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                for marker in markers:
                    self.assertIn(marker, response.data)
                self.assertIn(b"data-content-upload-progress", response.data)
                self.assertIn(b"Ready to save", response.data)
                self.assertIn(b"admin.css?v=20261010-content-management", response.data)
                self.assertIn(b"admin.js?v=20261010-content-management", response.data)

        for route in ("/admin/projects", "/admin/products", "/admin/news"):
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"data-content-search", response.data)
                self.assertIn(b"content-library-grid", response.data)

    def test_projects_products_and_news_use_existing_crud_and_upload_backend(self):
        project_response = self.client.post(
            "/admin/projects/new",
            data={
                "title": "Portfolio project",
                "short_description": "A project card summary.",
                "description": "Full project story.",
                "category": "Web",
                "project_url": "https://example.com",
                "github_url": "https://github.com/example/project",
                "display_order": "2",
                "active": "on",
                "image": self.valid_image(),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(project_response.status_code, 302)
        product_response = self.client.post(
            "/admin/products/new",
            data={
                "name": "Catalog product",
                "short_description": "A product card summary.",
                "description": "Product details.",
                "price": "19.95",
                "category": "Template",
                "stock_status": "out_of_stock",
                "featured": "on",
                "published": "on",
                "image": self.valid_image("product.png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(product_response.status_code, 302)
        news_response = self.client.post(
            "/admin/news/new",
            data={
                "title": "Newsroom article",
                "summary": "A concise news summary.",
                "content": "<p>Article content.</p>",
                "author": "Editor",
                "featured_image": self.valid_image("news.png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(news_response.status_code, 302)

        with self.app.app_context():
            project = FeaturedProject.query.one()
            product = Product.query.one()
            article = News.query.one()
            self.assertTrue(project.active)
            self.assertEqual(project.project_url, "https://example.com")
            self.assertTrue(os.path.isfile(os.path.join(self.upload_folder, project.image)))
            self.assertTrue(product.published)
            self.assertTrue(product.featured)
            self.assertEqual(product.stock_status, "out_of_stock")
            self.assertEqual(str(product.price), "19.95")
            self.assertTrue(os.path.isfile(os.path.join(self.upload_folder, product.image)))
            self.assertFalse(article.published)
            self.assertEqual(article.author, "Editor")
            self.assertTrue(os.path.isfile(os.path.join(self.upload_folder, article.featured_image)))
            project_id, product_id, article_id = project.id, product.id, article.id

        self.assertIn(b"Portfolio project", self.client.get("/admin/projects").data)
        self.assertIn(b"Catalog product", self.client.get("/admin/products").data)
        self.assertIn(b"Newsroom article", self.client.get("/admin/news").data)
        self.assertEqual(self.client.get(f"/admin/projects/{project_id}/edit").status_code, 200)
        self.assertEqual(self.client.get(f"/admin/products/{product_id}/edit").status_code, 200)
        self.assertEqual(self.client.get(f"/admin/news/{article_id}/edit").status_code, 200)

        project_update = self.client.post(
            f"/admin/projects/{project_id}/edit",
            data={
                "title": "Portfolio project",
                "short_description": "Updated project card summary.",
                "display_order": "3",
            },
        )
        product_update = self.client.post(
            f"/admin/products/{product_id}/edit",
            data={
                "name": "Catalog product",
                "description": "Updated product details.",
                "stock_status": "in_stock",
            },
        )
        news_publish = self.client.post(
            f"/admin/news/{article_id}/edit",
            data={
                "title": "Newsroom article",
                "summary": "Updated news summary.",
                "content": "<p>Updated article content.</p>",
                "published": "on",
            },
        )
        self.assertEqual(project_update.status_code, 302)
        self.assertEqual(product_update.status_code, 302)
        self.assertEqual(news_publish.status_code, 302)
        with self.app.app_context():
            self.assertFalse(db.session.get(FeaturedProject, project_id).active)
            updated_product = db.session.get(Product, product_id)
            self.assertEqual(updated_product.stock_status, "in_stock")
            self.assertFalse(updated_product.published)
            self.assertTrue(db.session.get(News, article_id).published)

        news_unpublish = self.client.post(
            f"/admin/news/{article_id}/edit",
            data={
                "title": "Newsroom article",
                "summary": "Updated news summary.",
                "content": "<p>Updated article content.</p>",
            },
        )
        self.assertEqual(news_unpublish.status_code, 302)
        with self.app.app_context():
            self.assertFalse(db.session.get(News, article_id).published)

    def test_invalid_project_request_renders_validation_instead_of_crashing(self):
        response = self.client.post(
            "/admin/projects/new",
            data={"title": "", "short_description": ""},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Title and short description are required.", response.data)
        with self.app.app_context():
            self.assertEqual(FeaturedProject.query.count(), 0)

        oversized_image = self.client.post(
            "/admin/projects/new",
            data={
                "title": "Oversized cover project",
                "short_description": "Project summary.",
                "image": (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"x" * (1024 * 1024)), "cover.png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(oversized_image.status_code, 200)
        self.assertIn(b"image exceeds the image upload limit", oversized_image.data)
        with self.app.app_context():
            self.assertEqual(FeaturedProject.query.count(), 0)

        invalid_image = self.client.post(
            "/admin/projects/new",
            data={
                "title": "Bad cover project",
                "short_description": "Project summary.",
                "image": (io.BytesIO(b"not an image"), "cover.png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(invalid_image.status_code, 200)
        self.assertIn(b"does not look like a valid image", invalid_image.data)
        with self.app.app_context():
            self.assertEqual(FeaturedProject.query.count(), 0)

    def test_content_management_routes_remain_admin_only(self):
        self.client.get("/admin/logout")
        for route in (
            "/admin/projects",
            "/admin/projects/new",
            "/admin/products",
            "/admin/products/new",
            "/admin/news",
            "/admin/news/new",
        ):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 302)
