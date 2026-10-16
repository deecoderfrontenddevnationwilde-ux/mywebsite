import importlib.util
import unittest
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations" / "versions"


def load_migration(filename):
    path = MIGRATIONS_DIR / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


class ContactPhoneMigrationTests(unittest.TestCase):
    def run_migration(self, migration, connection, direction="upgrade"):
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            getattr(migration, direction)()

    def create_legacy_contact_table(self, connection):
        connection.exec_driver_sql(
            """
            CREATE TABLE contact_messages (
                id INTEGER PRIMARY KEY,
                name VARCHAR(150) NOT NULL,
                email VARCHAR(255) NOT NULL,
                status VARCHAR(20) NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            "INSERT INTO contact_messages (id, name, email, status) "
            "VALUES (1, 'Existing contact', 'contact@example.com', 'PENDING')"
        )

    def assert_phone_column_is_nullable(self, connection):
        column = next(
            column
            for column in sa.inspect(connection).get_columns("contact_messages")
            if column["name"] == "phone"
        )
        self.assertEqual(column["type"].length, 50)
        self.assertTrue(column["nullable"])

    def test_original_phone_migration_adds_column_and_is_repeatable(self):
        migration = load_migration("20261016_contact_phone.py")
        engine = sa.create_engine("sqlite://")
        with engine.begin() as connection:
            self.create_legacy_contact_table(connection)
            self.run_migration(migration, connection)
            self.run_migration(migration, connection)

            self.assert_phone_column_is_nullable(connection)
            row = connection.exec_driver_sql(
                "SELECT id, name, phone FROM contact_messages WHERE id = 1"
            ).one()
            self.assertEqual(row, (1, "Existing contact", None))

            self.run_migration(migration, connection, direction="downgrade")
            self.assertNotIn(
                "phone",
                {column["name"] for column in sa.inspect(connection).get_columns("contact_messages")},
            )
        engine.dispose()

    def test_reconciliation_migration_repairs_stamped_schema_without_data_loss(self):
        migration = load_migration("20261016_reconcile_contact_phone.py")
        engine = sa.create_engine("sqlite://")
        with engine.begin() as connection:
            self.create_legacy_contact_table(connection)
            self.run_migration(migration, connection)
            self.run_migration(migration, connection)

            self.assert_phone_column_is_nullable(connection)
            row = connection.exec_driver_sql(
                "SELECT id, name, status, phone FROM contact_messages WHERE id = 1"
            ).one()
            self.assertEqual(row, (1, "Existing contact", "PENDING", None))
            count = connection.exec_driver_sql(
                "SELECT COUNT(*) FROM contact_messages WHERE status = 'PENDING'"
            ).scalar_one()
            self.assertEqual(count, 1)
        engine.dispose()

    def test_reconciliation_does_not_remove_an_existing_phone_column(self):
        migration = load_migration("20261016_reconcile_contact_phone.py")
        engine = sa.create_engine("sqlite://")
        with engine.begin() as connection:
            self.create_legacy_contact_table(connection)
            connection.exec_driver_sql(
                "ALTER TABLE contact_messages ADD COLUMN phone VARCHAR(50)"
            )
            connection.exec_driver_sql(
                "UPDATE contact_messages SET phone = '+1 555 0100' WHERE id = 1"
            )
            self.run_migration(migration, connection)

            phone = connection.exec_driver_sql(
                "SELECT phone FROM contact_messages WHERE id = 1"
            ).scalar_one()
            self.assertEqual(phone, "+1 555 0100")
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
