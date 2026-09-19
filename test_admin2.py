import requests
from bs4 import BeautifulSoup

session = requests.Session()
base_url = "http://127.0.0.1:5000"

# Test 1: Get login page and extract CSRF token
print("Test 1: Accessing login page and extracting CSRF token...")
r = session.get(f"{base_url}/admin/login")
print(f"  Status: {r.status_code}")
soup = BeautifulSoup(r.text, 'html.parser')
csrf_token = soup.find('input', {'name': 'csrf_token'})
if csrf_token:
    token = csrf_token.get('value')
    print(f"  ✓ CSRF token found: {token[:20]}...")
else:
    print("  ⚠ CSRF token not found in form")
    token = None

# Test 2: Login with CSRF token
if token:
    print("\nTest 2: Admin login with CSRF token...")
    r = session.post(f"{base_url}/admin/login", data={
        "username": "admin",
        "password": "Test@1234",
        "csrf_token": token
    }, allow_redirects=True)
    print(f"  Status: {r.status_code}")
    if r.status_code == 200:
        if "Dashboard" in r.text or "offers" in r.text:
            print("  ✓ Login successful, redirected to dashboard")
        else:
            print("  ⚠ Login may have failed, checking page content...")
            if "Welcome" in r.text or "Admin" in r.text:
                print("  ✓ Dashboard content visible")
            else:
                print("  ✗ No admin content found")
    else:
        print(f"  ✗ Login failed")

# Test 3: Access offers list
print("\nTest 3: Accessing offers list...")
r = session.get(f"{base_url}/admin/offers")
print(f"  Status: {r.status_code}")
if "Custom Software Development" in r.text:
    print("  ✓ Offers list loaded with data")
    # Count offers
    soup = BeautifulSoup(r.text, 'html.parser')
    rows = soup.find_all('tr')
    offer_count = len(rows) - 1  # Subtract header
    print(f"  Found {offer_count} offers in list")
else:
    print("  ✗ Offers not found or not logged in")
    if "Login" in r.text:
        print("  ⚠ Redirected to login, authentication may have failed")

print("\n✓ Tests completed!")
