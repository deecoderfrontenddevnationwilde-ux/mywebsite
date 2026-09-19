import sqlite3

conn = sqlite3.connect('instance/company.db')
cursor = conn.cursor()

# Get all tables
tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print("All tables:", [t[0] for t in tables])

# Check for service_offers
service_table = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='service_offers'").fetchall()
print("service_offers table exists:", bool(service_table))

# Check for featured_projects
project_table = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='featured_projects'").fetchall()
print("featured_projects table exists:", bool(project_table))

conn.close()
