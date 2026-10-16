import os
import tempfile
import unittest
import uuid
from unittest.mock import patch

from app import create_app
from config import Config
from extensions import db
from models import AdminUser, ContactMessage, ContactMessageActivity


class ContactInboxTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = os.path.join(self.temp_dir.name, "inbox.sqlite3")

        class TestConfig(Config):
            TESTING = True
            WTF_CSRF_ENABLED = False
            SECRET_KEY = "contact-inbox-test-secret"
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{database_path}"
            UPLOAD_FOLDER = os.path.join(self.temp_dir.name, "uploads")

        self.app = create_app(TestConfig)
        with self.app.app_context():
            db.create_all()
            admin = AdminUser(username="inbox-admin", email="inbox-admin@example.com")
            admin.set_password("test-password")
            db.session.add(admin)
            db.session.commit()
            self.admin_id = admin.id
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["admin_id"] = self.admin_id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def add_message(self, *, name="Visitor One", email="visitor@example.net", subject="Project"):
        message = ContactMessage(
            name=name,
            email=email,
            subject=subject,
            message="Please contact me about a project.",
        )
        db.session.add(message)
        db.session.commit()
        return message

    def test_inbox_search_filters_and_paginates(self):
        with self.app.app_context():
            self.add_message()
            self.add_message(name="Another Visitor", email="other@example.net", subject="Other")

        response = self.client.get("/admin/messages?q=visitor%40example.net")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Visitor One", response.data)
        self.assertNotIn(b"Another Visitor", response.data)

        response = self.client.get("/admin/messages?status=ACCEPTED")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No messages match these filters.", response.data)

    def test_message_pagination_and_reply_filter(self):
        with self.app.app_context():
            oldest = self.add_message(name="Oldest visitor")
            oldest_id = oldest.id
            for index in range(20):
                self.add_message(name=f"Visitor {index}")
            oldest.activities.append(
                ContactMessageActivity(
                    event_type=ContactMessageActivity.TYPE_ADMIN_REPLY,
                    body="Reply",
                    email_status=ContactMessageActivity.EMAIL_ACCEPTED,
                    attempt_count=1,
                )
            )
            db.session.commit()

        second_page = self.client.get("/admin/messages?page=2")
        self.assertEqual(second_page.status_code, 200)
        self.assertIn(b"Page 2 of 2", second_page.data)
        self.assertIn(b"Oldest visitor", second_page.data)

        replied = self.client.get("/admin/messages?tab=replied")
        self.assertEqual(replied.status_code, 200)
        self.assertIn(b"Oldest visitor", replied.data)
        self.assertNotIn(b"Visitor 19", replied.data)
        with self.app.app_context():
            self.assertEqual(
                db.session.get(ContactMessage, oldest_id).activities[-1].email_status,
                ContactMessageActivity.EMAIL_ACCEPTED,
            )

    def test_detail_marks_read_and_message_can_be_archived_and_restored(self):
        with self.app.app_context():
            message = self.add_message()
            message_id = message.id

        response = self.client.get(f"/admin/messages/{message_id}")
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertTrue(db.session.get(ContactMessage, message_id).is_read)

        in_progress = self.client.post(
            f"/admin/messages/{message_id}/status",
            data={"status": "IN_PROGRESS"},
        )
        self.assertEqual(in_progress.status_code, 302)
        with self.app.app_context():
            message = db.session.get(ContactMessage, message_id)
            self.assertEqual(message.status, ContactMessage.STATUS_IN_PROGRESS)
            self.assertTrue(message.is_read)
            self.assertTrue(
                ContactMessageActivity.query.filter_by(
                    event_type=ContactMessageActivity.TYPE_STATUS_CHANGED
                ).count()
            )

        marked_unread = self.client.post(
            f"/admin/messages/{message_id}/read",
            data={"is_read": "0"},
        )
        self.assertEqual(marked_unread.status_code, 302)
        with self.app.app_context():
            message = db.session.get(ContactMessage, message_id)
            self.assertEqual(message.status, ContactMessage.STATUS_IN_PROGRESS)
            self.assertFalse(message.is_read)

        archived = self.client.post(
            f"/admin/messages/{message_id}/archive",
            data={"archived": "1"},
        )
        self.assertEqual(archived.status_code, 302)
        self.assertIn("archived=1", archived.location)
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(ContactMessage, message_id).archived_at)
        self.assertIn(b"Visitor One", self.client.get("/admin/messages?folder=all").data)
        self.assertNotIn(b"Visitor One", self.client.get("/admin/messages?folder=inbox").data)
        self.assertIn(b"Visitor One", self.client.get("/admin/messages?folder=archive").data)

        restored = self.client.post(
            f"/admin/messages/{message_id}/archive",
            data={"archived": "0"},
        )
        self.assertEqual(restored.status_code, 302)
        with self.app.app_context():
            self.assertIsNone(db.session.get(ContactMessage, message_id).archived_at)

    @patch("routes.admin.send_contact_approval_notification", side_effect=[False, True])
    def test_acceptance_persists_failed_notice_and_retry_history(self, send_notice):
        with self.app.app_context():
            message = self.add_message()
            message_id = message.id

        response = self.client.post(
            f"/admin/messages/{message_id}/approve",
            data={
                "admin_note": "We can discuss the project.",
                "request_token": str(uuid.uuid4()),
            },
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            message = db.session.get(ContactMessage, message_id)
            self.assertEqual(message.status, ContactMessage.STATUS_ACCEPTED)
            activity = ContactMessageActivity.query.filter_by(
                event_type=ContactMessageActivity.TYPE_REQUEST_ACCEPTED
            ).one()
            self.assertEqual(activity.email_status, ContactMessageActivity.EMAIL_FAILED)
            self.assertEqual(activity.attempt_count, 1)
            activity_id = activity.id

        response = self.client.post(
            f"/admin/messages/{message_id}/activities/{activity_id}/retry"
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            activity = db.session.get(ContactMessageActivity, activity_id)
            self.assertEqual(activity.email_status, ContactMessageActivity.EMAIL_ACCEPTED)
            self.assertEqual(activity.attempt_count, 2)
            self.assertIsNotNone(activity.accepted_at)
        self.assertEqual(send_notice.call_count, 2)

    @patch("routes.admin.send_contact_admin_reply", side_effect=[False, True])
    def test_reply_is_persisted_on_failure_and_retry_does_not_duplicate(self, send_reply):
        with self.app.app_context():
            message = self.add_message()
            message_id = message.id

        token = str(uuid.uuid4())
        self.client.post(
            f"/admin/messages/{message_id}/reply",
            data={
                "reply": "Thank you, we will respond soon.",
                "recipient_email": "reply@example.org",
                "email_subject": "Re: Project",
                "request_token": token,
            },
        )
        with self.app.app_context():
            activity = ContactMessageActivity.query.filter_by(
                event_type=ContactMessageActivity.TYPE_ADMIN_REPLY
            ).one()
            self.assertEqual(activity.body, "Thank you, we will respond soon.")
            self.assertEqual(activity.recipient_email, "reply@example.org")
            self.assertEqual(activity.email_subject, "Re: Project")
            self.assertEqual(activity.email_status, ContactMessageActivity.EMAIL_FAILED)
            activity_id = activity.id

        self.client.post(
            f"/admin/messages/{message_id}/activities/{activity_id}/retry"
        )
        self.client.post(
            f"/admin/messages/{message_id}/activities/{activity_id}/retry"
        )
        with self.app.app_context():
            activity = db.session.get(ContactMessageActivity, activity_id)
            self.assertEqual(activity.email_status, ContactMessageActivity.EMAIL_ACCEPTED)
            self.assertEqual(activity.attempt_count, 2)
        self.assertEqual(send_reply.call_count, 2)
        self.assertEqual(send_reply.call_args_list[0].kwargs["recipient_email"], "reply@example.org")
        self.assertEqual(send_reply.call_args_list[0].kwargs["subject"], "Re: Project")
        detail = self.client.get(f"/admin/messages/{message_id}")
        self.assertIn(b"Thank you, we will respond soon.", detail.data)

    @patch("routes.admin.send_contact_admin_reply")
    def test_reply_rejects_invalid_recipient_and_header_injection(self, send_reply):
        with self.app.app_context():
            message = self.add_message()
            message_id = message.id

        for recipient, subject in (
            ("not-an-email", "Re: Project"),
            ("visitor@example.net", "Re: Project\r\nBcc: attacker@example.org"),
        ):
            response = self.client.post(
                f"/admin/messages/{message_id}/reply",
                data={
                    "reply": "A valid reply body.",
                    "recipient_email": recipient,
                    "email_subject": subject,
                    "request_token": str(uuid.uuid4()),
                },
            )
            self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertEqual(ContactMessageActivity.query.filter_by(
                event_type=ContactMessageActivity.TYPE_ADMIN_REPLY
            ).count(), 0)
        send_reply.assert_not_called()

    def test_bulk_trash_restore_and_permanent_delete_only_affect_selected_messages(self):
        with self.app.app_context():
            first = self.add_message(name="First")
            second = self.add_message(name="Second")
            untouched = self.add_message(name="Untouched")
            first_id, second_id, untouched_id = first.id, second.id, untouched.id

        response = self.client.post(
            "/admin/messages/bulk",
            data={"message_ids": [str(first_id), str(second_id)], "action": "trash"},
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(ContactMessage, first_id).deleted_at)
            self.assertIsNotNone(db.session.get(ContactMessage, second_id).deleted_at)
            self.assertIsNone(db.session.get(ContactMessage, untouched_id).deleted_at)

        restored = self.client.post(
            f"/admin/messages/{first_id}/restore",
        )
        self.assertEqual(restored.status_code, 302)
        with self.app.app_context():
            self.assertIsNone(db.session.get(ContactMessage, first_id).deleted_at)
            self.assertIsNotNone(db.session.get(ContactMessage, second_id).deleted_at)

        deleted = self.client.post(
            "/admin/messages/bulk",
            data={"message_ids": [str(second_id)], "action": "delete_permanently"},
        )
        self.assertEqual(deleted.status_code, 302)
        with self.app.app_context():
            self.assertIsNone(db.session.get(ContactMessage, second_id))
            self.assertIsNotNone(db.session.get(ContactMessage, untouched_id))

    def test_priority_internal_note_and_history_are_saved(self):
        with self.app.app_context():
            message = self.add_message()
            message_id = message.id

        self.client.post(
            f"/admin/messages/{message_id}/priority",
            data={"priority": "URGENT"},
        )
        self.client.post(
            f"/admin/messages/{message_id}/note",
            data={"internal_note": "Call after 3pm; do not email this note."},
        )
        with self.app.app_context():
            message = db.session.get(ContactMessage, message_id)
            self.assertEqual(message.priority, "URGENT")
            self.assertEqual(message.internal_note, "Call after 3pm; do not email this note.")
            self.assertEqual(
                ContactMessageActivity.query.filter_by(
                    event_type=ContactMessageActivity.TYPE_PRIORITY_CHANGED
                ).count(),
                1,
            )
            self.assertEqual(
                ContactMessageActivity.query.filter_by(
                    event_type=ContactMessageActivity.TYPE_NOTE_UPDATED
                ).count(),
                1,
            )

        detail = self.client.get(f"/admin/messages/{message_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b"do not email this note", detail.data)

    @patch("routes.admin.send_contact_declined_notification", return_value=True)
    @patch("routes.admin.send_contact_approval_notification", return_value=True)
    def test_decision_can_be_changed_and_each_change_is_audited(self, approval, decline):
        with self.app.app_context():
            message = self.add_message()
            message_id = message.id

        approved = self.client.post(
            f"/admin/messages/{message_id}/approve",
            data={
                "request_token": str(uuid.uuid4()),
                "admin_note": "",
                "internal_note": "Assigned to the sales team.",
            },
        )
        declined = self.client.post(
            f"/admin/messages/{message_id}/decline",
            data={"request_token": str(uuid.uuid4()), "admin_note": ""},
        )
        self.assertEqual(approved.status_code, 302)
        self.assertEqual(declined.status_code, 302)
        with self.app.app_context():
            message = db.session.get(ContactMessage, message_id)
            self.assertEqual(message.status, ContactMessage.STATUS_REJECTED)
            self.assertEqual(message.internal_note, "Assigned to the sales team.")
            self.assertEqual(approval.call_count, 1)
            self.assertEqual(decline.call_count, 1)
            changes = [
                activity.body
                for activity in ContactMessageActivity.query.filter_by(
                    event_type=ContactMessageActivity.TYPE_STATUS_CHANGED
                ).all()
            ]
            self.assertTrue(any("to Accepted" in change for change in changes))
            self.assertTrue(any("to Declined" in change for change in changes))

    @patch("routes.admin.send_contact_declined_notification")
    @patch("routes.admin.send_contact_approval_notification")
    def test_bulk_decisions_are_audited_without_sending_email(self, approval, decline):
        with self.app.app_context():
            first = self.add_message(name="First")
            second = self.add_message(name="Second")
            first_id, second_id = first.id, second.id

        response = self.client.post(
            "/admin/messages/bulk",
            data={"message_ids": [str(first_id), str(second_id)], "action": "approve"},
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertEqual(
                db.session.get(ContactMessage, first_id).status,
                ContactMessage.STATUS_ACCEPTED,
            )
            self.assertEqual(
                db.session.get(ContactMessage, second_id).status,
                ContactMessage.STATUS_ACCEPTED,
            )
            self.assertEqual(
                ContactMessageActivity.query.filter_by(
                    event_type=ContactMessageActivity.TYPE_STATUS_CHANGED
                ).count(),
                2,
            )
        approval.assert_not_called()
        decline.assert_not_called()

    def test_contact_messages_are_not_public_and_require_admin_authentication(self):
        client = self.app.test_client()
        response = client.get("/admin/messages")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login", response.location)
        post_response = client.post(
            "/admin/messages/bulk",
            data={"message_ids": ["1"], "action": "trash"},
        )
        self.assertEqual(post_response.status_code, 302)
        with self.app.app_context():
            self.assertEqual(ContactMessage.query.count(), 0)

    def test_sensitive_message_mutations_require_csrf(self):
        with self.app.app_context():
            message = self.add_message()
            message_id = message.id

        self.app.config["WTF_CSRF_ENABLED"] = True
        response = self.client.post(f"/admin/messages/{message_id}/trash")
        self.assertEqual(response.status_code, 400)
        with self.app.app_context():
            self.assertIsNone(db.session.get(ContactMessage, message_id).deleted_at)


if __name__ == "__main__":
    unittest.main()
