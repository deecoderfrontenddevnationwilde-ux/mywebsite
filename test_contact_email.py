import os
import tempfile
import unittest
import uuid
from unittest.mock import patch

from app import create_app
from config import Config
from extensions import db
from models import ContactMessage
from services.email_service import send_email, send_new_contact_notification


class ContactEmailTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = os.path.join(self.temp_dir.name, "contact.sqlite3")

        class TestConfig(Config):
            TESTING = True
            WTF_CSRF_ENABLED = False
            SECRET_KEY = "contact-test-secret"
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{database_path}"
            UPLOAD_FOLDER = os.path.join(self.temp_dir.name, "uploads")
            GMAIL_ADDRESS = "sender@example.com"
            GMAIL_APP_PASSWORD = "not-a-real-password"
            NOTIFICATION_EMAIL = "deecodertechnologiesworldwide@gmail.com"
            CONTACT_NOTIFICATION_EMAIL = "deecodertechnologiesworldwide@gmail.com"

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        self.temp_dir.cleanup()

    @staticmethod
    def payload(**overrides):
        values = {
            "name": "Test Sender",
            "email": "sender@example.net",
            "subject": "Web Development",
            "message": "Please contact me about a test project.",
            "contact_reference_code": "",
            "submission_token": str(uuid.uuid4()),
        }
        values.update(overrides)
        return values

    @patch("routes.api.send_contact_submission_confirmation", return_value=True)
    @patch("routes.api.send_new_contact_notification", return_value=True)
    def test_valid_submission_is_saved_and_sends_both_emails(self, notification, confirmation):
        response = self.client.post("/api/contact", json=self.payload(subject=None, service=None))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        notification.assert_called_once()
        confirmation.assert_called_once()
        with self.app.app_context():
            contact = ContactMessage.query.one()
            self.assertEqual(contact.email, "sender@example.net")
            self.assertEqual(len(contact.request_fingerprint), 64)

    @patch("routes.api.send_contact_submission_confirmation")
    @patch("routes.api.send_new_contact_notification", return_value=False)
    def test_notification_failure_is_not_reported_as_success(self, notification, confirmation):
        response = self.client.post("/api/contact", json=self.payload())

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json["success"])
        self.assertTrue(response.json["saved"])
        confirmation.assert_not_called()
        notification.assert_called_once()

    @patch("routes.api.send_contact_submission_confirmation", return_value=True)
    @patch("routes.api.send_new_contact_notification", side_effect=[False, True])
    def test_retry_reuses_saved_submission_and_retries_only_unaccepted_notification(
        self, notification, confirmation
    ):
        payload = self.payload()
        first = self.client.post("/api/contact", json=payload)
        retry = self.client.post("/api/contact", json=payload)

        self.assertEqual(first.status_code, 503)
        self.assertEqual(retry.status_code, 200)
        self.assertTrue(retry.json["success"])
        notification.assert_has_calls([unittest.mock.call(unittest.mock.ANY)] * 2)
        confirmation.assert_called_once()
        with self.app.app_context():
            self.assertEqual(ContactMessage.query.count(), 1)

    @patch("routes.api.send_new_contact_notification")
    def test_reusing_submission_token_with_changed_content_is_rejected(self, notification):
        payload = self.payload()
        first = self.client.post("/api/contact", json=payload)
        changed = dict(payload, message="Changed content")

        response = self.client.post("/api/contact", json=changed)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(response.status_code, 409)
        notification.assert_called_once()

    @patch("routes.api.send_contact_submission_confirmation", return_value=True)
    @patch("routes.api.send_new_contact_notification", return_value=True)
    def test_replay_of_successful_submission_does_not_send_duplicate_emails(
        self, notification, confirmation
    ):
        payload = self.payload()
        first = self.client.post("/api/contact", json=payload)
        replay = self.client.post("/api/contact", json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.status_code, 200)
        notification.assert_called_once()
        confirmation.assert_called_once()
        with self.app.app_context():
            self.assertEqual(ContactMessage.query.count(), 1)

    @patch("routes.api.send_contact_submission_confirmation", return_value=False)
    @patch("routes.api.send_new_contact_notification", return_value=True)
    def test_confirmation_failure_is_reported_without_claiming_confirmation(self, notification, confirmation):
        response = self.client.post("/api/contact", json=self.payload())

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertIn("couldn't send a confirmation", response.json["message"])
        notification.assert_called_once()
        confirmation.assert_called_once()

    @patch("routes.api.send_contact_submission_confirmation")
    @patch("routes.api.send_new_contact_notification")
    def test_missing_and_malformed_fields_are_rejected(self, notification, confirmation):
        non_json = self.client.post("/api/contact", data=self.payload())
        self.assertEqual(non_json.status_code, 415)

        for payload in (
            {},
            [],
            self.payload(name=[]),
            self.payload(subject=["not", "text"]),
            self.payload(submission_token="invalid-token"),
            self.payload(name=""),
            self.payload(email="not-an-email"),
            self.payload(message=""),
            self.payload(subject="x" * 201),
            self.payload(message="x" * 5001),
        ):
            with self.subTest(payload=payload):
                response = self.client.post("/api/contact", json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.json["success"])
        notification.assert_not_called()
        confirmation.assert_not_called()

    @patch("routes.api.send_contact_submission_confirmation")
    @patch("routes.api.send_new_contact_notification")
    def test_honeypot_and_rate_limit_block_unwanted_submissions(self, notification, confirmation):
        response = self.client.post(
            "/api/contact",
            json=self.payload(contact_reference_code="spam"),
        )
        self.assertEqual(response.status_code, 400)

        with patch("routes.api.CONTACT_RATE_LIMIT", 1):
            first = self.client.post("/api/contact", json=self.payload(website="https://example.net"))
            second = self.client.post("/api/contact", json=self.payload(website="https://example.net"))
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        notification.assert_called_once()
        confirmation.assert_called_once()

    @patch("services.email_service.smtplib.SMTP_SSL")
    def test_smtp_submission_uses_configured_recipient_and_tls_without_network(self, smtp_ssl):
        with self.app.app_context():
            self.app.config["SMTP_HOST"] = "smtp.gmail.com"
            self.app.config["SMTP_PORT"] = 465
            self.app.config["SMTP_USE_SSL"] = True
            self.assertTrue(send_email("recipient@example.com", "Test", "<p>Test</p>", "Test"))

        smtp_ssl.assert_called_once()
        smtp_ssl.return_value.__enter__.return_value.login.assert_called_once_with(
            "sender@example.com", "not-a-real-password"
        )
        smtp_ssl.return_value.__enter__.return_value.sendmail.assert_called_once()

    @patch("services.email_service.send_email", return_value=True)
    def test_contact_notification_uses_configured_notification_inbox(self, send):
        contact = ContactMessage(
            name="Test Sender",
            email="sender@example.net",
            subject="A test",
            message="A test message",
        )

        with self.app.app_context():
            self.assertTrue(send_new_contact_notification(contact))

        self.assertEqual(
            send.call_args.args[0],
            "deecodertechnologiesworldwide@gmail.com",
        )
