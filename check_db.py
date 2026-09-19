import sqlite3

conn = sqlite3.connect('instance/company.db')
cursor = conn.cursor()

# Get all tables
tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", [t[0] for t in tables])

# Check alembic_version
try:
    version = cursor.execute("SELECT version_num FROM alembic_version").fetchall()
    print("Alembic version:", version)
except Exception as e:
    print("No alembic_version table:", e)

conn.close()
