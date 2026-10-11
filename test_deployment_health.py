import os
import tempfile
import unittest
from pathlib import Path

from app import create_app, database_schema_problems
from config import BASE_DIR, Config, normalize_database_uri, resolve_project_path
from extensions import db
from models import AdminUser, ProductVideo


class DeploymentHealthTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = os.path.join(self.temp_dir.name, "deployment.sqlite3")
        self.upload_folder = os.path.join(self.temp_dir.name, "uploads")

        class TestConfig(Config):
            TESTING = True
            WTF_CSRF_ENABLED = False
            SECRET_KEY = "deployment-health-test-secret"
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{self.database_path}"
            UPLOAD_FOLDER = self.upload_folder

        self.app = create_app(TestConfig)
        with self.app.app_context():
            db.create_all()
            admin = AdminUser(username="health-admin", email="health@example.com")
            admin.set_password("test-password")
            db.session.add(admin)
            db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def test_relative_sqlite_urls_resolve_from_project_and_production_requires_absolute(self):
        resolved = normalize_database_uri("sqlite:///instance/company.db")
        from sqlalchemy.engine import make_url

        self.assertEqual(
            Path(make_url(resolved).database),
            (BASE_DIR / "instance" / "company.db").resolve(),
        )
        self.assertEqual(
            resolve_project_path("uploads"),
            (BASE_DIR / "uploads").resolve(),
        )
        absolute_upload_path = self.temp_dir.name
        self.assertEqual(
            resolve_project_path(absolute_upload_path),
            Path(absolute_upload_path).resolve(),
        )
        with self.assertRaisesRegex(ValueError, "absolute file path"):
            normalize_database_uri(
                "sqlite:///instance/company.db",
                require_absolute_sqlite=True,
            )

    def test_public_pages_and_empty_admin_video_sections_load(self):
        homepage = self.client.get("/")
        self.assertEqual(homepage.status_code, 200)

        self.assertEqual(self.client.get("/admin/dashboard").status_code, 302)
        self.assertEqual(self.client.get("/admin/videos").status_code, 302)

        login = self.client.post(
            "/admin/login",
            data={"username": "health-admin", "password": "test-password"},
        )
        self.assertEqual(login.status_code, 302)
        dashboard = self.client.get("/admin/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn(b"Product Videos", dashboard.data)
        self.assertIn(b">0</div>", dashboard.data)

        videos = self.client.get("/admin/videos")
        self.assertEqual(videos.status_code, 200)
        self.assertIn(b"No product videos yet", videos.data)

    def test_database_check_finds_missing_video_table(self):
        with self.app.app_context():
            ProductVideo.__table__.drop(db.engine)
            problems = database_schema_problems(db.engine, db.metadata)

        self.assertIn("missing table product_videos", problems)

    def test_database_check_reports_missing_models_without_changing_records(self):
        with self.app.app_context():
            before = AdminUser.query.count()
            problems = database_schema_problems(db.engine, db.metadata)
            after = AdminUser.query.count()

        self.assertEqual(problems, [])
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
