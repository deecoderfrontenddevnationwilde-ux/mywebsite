import requests

base_url = "http://127.0.0.1:5000"

# Test public homepage
print("Testing public homepage...")
r = requests.get(f"{base_url}/")
print(f"Status: {r.status_code}")

# Check for service offers
offers = [
    "Custom Software Development",
    "Application & Network Security",
    "DevSecOps Integration",
    "UI / UX Design",
    "E-Commerce & Product Sites",
    "Code Reviews & Audits"
]

print("\nService Offers on homepage:")
for offer in offers:
    if offer in r.text:
        print(f"  ✓ {offer}")
    else:
        print(f"  ✗ {offer} NOT FOUND")

# Check for featured projects
projects = [
    "DeeCoder Portfolio",
    "Florante Online Shopping",
    "Movie-Zone Streaming App",
    "Premium Brand Showcase",
    "Interactive Component Suite"
]

print("\nFeatured Projects on homepage:")
for project in projects:
    if project in r.text:
        print(f"  ✓ {project}")
    else:
        print(f"  ✗ {project} NOT FOUND")
