# PythonAnywhere Deployment

This project is a Flask application. PythonAnywhere runs it through a WSGI file and does not use `python app.py` as the production server.

## 1. Upload the project

Open a PythonAnywhere Bash console and clone the repository:

```bash
cd ~
git clone YOUR_GITHUB_REPOSITORY_URL company_website
cd company_website
```

If the project is not in GitHub, upload and extract it from the Files tab.

## 2. Create the virtual environment

Use the Python version selected in the PythonAnywhere Web tab:

```bash
cd ~/company_website
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Replace `python3.10` if another supported Python version is selected.

## 3. Configure production settings

Create `.env` in the project directory. Do not commit this file:

```env
SECRET_KEY=replace-with-a-long-random-secret
FLASK_ENV=production
FLASK_DEBUG=0

DATABASE_URL=sqlite:////home/YOUR_USERNAME/company_website/instance/company.db

COMPANY_NAME=Dee Coder Technologies
SITE_URL=https://YOUR_USERNAME.pythonanywhere.com

GMAIL_ADDRESS=your-email@gmail.com
GMAIL_APP_PASSWORD=your-gmail-app-password
NOTIFICATION_EMAIL=your-newsletter-inbox@gmail.com
CONTACT_NOTIFICATION_EMAIL=deecodertechnologiesworldwide@gmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USE_SSL=1
SMTP_TIMEOUT=20
MAX_UPLOAD_MB=5
MAX_VIDEO_UPLOAD_MB=500
VIDEO_UPLOAD_CHUNK_MB=8
```

Replace `YOUR_USERNAME` with the PythonAnywhere username. A Gmail App Password is required; do not use the normal Gmail password. `DATABASE_URL` must be the absolute path to the existing persistent production database. Do not point it at a cloned or test database. Relative SQLite paths resolve against the project directory in development and are rejected in production.

Use an SMTP host, port, and TLS mode supported by both your provider and PythonAnywhere account. For Gmail, the compatible pairs are port 587 with `SMTP_USE_SSL=0` (STARTTLS), or port 465 with `SMTP_USE_SSL=1` (implicit TLS); do not mix the port and mode. PythonAnywhere plan/network policy may restrict external SMTP, so a local SMTP test does not verify that the service is reachable from the hosted account.

Product videos have no duration limit in the application. The default maximum
file size is 500 MB, and new videos upload in 8 MiB chunks so an individual
request stays small and can be retried from the admin form. Set
`MAX_VIDEO_UPLOAD_MB` to a lower value if needed to match available account
storage, or raise it only when the PythonAnywhere account has enough free
storage. `VIDEO_UPLOAD_CHUNK_MB` can be lowered if the hosting tier or any
upstream proxy has a smaller per-request body limit. Hosting disk quotas and
provider request limits are independent of Flask settings and cannot be raised
by application code; check the account's current plan/usage before selecting
a higher total upload size. Uploads preserve the original file bytes.

Create the directories used for the database and uploads:

```bash
mkdir -p instance uploads/news uploads/products uploads/projects uploads/videos uploads/video-thumbnails
```

## 4. Database migrations

The migration files are already included in the repository. On the first deployment, apply them to create all tables:

```bash
cd ~/company_website
source venv/bin/activate
flask --app app db upgrade
```

Before upgrading an existing production database, verify that the environment
selects its existing absolute path and back up that exact SQLite file. Check
the migration revision first. If production records exist but `flask db current`
reports no revision, stop and investigate the database history rather than
initializing, stamping, or creating another database. After confirming the
target, make an online-safe SQLite backup (replace the path with the exact
`DATABASE_URL` file), then check and apply the schema:

```bash
DB_FILE=/home/YOUR_USERNAME/company_website/instance/company.db
python -c 'import sqlite3,sys,time; src=sys.argv[1]; dst=src+".backup."+time.strftime("%Y%m%d-%H%M%S"); a=sqlite3.connect("file:"+src+"?mode=ro",uri=True); b=sqlite3.connect(dst); a.backup(b); b.close(); a.close(); print("Backup created:",dst)' "$DB_FILE"
flask --app app db current
flask --app app verify-deployment
flask --app app db upgrade
flask --app app verify-deployment
```

`verify-deployment` prints the selected SQLite path, checks all model tables
and columns, and probes the persistent instance/upload directories. It does
not create application tables or alter records.

Create the first administrator:

```bash
flask --app app create-admin
```

This command asks for the admin username, email, and password.

### When models change later

Run these commands on the development machine after changing a model:

```bash
flask --app app db migrate -m "Describe the database change"
flask --app app db upgrade
```

Commit and upload the new migration file, then run only the upgrade command on PythonAnywhere:

```bash
cd ~/company_website
git pull
source venv/bin/activate
flask --app app db upgrade
```

Do not run `db init` on PythonAnywhere because the `migrations/` directory already exists.

### Existing local data

If the local site already contains content, copy the local files to PythonAnywhere instead of creating an empty database:

- `instance/company.db`
- the complete `uploads/` directory

Keep the same paths under `/home/YOUR_USERNAME/company_website/`.

## 5. Configure the web app

In the PythonAnywhere Web tab:

1. Select **Add a new web app**.
2. Choose **Manual configuration**.
3. Select the same Python version used for `venv`.
4. Set the virtualenv path to:

```text
/home/YOUR_USERNAME/company_website/venv
```

Open the WSGI configuration file and replace its contents with:

```python
import sys

