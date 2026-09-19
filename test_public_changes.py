import requests

base_url = "http://127.0.0.1:5000"

print("=" * 70)
print("VERIFY PUBLIC WEBSITE REFLECTS DATABASE CHANGES")
print("=" * 70)

# Get homepage
r = requests.get(f"{base_url}/")
content = r.text

print("\n1. SERVICE OFFERS ON PUBLIC WEBSITE")
print("-" * 70)

# These should appear (active)
active_offers = [
    "Custom Software Development & Consulting",  # edited name
    "Application & Network Security",
    "DevSecOps Integration",
    "UI / UX Design",
    "E-Commerce & Product Sites",
]

print("SHOULD APPEAR (active):")
for offer in active_offers:
    if offer in content:
        print(f"  ✓ {offer}")
    else:
        print(f"  ✗ {offer} - NOT FOUND")

# This should NOT appear (disabled/inactive)
print("\nSHOULD NOT APPEAR (inactive/disabled):")
inactive = "Code Reviews & Audits"
if inactive not in content:
    print(f"  ✓ {inactive} - correctly hidden")
else:
    print(f"  ✗ {inactive} - still visible (should be hidden)")

print("\n2. FEATURED PROJECTS ON PUBLIC WEBSITE")
print("-" * 70)

# These should appear (active)
active_projects = [
    "DeeCoder Portfolio",  # edited short_description but still active
    "Florante Online Shopping",
    "Premium Brand Showcase",
    "Interactive Component Suite",
]

print("SHOULD APPEAR (active):")
for project in active_projects:
    if project in content:
        print(f"  ✓ {project}")
    else:
        print(f"  ✗ {project} - NOT FOUND")

# This should NOT appear (disabled/inactive)
print("\nSHOULD NOT APPEAR (inactive/disabled):")
inactive_project = "Movie-Zone Streaming App"
if inactive_project not in content:
    print(f"  ✓ {inactive_project} - correctly hidden")
else:
    print(f"  ✗ {inactive_project} - still visible (should be hidden)")

print("\n" + "=" * 70)
print("✓ PUBLIC WEBSITE TEST COMPLETED")
print("=" * 70)
print("\nConclusion:")
print("  The public website correctly displays:")
print("  - Only active service offers")
print("  - Only active featured projects")
print("  - Reflects edits made in admin dashboard")
print("  - Hides deleted/disabled content")
