import requests
from requests.exceptions import RequestException

session = requests.Session()
base_url = "http://127.0.0.1:5000"

# Test 1: Access login page
print("Test 1: Accessing login page...")
r = session.get(f"{base_url}/admin/login")
print(f"  Status: {r.status_code}")
if "login" in r.text.lower():
    print("  ✓ Login page loaded")
else:
    print("  ✗ Login page not found")

# Test 2: Login
print("\nTest 2: Admin login...")
r = session.post(f"{base_url}/admin/login", data={
    "username": "admin",
    "password": "Test@1234"
})
print(f"  Status: {r.status_code}")
if r.status_code in [200, 302]:
    print("  ✓ Login request processed")
else:
    print(f"  ✗ Login failed with status {r.status_code}")

# Test 3: Access dashboard
print("\nTest 3: Accessing dashboard...")
r = session.get(f"{base_url}/admin/dashboard")
print(f"  Status: {r.status_code}")
if "Dashboard" in r.text or "Admin" in r.text:
    print("  ✓ Dashboard loaded")
else:
    print("  ✗ Dashboard not found")

# Test 4: Access offers list
print("\nTest 4: Accessing offers list...")
r = session.get(f"{base_url}/admin/offers")
print(f"  Status: {r.status_code}")
if "Custom Software Development" in r.text:
    print("  ✓ Offers list loaded with data")
else:
    print("  ✗ Offers not found")

# Test 5: Access projects list
print("\nTest 5: Accessing projects list...")
r = session.get(f"{base_url}/admin/projects")
print(f"  Status: {r.status_code}")
if "DeeCoder Portfolio" in r.text:
    print("  ✓ Projects list loaded with data")
else:
    print("  ✗ Projects not found")

print("\n✓ All tests completed!")
