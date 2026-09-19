"""
Diagnostic script — figures out exactly why SQLite can't open the database
file. Run this from the same folder as app.py:

    python diagnose_db.py
"""

import os
import sqlite3
import sys
from pathlib import Path

print("=" * 70)
print("Database diagnostic")
print("=" * 70)

cwd = Path.cwd()
print(f"Current working directory:\n  {cwd}\n")

script_dir = Path(__file__).resolve().parent
print(f"This script's folder (should match project root):\n  {script_dir}\n")

# Load the same way config.py does
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("WARNING: python-dotenv not installed — .env won't be loaded.")

database_url_env = os.environ.get("DATABASE_URL")
print(f"DATABASE_URL from environment/.env: {database_url_env!r}")

instance_dir = script_dir / "instance"
fallback_db_path = instance_dir / "company.db"
fallback_uri = f"sqlite:///{fallback_db_path}"

effective_uri = database_url_env or fallback_uri
print(f"Effective SQLALCHEMY_DATABASE_URI that config.py will build: {effective_uri!r}\n")

print(f"Does the 'instance' folder exist? -> {instance_dir.exists()}")
if not instance_dir.exists():
    print(f"  Creating it now: {instance_dir}")
    try:
        instance_dir.mkdir(parents=True, exist_ok=True)
        print("  Created successfully.")
    except Exception as e:
        print(f"  FAILED to create it: {e!r}")
        sys.exit(1)
else:
    print(f"  It's a directory: {instance_dir.is_dir()}")
    print(f"  Writable (os.access W_OK): {os.access(instance_dir, os.W_OK)}")

print()
print(f"Attempting to open a raw sqlite3 connection to:\n  {fallback_db_path}\n")
try:
    conn = sqlite3.connect(str(fallback_db_path))
    conn.execute("CREATE TABLE IF NOT EXISTS _diag_test (id INTEGER PRIMARY KEY)")
    conn.execute("DROP TABLE _diag_test")
    conn.commit()
    conn.close()
    print("✅ SUCCESS — raw sqlite3 can open and write to this file.")
    print(f"   File now exists: {fallback_db_path.exists()}")
    print(f"   File size: {fallback_db_path.stat().st_size if fallback_db_path.exists() else 'N/A'} bytes")
except Exception as e:
    print(f"❌ FAILED with raw sqlite3: {e!r}")
    print("\nThis means the problem is NOT Flask/SQLAlchemy at all — it's Windows")
    print("itself refusing to let Python create/open a file at that exact path.")
    print("Common causes:")
    print("  - Antivirus / Windows Defender real-time protection blocking file creation")
    print("  - OneDrive sync lock on the Downloads folder")
    print("  - The path contains characters OneDrive/antivirus is flagging")
    print("  - Folder permissions inherited oddly from a zip extraction")

print()
print("=" * 70)
print("If the raw sqlite3 test above SUCCEEDED, re-run your flask db commands —")
print("they should work now that the instance/ folder definitely exists.")
print("If it FAILED, try moving the whole project folder somewhere simple like")
print("C:\\dev\\company_website (no spaces, no parentheses, not inside OneDrive)")
print("and running everything again from there.")
print("=" * 70)
