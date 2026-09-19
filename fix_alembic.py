import sqlite3

conn = sqlite3.connect('instance/company.db')
cursor = conn.cursor()

# Update the alembic version to the current migration
cursor.execute("DELETE FROM alembic_version")
cursor.execute("INSERT INTO alembic_version (version_num) VALUES ('20260912_content_management')")
conn.commit()

print("Updated alembic_version to 20260912_content_management")

# Check the update
version = cursor.execute("SELECT version_num FROM alembic_version").fetchall()
print("New version:", version)

conn.close()
