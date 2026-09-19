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
NOTIFICATION_EMAIL=your-email@gmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_SSL=0
MAX_UPLOAD_MB=5
```

Replace `YOUR_USERNAME` with the PythonAnywhere username. A Gmail App Password is required; do not use the normal Gmail password.

Create the directories used for the database and uploads:

```bash
mkdir -p instance uploads/news uploads/products uploads/projects
```

## 4. Database migrations

The migration files are already included in the repository. On the first deployment, apply them to create all tables:

```bash
cd ~/company_website
source venv/bin/activate
flask --app app db upgrade
```

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
flask --app app db upgrade
```

Then click **Reload** in the Web tab.

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
```

Common fixes:

- `ModuleNotFoundError`: activate the configured virtualenv and run `pip install -r requirements.txt`.
- `cannot import name application`: the WSGI file must contain `from app import app as application` after adding the project path to `sys.path`.
- `no such table`: run `flask --app app db upgrade`.
- `unable to open database file` or upload permission errors: confirm the paths in `.env` and run `mkdir -p instance uploads/news uploads/products uploads/projects`.

After changing the WSGI file, `.env`, dependencies, or migrations, click **Reload** in the Web tab.
