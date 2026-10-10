import os
import tempfile
import unittest

from app import create_app
from config import Config
from extensions import db
from models import FeaturedProject


class PublicProjectListingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = os.path.join(self.temp_dir.name, "projects.sqlite3")
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
                        title=f"Public project {number}",
                        short_description=f"Description for project {number}",
                        display_order=number,
                    )
                    for number in range(1, 12)
                ]
                + [
                    FeaturedProject(
                        title="Inactive project",
                        short_description="This project is not public.",
                        active=False,
                    )
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

    def test_homepage_links_to_complete_public_project_collection(self):
        homepage = self.client.get("/")
        self.assertEqual(homepage.status_code, 200)
        self.assertIn(b"View All Projects", homepage.data)
        self.assertIn(b'href="/projects"', homepage.data)
        projects_section = homepage.data.split(b"<!-- PROJECTS -->", 1)[1].split(
            b"<!-- PRICING -->", 1
        )[0]
        self.assertEqual(projects_section.count(b'class="project-card reveal"'), 3)
        self.assertNotIn(b"Inactive project", homepage.data)

        first_page = self.client.get("/projects")
        self.assertEqual(first_page.status_code, 200)
        for number in range(1, 10):
            self.assertIn(f"Public project {number}".encode(), first_page.data)
        self.assertIn(b"Next &raquo;", first_page.data)
        self.assertNotIn(b"Inactive project", first_page.data)

        second_page = self.client.get("/projects?page=2")
        self.assertEqual(second_page.status_code, 200)
        self.assertIn(b"Public project 10", second_page.data)
        self.assertIn(b"Public project 11", second_page.data)
        self.assertNotIn(b"<h3>Public project 1</h3>", second_page.data)
