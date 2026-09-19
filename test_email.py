"""
Standalone Gmail SMTP test — run this directly to check whether your
Gmail credentials work, completely separate from the Flask app.

Usage (from the company_website project folder, with your .env filled in):

    python test_email.py your-real-test-email@example.com
xIf this script fails, the problem is your Gmail setup (not the Flask app).
If this script succeeds but the website still doesn't send emails, the
problem is in how the Flask app is loading .env (see the checklist this
script prints at the end).
"""

import os
import smtplib
import sys
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()

GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")

print("=" * 60)
print("Gmail SMTP test")
print("=" * 60)
print(f"GMAIL_ADDRESS loaded as: {GMAIL_ADDRESS!r}")
if GMAIL_APP_PASSWORD:
    print(f"GMAIL_APP_PASSWORD loaded, length={len(GMAIL_APP_PASSWORD)} "
          f"(should be 16, no spaces)")
else:
    print("GMAIL_APP_PASSWORD loaded as: None")
print("=" * 60)

if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
    print("\n❌ .env was not loaded, or the variables are missing/misnamed.")
    print("   Checklist:")
    print("   1. Is the file literally named '.env' (not '.env.txt' or 'env.env')?")
    print("      On Windows, run this to check:  dir /a .env*")
    print("   2. Is it in the SAME folder as this script and app.py?")
    print("   3. Open it in a text editor and confirm these two lines exist,")
    print("      with no quotes and no extra spaces around the '=':")
    print("      GMAIL_ADDRESS=youraddress@gmail.com")
    print("      GMAIL_APP_PASSWORD=your16characterpassword")
    sys.exit(1)

if len(GMAIL_APP_PASSWORD) != 16:
    print(f"\n⚠️  Warning: GMAIL_APP_PASSWORD is {len(GMAIL_APP_PASSWORD)} characters, "
          f"expected 16. Did you accidentally leave spaces in it?")

recipient = sys.argv[1] if len(sys.argv) > 1 else GMAIL_ADDRESS

msg = MIMEText("This is a test email from your Flask app's SMTP test script. If you got this, Gmail sending works!")
msg["Subject"] = "Test email — Dee Coder Technologies"
msg["From"] = GMAIL_ADDRESS
msg["To"] = recipient


def try_starttls():
    print(f"\n--- Attempt 1: port 587 with STARTTLS (smtp.gmail.com:587) ---")
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=12) as server:
        server.starttls()
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, [recipient], msg.as_string())


def try_ssl():
    print(f"\n--- Attempt 2: port 465 with SSL (smtp.gmail.com:465) ---")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=12) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, [recipient], msg.as_string())


auth_failed = False
last_error = None

for attempt_name, attempt_fn in [("587/STARTTLS", try_starttls), ("465/SSL", try_ssl)]:
    try:
        attempt_fn()
        print(f"\n✅ SUCCESS via {attempt_name} — check the inbox (and spam folder) of: {recipient}")
        if attempt_name == "465/SSL":
            print("\n   NOTE: port 587 failed but port 465 worked — your network blocks 587.")
            print("   Tell Claude this, so services/email_service.py can be switched to use")
            print("   port 465 with SMTP_SSL instead of port 587 with STARTTLS.")
        sys.exit(0)
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ AUTHENTICATION FAILED on {attempt_name} — Gmail rejected the login.")
        print("   Details:", e)
        auth_failed = True
        last_error = e
    except Exception as e:
        print(f"❌ {attempt_name} failed: {e!r}")
        last_error = e

print("\n" + "=" * 60)
if auth_failed:
    print("Gmail was REACHABLE but rejected your credentials. Most common causes:")
    print("- 2-Step Verification is not turned on for this Gmail account")
    print("  (App Passwords only work with 2-Step Verification enabled)")
    print("- The App Password was regenerated/revoked since you copied it")
    print("- There's a typo, or a duplicated 'GMAIL_ADDRESS=GMAIL_ADDRESS=...' in .env")
    print("- You used your normal Gmail password instead of an App Password")
else:
    print("BOTH ports timed out / failed to connect — Gmail was never reached at all.")
    print("This points to your network, not your credentials. Try, in order:")
    print("1. Temporarily disable antivirus/firewall (Windows Defender, Avast, etc.)")
    print("   and re-run this script.")
    print("2. Connect to a phone hotspot instead of your normal WiFi/router and")
    print("   re-run this script — this tells us if your router/ISP is blocking it.")
    print("3. Check Windows Firewall > Advanced Settings > Outbound Rules for any")
    print("   rule blocking python.exe or ports 587/465.")
    print(f"\nLast error seen: {last_error!r}")
