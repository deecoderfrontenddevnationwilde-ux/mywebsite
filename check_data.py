import sqlite3

conn = sqlite3.connect('instance/company.db')
cursor = conn.cursor()

# Check service_offers
offers = cursor.execute("SELECT id, title, active FROM service_offers ORDER BY display_order").fetchall()
print(f"\nService Offers ({len(offers)} total):")
for offer in offers:
    print(f"  {offer[0]}. {offer[1]} (active={offer[2]})")

# Check featured_projects
projects = cursor.execute("SELECT id, title, active FROM featured_projects ORDER BY display_order").fetchall()
print(f"\nFeatured Projects ({len(projects)} total):")
for project in projects:
    print(f"  {project[0]}. {project[1]} (active={project[2]})")

conn.close()