project_path = "/home/YOUR_USERNAME/company_website"

if project_path not in sys.path:
    sys.path.insert(0, project_path)

from app import app as application
```

Replace `YOUR_USERNAME` in both paths.
The WSGI file must insert the deployed project path before importing the app.
The application loads `.env` relative to `config.py`, so its environment is
independent of the WSGI working directory.

## 6. Static files and uploads

Add these mappings in the Web tab:

```text
URL: /static/
Directory: /home/YOUR_USERNAME/company_website/static
```

```text
URL: /uploads/
Directory: /home/YOUR_USERNAME/company_website/uploads
```

Click **Reload** after saving the WSGI file or changing a mapping.

## 7. Open the site

Public site:

```text
https://YOUR_USERNAME.pythonanywhere.com
```

Admin login:

```text
https://YOUR_USERNAME.pythonanywhere.com/admin/login
```

Do not run `python app.py` as the production server. The WSGI file imports the `app` object from `app.py`.

## 8. Updating the deployment

For a normal code update:

```bash
cd ~/company_website
git pull
source venv/bin/activate
pip install -r requirements.txt
flask --app app db current
flask --app app verify-deployment
flask --app app db upgrade
flask --app app verify-deployment
flask --app app check-smtp
```

If this site already has a production `.env`, update its existing
`MAX_VIDEO_UPLOAD_MB` value to `500` (or another value supported by the
account's remaining storage) and set `VIDEO_UPLOAD_CHUNK_MB=8`. Environment
variables configured separately in the hosting dashboard take precedence over
`.env`, so update those there if present. Then click **Reload** in the Web tab.

## 9. Troubleshooting a generic PythonAnywhere error

The browser message does not include the Python exception. Open the Web tab and inspect:

- **Error log** for WSGI import, dependency, environment-variable, and permission errors.
- **Server log** for request-time errors after the app has started.

You can also verify the deployment from a Bash console:

```bash
cd ~/company_website
source venv/bin/activate
python -c "from app import app; print(app.url_map)"
flask --app app db current
flask --app app verify-deployment
flask --app app check-smtp
```

Common fixes:

- `ModuleNotFoundError`: activate the configured virtualenv and run `pip install -r requirements.txt`.
- `cannot import name application`: the WSGI file must contain `from app import app as application` after adding the project path to `sys.path`.
- `no such table`: confirm the WSGI process and CLI use the same absolute `DATABASE_URL`, back up the existing database, then run `flask --app app db upgrade`. Never reset a production database to fix a missing table.
- `unable to open database file` or upload permission errors: confirm the paths in `.env` and run `mkdir -p instance uploads/news uploads/products uploads/projects`.
- `SMTPServerDisconnected` during login: run `flask --app app check-smtp` from a PythonAnywhere Bash console. It checks connectivity, TLS, and authentication without sending an email. Confirm the SMTP provider, port/TLS pairing, App Password, and PythonAnywhere account network policy. If it passes, send a separate deliberate test only to a mailbox you control and check provider bounce/delivery logs.
- `OSError` while storing uploads: run `flask --app app verify-deployment` and inspect the full traceback for the precise failing path. Check PythonAnywhere permissions and disk quota; do not remove or relocate persistent uploads as a workaround.

After changing the WSGI file, `.env`, dependencies, or migrations, click **Reload** in the Web tab.
