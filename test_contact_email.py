import os
import tempfile
import unittest
import uuid
from email import message_from_string
from unittest.mock import patch

from app import create_app
from config import Config
from extensions import db
from models import ContactMessage, ContactMessageActivity
from services.email_service import (
    send_contact_admin_reply,
    send_email,
    send_new_contact_notification,
)


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
            SMTP_USE_SSL = False

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
        response = self.client.post("/api/contact", json=self.payload(phone="+234 800 123 4567"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        notification.assert_called_once()
        confirmation.assert_called_once()
        with self.app.app_context():
            contact = ContactMessage.query.one()
            self.assertEqual(contact.email, "sender@example.net")
            self.assertEqual(contact.phone, "+234 800 123 4567")
            self.assertEqual(len(contact.request_fingerprint), 64)
            activities = {activity.event_type: activity for activity in contact.activities}
            self.assertEqual(
                activities[ContactMessageActivity.TYPE_BUSINESS_NOTIFICATION].email_status,
                ContactMessageActivity.EMAIL_ACCEPTED,
            )
            self.assertEqual(
                activities[ContactMessageActivity.TYPE_SUBMISSION_CONFIRMATION].email_status,
                ContactMessageActivity.EMAIL_ACCEPTED,
            )

    @patch("routes.api.send_contact_submission_confirmation")
    @patch("routes.api.send_new_contact_notification", return_value=False)
    def test_notification_failure_is_not_reported_as_success(self, notification, confirmation):
        response = self.client.post("/api/contact", json=self.payload())

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json["success"])
        self.assertTrue(response.json["saved"])
        confirmation.assert_not_called()
        notification.assert_called_once()
        with self.app.app_context():
            activity = ContactMessageActivity.query.filter_by(
                event_type=ContactMessageActivity.TYPE_BUSINESS_NOTIFICATION
            ).one()
            self.assertEqual(activity.email_status, ContactMessageActivity.EMAIL_FAILED)
            self.assertEqual(activity.attempt_count, 1)

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

    @patch("routes.api.send_contact_submission_confirmation", return_value=True)
    @patch("routes.api.send_new_contact_notification")
    def test_reusing_submission_token_with_changed_content_is_rejected(
        self, notification, confirmation
    ):
        payload = self.payload()
        first = self.client.post("/api/contact", json=payload)
        changed = dict(payload, message="Changed content")

        response = self.client.post("/api/contact", json=changed)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(response.status_code, 409)
        notification.assert_called_once()
        confirmation.assert_called_once()

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

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json["success"])
        self.assertTrue(response.json["notification_sent"])
        self.assertIn("couldn't send your confirmation email", response.json["message"])
        notification.assert_called_once()
        confirmation.assert_called_once()

    @patch("routes.api.send_contact_submission_confirmation", side_effect=[False, True])
    @patch("routes.api.send_new_contact_notification", return_value=True)
    def test_retry_after_confirmation_failure_does_not_resend_business_notification(
        self, notification, confirmation
    ):
        payload = self.payload()
        first = self.client.post("/api/contact", json=payload)
        retry = self.client.post("/api/contact", json=payload)

        self.assertEqual(first.status_code, 503)
        self.assertEqual(retry.status_code, 200)
        self.assertTrue(retry.json["success"])
        notification.assert_called_once()
        confirmation.assert_has_calls([unittest.mock.call(unittest.mock.ANY)] * 2)

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
            self.payload(subject=""),
            self.payload(submission_token="invalid-token"),
            self.payload(name=""),
            self.payload(email="not-an-email"),
            self.payload(message=""),
            self.payload(phone="call me maybe"),
            self.payload(phone="1" * 51),
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
            smtp_ssl.return_value.__enter__.return_value.sendmail.return_value = {}
            self.assertTrue(send_email("recipient@example.com", "Test", "<p>Test</p>", "Test"))

        smtp_ssl.assert_called_once()
        smtp_ssl.return_value.__enter__.return_value.login.assert_called_once_with(
            "sender@example.com", "not-a-real-password"
        )
        smtp_ssl.return_value.__enter__.return_value.sendmail.assert_called_once()

    @patch("services.email_service.send_email", return_value=True)
    def test_contact_notification_uses_business_inbox_reply_to_and_optional_phone(self, send):
        contact = ContactMessage(
            name="Test Sender",
            email="sender@example.net",
            phone="+234 800 123 4567",
            subject="A test",
            message="A test message",
        )

        with self.app.app_context():
            self.assertTrue(send_new_contact_notification(contact))

        self.assertEqual(
            send.call_args.args[0],
            "deecodertechnologiesworldwide@gmail.com",
        )
        self.assertEqual(send.call_args.kwargs["reply_to"], "sender@example.net")
        self.assertIn("+234 800 123 4567", send.call_args.kwargs["text_body"])

    @patch("services.email_service.send_email", return_value=True)
    def test_admin_reply_is_sent_to_visitor_with_escaped_html(self, send):
        contact = ContactMessage(
            name="Visitor",
            email="visitor@example.net",
            subject="Question",
            message="Original question",
        )
        with self.app.app_context():
            self.assertTrue(send_contact_admin_reply(contact, "<script>alert(1)</script>\nThanks"))

        self.assertEqual(send.call_args.args[0], "visitor@example.net")
        self.assertIn("&lt;script&gt;", send.call_args.args[2])
        self.assertNotIn("<script>", send.call_args.args[2])
        self.assertIn("<br>", send.call_args.args[2])

    def test_both_forms_share_the_real_endpoint_and_required_fields(self):
        for page, form_id in (("/", "homepage-contact-form"), ("/contact", "contact-page-form")):
            with self.subTest(page=page):
                response = self.client.get(page)
                self.assertEqual(response.status_code, 200)
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(response.data, "html.parser")
                form = soup.find("form", id=form_id)
                self.assertIsNotNone(form)
                self.assertEqual(form["data-endpoint"], "/api/contact")
                for field_name in ("name", "email", "subject", "message"):
                    self.assertIsNotNone(form.find(attrs={"name": field_name, "required": True}))
                self.assertIsNotNone(form.find(attrs={"name": "phone"}))
                self.assertIsNone(form.find(attrs={"name": "phone", "required": True}))
                self.assertIn("aria-live", form.find(attrs={"role": "status"}).attrs)

    @patch("routes.api.send_contact_submission_confirmation")
    @patch("routes.api.send_new_contact_notification")
    def test_contact_endpoint_rejects_missing_csrf_when_enabled(self, notification, confirmation):
        self.app.config["WTF_CSRF_ENABLED"] = True
        missing_token = self.client.post("/api/contact", json=self.payload())
        self.assertEqual(missing_token.status_code, 400)
        self.assertFalse(missing_token.json["success"])
        notification.assert_not_called()
        confirmation.assert_not_called()

    @patch("routes.api.send_contact_submission_confirmation", return_value=True)
    @patch("routes.api.send_new_contact_notification", return_value=True)
    def test_contact_endpoint_accepts_csrf_from_rendered_form(self, notification, confirmation):
        self.app.config["WTF_CSRF_ENABLED"] = True
        from bs4 import BeautifulSoup

        page = BeautifulSoup(self.client.get("/contact").data, "html.parser")
        csrf_token = page.select_one("#contact-page-form input[name='csrf_token']")["value"]
        response = self.client.post(
            "/api/contact",
            json=self.payload(),
            headers={"X-CSRFToken": csrf_token},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        notification.assert_called_once()
        confirmation.assert_called_once()

    @patch("services.email_service.smtplib.SMTP_SSL")
    def test_smtp_refusal_is_not_reported_as_accepted(self, smtp_ssl):
        with self.app.app_context():
            self.app.config["SMTP_USE_SSL"] = True
            self.app.config["SMTP_PORT"] = 465
            smtp = smtp_ssl.return_value.__enter__.return_value
            smtp.sendmail.return_value = {"recipient@example.com": (550, b"rejected")}
            self.assertFalse(
                send_email("recipient@example.com", "Test", "<p>Test</p>", "Test")
            )
            sent_message = smtp.sendmail.call_args.args[2]
            self.assertNotIn("Reply-To:", sent_message)

    @patch("services.email_service.smtplib.SMTP")
    def test_contact_submission_uses_real_smtp_service_for_both_messages(self, smtp_factory):
        smtp = smtp_factory.return_value
        smtp.__enter__.return_value = smtp
        smtp.sendmail.return_value = {}

        response = self.client.post(
            "/api/contact",
            json=self.payload(phone="+234 800 123 4567"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertEqual(smtp.sendmail.call_count, 2)
        self.assertEqual(smtp.login.call_count, 2)
        self.assertEqual(smtp.starttls.call_count, 2)

        submissions = [
            (call.args[0], call.args[1], message_from_string(call.args[2]))
            for call in smtp.sendmail.call_args_list
        ]
        notification = next(
            message for _, recipients, message in submissions
            if recipients == ["deecodertechnologiesworldwide@gmail.com"]
        )
        confirmation = next(
            message for _, recipients, message in submissions
            if recipients == ["sender@example.net"]
        )
        self.assertEqual(notification["Reply-To"], "sender@example.net")
        self.assertEqual(notification["From"], "DeeCoder Technologies <sender@example.com>")
        self.assertEqual(confirmation["To"], "sender@example.net")
        self.assertIsNone(confirmation["Reply-To"])
        notification_body = notification.get_payload()[0].get_payload(decode=True).decode()
        self.assertIn("+234 800 123 4567", notification_body)
