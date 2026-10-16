import io
import os
import re
import tempfile
import unittest

from app import create_app
from config import Config
from extensions import db
from models import AdminUser, News, Product, ProductVideo


class ProductVideoTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = os.path.join(self.temp_dir.name, "videos.sqlite3")
        self.upload_folder = os.path.join(self.temp_dir.name, "uploads")

        class TestConfig(Config):
            TESTING = True
            WTF_CSRF_ENABLED = False
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{self.database_path}"
            UPLOAD_FOLDER = self.upload_folder
            MAX_UPLOAD_MB = 1
            MAX_VIDEO_UPLOAD_MB = 2
            VIDEO_UPLOAD_CHUNK_MB = 1
            MAX_CONTENT_LENGTH = 2 * 1024 * 1024

        self.config_class = TestConfig
        self.app = create_app(self.config_class)
        self.apps = [self.app]
        with self.app.app_context():
            db.create_all()
            admin = AdminUser(username="video-admin", email="video-admin@example.com")
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
        for app in self.apps:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        self.temp_dir.cleanup()

    def login(self):
        with self.client.session_transaction() as session:
            session["admin_id"] = self.admin_id if hasattr(self, "admin_id") else 1

    @staticmethod
    def mp4_file(name="preview.mp4", padding=b"video-data"):
        return (io.BytesIO(b"\x00\x00\x00\x18ftypisom" + padding), name)

    @staticmethod
    def thumbnail_file(name="poster.png"):
        return (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"image-data"), name)

    def test_admin_crud_public_playback_and_persistence(self):
        videos_page = self.client.get("/admin/videos")
        self.assertEqual(videos_page.status_code, 200)
        self.assertIn(b"/admin/videos/new", videos_page.data)

        add_page = self.client.get("/admin/videos/new")
        self.assertEqual(add_page.status_code, 200)
        self.assertIn(b'action="/admin/videos/new"', add_page.data)
        self.assertIn(b'enctype="multipart/form-data"', add_page.data)
        self.assertIn(b'data-chunk-size="1048576"', add_page.data)
        self.assertIn(b'data-max-video-mb="2"', add_page.data)
        self.assertIn(b"Drag and drop your video here", add_page.data)
        self.assertIn(b"Select Video", add_page.data)
        self.assertIn(b"data-video-preview", add_page.data)
        self.assertIn(b"data-video-filename", add_page.data)
        self.assertIn(b"Ready to upload", add_page.data)
        self.assertIn(b"data-video-thumbnail", add_page.data)
        self.assertIn(b"Saved product videos are published immediately.", add_page.data)
        self.assertIn(b"admin.css?v=20261016-message-center-v2", add_page.data)
        self.assertIn(b"admin.js?v=20261010-content-management", add_page.data)

        legacy_add_page = self.client.get("/admin/videos/add")
        self.assertEqual(legacy_add_page.status_code, 200)

        response = self.client.post(
            "/admin/videos/new",
            data={
                "title": "Product walkthrough",
                "description": "A short introduction to the product.",
                "video": self.mp4_file(),
                "thumbnail": self.thumbnail_file(),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Product video uploaded.", response.data)
        management_page = self.client.get("/admin/videos")
        self.assertEqual(management_page.status_code, 200)
        self.assertIn(b"Search videos...", management_page.data)
        self.assertIn(b"Product walkthrough", management_page.data)
        self.assertIn(b"data-video-duration-source", management_page.data)
        self.assertIn(b"> Live<", management_page.data)
        admin_styles = self.client.get("/static/css/admin.css")
        self.assertEqual(admin_styles.status_code, 200)
        self.assertIn(b".video-library-grid", admin_styles.data)
        self.assertIn(b"@media (max-width: 600px)", admin_styles.data)
        self.assertIn(b".video-dropzone", admin_styles.data)

        with self.app.app_context():
            video = ProductVideo.query.one()
            video_id = video.id
            original_video_path = video.video_path
            original_thumbnail_path = video.thumbnail_path

        edit_page = self.client.get(f"/admin/videos/{video_id}/edit")
        self.assertEqual(edit_page.status_code, 200)
        self.assertIn(f'action="/admin/videos/{video_id}/edit"'.encode(), edit_page.data)
        self.assertIn(f'data-video-id="{video_id}"'.encode(), edit_page.data)

        homepage = self.client.get("/")
        self.assertIn(b"Product walkthrough", homepage.data)
        homepage_html = homepage.data.decode()
        video_tag = re.search(r"<video\b[^>]*>", homepage_html)
        self.assertIsNotNone(video_tag)
        self.assertNotRegex(video_tag.group(0), r"\scontrols(?:\s|>|=)")
        self.assertIn(b"data-video-seek", homepage.data)
        self.assertIn(b'role="slider"', homepage.data)
        self.assertIn(b"product-video-seek-rail", homepage.data)
        self.assertIn(b"data-video-played", homepage.data)
        self.assertIn(b"product-video-seek-handle", homepage.data)
        self.assertIn(b"data-video-time", homepage.data)
        self.assertIn(b'aria-label="Seek Product walkthrough"', homepage.data)
        self.assertIn(b'aria-label="Volume for Product walkthrough"', homepage.data)
        self.assertNotIn(b"<span class=\"sr-only\">Seek Product walkthrough</span>", homepage.data)
        self.assertNotIn(b"<span class=\"sr-only\">Volume for Product walkthrough</span>", homepage.data)
        self.assertIn(b"site-extra.css?v=20261016-responsive-layout-2", homepage.data)
        self.assertIn(b"main.js?v=20261016-shared-contact-forms", homepage.data)
        media = self.client.get(f"/uploads/{original_video_path}")
        self.assertEqual(media.status_code, 200)
        self.assertTrue(media.data.startswith(b"\x00\x00\x00\x18ftypisom"))
        media.close()

        restarted_app = create_app(self.config_class)
        self.apps.append(restarted_app)
        with restarted_app.test_client() as restarted_client:
            self.assertIn(b"Product walkthrough", restarted_client.get("/").data)
            persisted_media = restarted_client.get(f"/uploads/{original_video_path}")
            self.assertEqual(persisted_media.status_code, 200)
            persisted_media.close()

        response = self.client.post(
            f"/admin/videos/{video_id}/edit",
            data={
                "title": "Updated walkthrough",
                "description": "Updated product details.",
                "video": (io.BytesIO(b"\x1a\x45\xdf\xa3webm-data"), "replacement.webm"),
                "thumbnail": self.thumbnail_file("replacement.png"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Product video updated.", response.data)
        with self.app.app_context():
            video = db.session.get(ProductVideo, video_id)
            replacement_video_path = video.video_path
            replacement_thumbnail_path = video.thumbnail_path
            self.assertEqual(video.title, "Updated walkthrough")
            self.assertEqual(video.description, "Updated product details.")
        self.assertFalse(os.path.exists(os.path.join(self.upload_folder, original_video_path)))
        self.assertFalse(os.path.exists(os.path.join(self.upload_folder, original_thumbnail_path)))
        replacement_media = self.client.get(f"/uploads/{replacement_video_path}")
        self.assertEqual(replacement_media.status_code, 200)
        replacement_media.close()

        response = self.client.post(
            f"/admin/videos/{video_id}/delete",
            data={"csrf_token": "test"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No product videos yet.", response.data)
        self.assertFalse(os.path.exists(os.path.join(self.upload_folder, replacement_video_path)))
        self.assertFalse(os.path.exists(os.path.join(self.upload_folder, replacement_thumbnail_path)))
        self.assertIn(b"Product video previews will appear here when available.", self.client.get("/").data)

    def test_card_previews_keep_full_text_for_visual_truncation(self):
        product_description = "Complete product description " * 18
        news_summary = "Complete news summary " * 18
        article_content = "<p>Complete full article text remains readable.</p>"
        with self.app.app_context():
            db.session.add(
                Product(
                    name="A very long product name " * 5,
                    slug="long-product-name",
                    description=product_description,
                    featured=True,
                    published=True,
                )
            )
            db.session.add(
                News(
                    title="A very long news headline " * 5,
                    slug="long-news-headline",
                    summary=news_summary,
                    content=article_content,
                    published=True,
                )
            )
            db.session.add(
                ProductVideo(
                    title="A very long video title " * 5,
                    description="Complete video description " * 18,
                    video_path="videos/card-preview.mp4",
                )
            )
            db.session.commit()

        homepage = self.client.get("/")
        self.assertEqual(homepage.status_code, 200)
        self.assertIn(product_description.encode(), homepage.data)
        self.assertIn(news_summary.encode(), homepage.data)
        self.assertIn(("Complete video description " * 18).encode(), homepage.data)

        products_page = self.client.get("/products")
        self.assertEqual(products_page.status_code, 200)
        self.assertIn(product_description.encode(), products_page.data)

        product_detail = self.client.get("/products/long-product-name")
        self.assertEqual(product_detail.status_code, 200)
        self.assertIn(product_description.encode(), product_detail.data)

        news_page = self.client.get("/news")
        self.assertEqual(news_page.status_code, 200)
        self.assertIn(news_summary.encode(), news_page.data)

        article_page = self.client.get("/news/long-news-headline")
        self.assertEqual(article_page.status_code, 200)
        self.assertIn(article_content.encode(), article_page.data)

        stylesheet = self.client.get("/static/css/site-extra.css")
        self.assertEqual(stylesheet.status_code, 200)
        self.assertIn(b"-webkit-line-clamp: 3", stylesheet.data)
        self.assertIn(b"-webkit-line-clamp: 2", stylesheet.data)
        self.assertIn(b"minmax(min(100%, 280px), 1fr)", stylesheet.data)
        self.assertIn(b"overflow-wrap: anywhere", stylesheet.data)

    def test_homepage_shows_latest_three_and_video_page_shows_all(self):
        with self.app.app_context():
            for index in range(5):
                db.session.add(
                    ProductVideo(
                        title=f"Collection video {index + 1}",
                        description=f"Description {index + 1}",
                        video_path=f"videos/collection-{index + 1}.mp4",
                    )
                )
            db.session.commit()
            expected = [
                video.title
                for video in ProductVideo.query.order_by(
                    ProductVideo.created_at.desc(), ProductVideo.id.desc()
                ).all()
            ]

        homepage = self.client.get("/")
        self.assertEqual(homepage.status_code, 200)
        self.assertEqual(homepage.data.count(b'data-video-player'), 3)
        for title in expected[:3]:
            self.assertIn(title.encode(), homepage.data)
        for title in expected[3:]:
            self.assertNotIn(title.encode(), homepage.data)
        self.assertIn(b'href="/videos"', homepage.data)

        all_videos = self.client.get("/videos")
        self.assertEqual(all_videos.status_code, 200)
        self.assertEqual(all_videos.data.count(b'data-video-player'), 5)
        for title in expected:
            self.assertIn(title.encode(), all_videos.data)
        self.assertIn(b"product-video-controls", all_videos.data)
        self.assertIn(b"data-video-seek", all_videos.data)

        stylesheet = self.client.get("/static/css/site-extra.css")
        self.assertEqual(stylesheet.status_code, 200)
        self.assertIn(b"grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr))", stylesheet.data)
        self.assertIn(b"aspect-ratio: 16 / 9", stylesheet.data)
        self.assertIn(b"object-fit: contain", stylesheet.data)

    def test_chunked_upload_keeps_original_bytes_and_publishes_video(self):
        original_video = b"\x00\x00\x00\x18ftypisom" + b"original-quality" * 70000
        chunk_size = 1024 * 1024
        upload_id = "23834ad5-2548-459a-90e2-d8ac51043254"
        chunks = [
            original_video[index : index + chunk_size]
            for index in range(0, len(original_video), chunk_size)
        ]

        for index, content in enumerate(chunks):
            response = self.client.post(
                "/admin/videos/upload-chunk",
                data={
                    "upload_id": upload_id,
                    "chunk_index": str(index),
                    "chunk": (io.BytesIO(content), "video.chunk"),
                },
                content_type="multipart/form-data",
            )
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
            self.assertTrue(response.json["success"])

        # A retry may resend the same chunk; it must replace it idempotently.
        retry_response = self.client.post(
            "/admin/videos/upload-chunk",
            data={
                "upload_id": upload_id,
                "chunk_index": "0",
                "chunk": (io.BytesIO(chunks[0]), "video.chunk"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(retry_response.status_code, 200)

        response = self.client.post(
            "/admin/videos/upload-complete",
            data={
                "upload_id": upload_id,
                "filename": "long-session.mp4",
                "chunk_count": str(len(chunks)),
                "title": "Long video upload",
                "description": "A chunked upload test.",
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertTrue(response.json["success"])
        self.assertEqual(response.json["message"], "Product video uploaded.")
        self.assertIn(b"Product video uploaded.", self.client.get("/admin/videos").data)

        with self.app.app_context():
            video = ProductVideo.query.one()
            self.assertEqual(video.title, "Long video upload")
            stored_path = os.path.join(self.upload_folder, video.video_path)
            with open(stored_path, "rb") as stored:
                self.assertEqual(stored.read(), original_video)

        self.assertIn(b"Long video upload", self.client.get("/").data)
        with self.app.app_context():
            published_video = ProductVideo.query.one()
            video_id = published_video.id
            old_video_path = published_video.video_path
            public_media = self.client.get(f"/uploads/{published_video.video_path}")
            self.assertEqual(public_media.status_code, 200)
            self.assertEqual(public_media.data, original_video)
            public_media.close()

        replacement_video = b"\x1a\x45\xdf\xa3" + b"replacement-bytes" * 100
        replacement_id = "5972a06e-c482-4f03-8cc7-52d48a174470"
        replacement_upload = self.client.post(
            "/admin/videos/upload-chunk",
            data={
                "upload_id": replacement_id,
                "chunk_index": "0",
                "chunk": (io.BytesIO(replacement_video), "video.chunk"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(replacement_upload.status_code, 200)
        replacement_complete = self.client.post(
            "/admin/videos/upload-complete",
            data={
                "upload_id": replacement_id,
                "filename": "replacement.webm",
                "chunk_count": "1",
                "video_id": str(video_id),
                "title": "Updated long video",
                "description": "Replacement chunk upload.",
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(replacement_complete.status_code, 200, replacement_complete.get_data(as_text=True))
        with self.app.app_context():
            updated_video = db.session.get(ProductVideo, video_id)
            self.assertEqual(updated_video.title, "Updated long video")
            self.assertNotEqual(updated_video.video_path, old_video_path)
            replacement_path = updated_video.video_path
        self.assertFalse(os.path.exists(os.path.join(self.upload_folder, old_video_path)))
        replacement_media = self.client.get(f"/uploads/{replacement_path}")
        self.assertEqual(replacement_media.status_code, 200)
        self.assertEqual(replacement_media.data, replacement_video)
        replacement_media.close()

    def test_video_management_requires_admin_and_valid_media(self):
        self.client.get("/admin/logout")
        self.assertEqual(self.client.get("/admin/videos").status_code, 302)
        self.assertEqual(
            self.client.post("/admin/videos/new").status_code,
            302,
        )
        self.login()

        response = self.client.post(
            "/admin/videos/new",
            data={
                "title": "Invalid upload",
                "description": "This should not be saved.",
                "video": (io.BytesIO(b"not a video"), "bad.mp4"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"does not match a supported", response.data)
        with self.app.app_context():
            self.assertEqual(ProductVideo.query.count(), 0)

        oversized_image_request = self.client.post(
            "/admin/products/new",
            data={
                "name": "Oversized image",
                "description": "Existing image uploads retain their request limit.",
                "image": (io.BytesIO(b"x" * (1024 * 1024 + 1)), "image.png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(oversized_image_request.status_code, 200)
        self.assertIn(b"image exceeds the image upload limit", oversized_image_request.data)
        self.assertNotIn(b"Page Not Found", oversized_image_request.data)

        oversized_chunk_index = self.client.post(
            "/admin/videos/upload-chunk",
            data={
                "upload_id": "55ec3ac1-aa01-48b3-a124-f1b154ddcb45",
                "chunk_index": "2",
                "chunk": (io.BytesIO(b"chunk"), "video.chunk"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(oversized_chunk_index.status_code, 413)
        self.assertIn("exceeds", oversized_chunk_index.json["message"])

        response = self.client.post(
            "/admin/videos/new",
            data={
                "title": "Oversized upload",
                "description": "This exceeds the configured limit.",
                "video": self.mp4_file(padding=b"x" * (2 * 1024 * 1024)),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"exceeds the 2 MB upload limit", response.data)
        with self.app.app_context():
            self.assertEqual(ProductVideo.query.count(), 0)

        request_too_large = self.client.post(
            "/admin/videos/new",
            data={
                "title": "Request too large",
                "description": "This exceeds the request body allowance.",
                "video": self.mp4_file(padding=b"x" * (4 * 1024 * 1024)),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(request_too_large.status_code, 413)
        self.assertIn(b"Upload Too Large", request_too_large.data)
        self.assertNotIn(b"Page Not Found", request_too_large.data)

if __name__ == "__main__":
    unittest.main()
