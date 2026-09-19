# Dee Coder Technologies — Full-Stack Website

Your original HTML/CSS front end, now backed by a real Flask + SQLAlchemy
application: dynamic News and Products, a newsletter, a moderated contact
form, an admin dashboard, and Gmail email notifications.

**Nothing about your original design was rebuilt.** `static/css/newadd.css`
is your file, untouched. All new styling lives in separate additive files
(`site-extra.css`, `admin.css`) so nothing collides with your existing
classes.

---

## 1. Project structure

```
company_website/
├── app.py                  # App factory, blueprint registration, CLI
├── config.py                # All settings, read from environment variables
├── extensions.py             # db / migrate / csrf instances
├── auth.py                   # Session-based admin login helpers
├── utils.py                  # Slug generation + safe image upload
├── requirements.txt
├── .env.example               # Copy to .env and fill in real values
├── .gitignore
│
├── models/
│   ├── admin.py               # AdminUser (Werkzeug password hashing)
│   ├── news.py                 # News
│   ├── product.py               # Product
│   ├── subscriber.py             # Subscriber
│   └── contact.py                # ContactMessage
│
├── routes/
│   ├── public.py               # /, /news, /news/<slug>, /products, /products/<slug>, /unsubscribe
│   ├── api.py                   # /api/news, /api/products, /api/subscribe, /api/contact (JSON, used by fetch())
│   └── admin.py                 # /admin/* — login, dashboard, CRUD, subscribers, messages, settings
│
├── services/
│   └── email_service.py          # All outgoing email goes through here (Gmail SMTP)
│
├── templates/
│   ├── base.html                  # Shared nav + footer (from your original markup)
│   ├── index.html                  # Your homepage, unchanged, + dynamic News/Products sections
│   ├── news.html / article.html       # Public news listing + article page
│   ├── products.html / product.html    # Public product listing + product page
│   ├── unsubscribe.html, 404.html, 500.html
│   ├── emails/                          # HTML email templates
│   └── admin/                            # Admin dashboard templates
│
├── static/
│   ├── css/newadd.css      # YOUR original CSS — untouched
│   ├── css/site-extra.css  # New additive styles only (alerts, pagination, badges…)
│   ├── css/admin.css       # Admin dashboard styling
│   ├── js/main.js          # Your original inline script, moved here + AJAX wiring
│   ├── js/admin.js         # Small admin dashboard helpers
│   └── images/             # Placeholder images generated for missing assets — see note below
│
├── uploads/news/ , uploads/products/    # User-uploaded images land here
├── migrations/                            # Created by `flask db init`
└── instance/company.db                     # SQLite database (created automatically)
```

### ⚠️ About images
Only `newadd.html` and `newadd.css` were provided — the actual image files
(`port.png`, `e-com.png`, `move.png`, `brand-show.png`, `interactive.png`,
`g6jYI.jpg`) were **not** uploaded. I generated simple placeholder graphics
in `static/images/` so the site isn't visually broken, but you should
replace them with your real project screenshots and logo — just drop files
with the same names into `static/images/`.

---

## 2. Setup instructions

### Step 1 — Create and activate a virtual environment
```bash
cd company_website
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### Step 2 — Install requirements
```bash
pip install -r requirements.txt
```

### Step 3 — Create your `.env` file
```bash
cp .env.example .env
```
Open `.env` and fill in a real `SECRET_KEY` (any long random string), and
leave `DATABASE_URL` as-is for SQLite.

### Step 4 — Configure Gmail
1. Turn on 2-Step Verification on the Gmail account you want to send from.
2. Create an **App Password** at https://myaccount.google.com/apppasswords
   (choose "Mail" as the app).
3. In `.env`, set:
   ```
   GMAIL_ADDRESS=your-real-address@gmail.com
   GMAIL_APP_PASSWORD=the-16-character-app-password
  NOTIFICATION_EMAIL=your-inbox@gmail.com
   ```
   Never put these values anywhere except `.env` — they are read only from
   environment variables (see `config.py` and `services/email_service.py`)
   and are never sent to the browser or hard-coded anywhere.

  `NOTIFICATION_EMAIL` receives new newsletter subscription and contact-form
  notifications. If it is omitted, notifications are sent to `GMAIL_ADDRESS`.
  The Flask application loads `.env` relative to `config.py`, so a WSGI server's
  working directory does not affect local `.env` loading. In hosted production,
  set the same variables in the platform's environment/secrets settings.

### Step 5 — Initialize the database
```bash
flask db init
flask db migrate -m "Initial tables"
flask db upgrade
```
This creates `instance/company.db` and the `migrations/` folder. Whenever
you change a model later, run `flask db migrate -m "..."` then
`flask db upgrade` again — no need to touch SQLite directly.

### Step 6 — Create your admin account
```bash
flask create-admin
```
You'll be prompted for a username, email, and password (min. 8 characters,
hashed with Werkzeug — never stored in plain text).

### Step 7 — Run the server
```bash
python app.py
```
Or, for development with auto-reload:
```bash
export FLASK_APP=app.py FLASK_DEBUG=1     # Windows: set FLASK_APP=app.py
flask run
```

### Step 8 — Open the site
- Public website: http://127.0.0.1:5000
- Admin dashboard: http://127.0.0.1:5000/admin/login

---

## 3. How to publish news

1. Log into `/admin/login`.
2. Go to **News → Add News**.
3. Fill in Title, Summary, Content, optionally upload an image and set
   an author.
4. Check **Published** and click **Save**.
5. The moment it's saved as published for the first time, every active
   subscriber automatically receives the "New Update" email with the
   title, summary, and a link to the article.
6. Editing an already-published article does **not** re-send the email.
   If you unpublish and later re-publish the same article, that next
   publish *will* send a fresh notification (so subscribers aren't
   accidentally spammed by simple edits, but a genuine "re-launch" still
   notifies them).

## 4. How to publish products

Same flow under **Products → Add Product**. Products do **not** email
subscribers by default — tick **"Email subscribers when this product is
published"** on the product form if you want that specific product to
trigger a notification.

## 5. How subscriber notifications work

- Visitors subscribe via the **"Stay in touch"** box in the footer
  (AJAX — no page reload). Duplicate emails are detected and simply
  return a friendly "already subscribed" message.
- Every subscriber gets a one-click **unsubscribe link** in every email
  (`/unsubscribe/<token>`), and admins can also deactivate or remove
  subscribers from **Subscribers** in the dashboard.
- Subscriber emails are never exposed on the public website.

## 6. How contact approval/decline works

1. A visitor submits the contact form → saved as **PENDING** → they see
   "waiting for admin approval" and receive a confirmation email.
2. In **Contact Messages**, you can view each message and click
   **Approve** or **Decline** (optionally adding a note, included in the
   decline email).
3. The sender is emailed automatically the moment you decide. Clicking
   Approve/Decline twice will never send a duplicate email — this is
   tracked per-message.

## 7. Security notes

- Passwords: Werkzeug `generate_password_hash` / `check_password_hash`
  — never stored or logged in plain text.
- Sessions: Flask's signed session cookie, `HttpOnly`, `SameSite=Lax`,
  and marked `Secure` automatically once `FLASK_ENV=production`.
- CSRF: `Flask-WTF`'s `CSRFProtect` protects every admin form (the JSON
  `/api/*` endpoints are exempted, since they carry no session-based
  admin privileges).
- Uploads: extension allow-list **and** magic-byte checking (so a
  renamed `.exe` can't sneak in as `.jpg`), random generated filenames
  (original filenames are never trusted or reused).
- All secrets come from environment variables via `.env`, which is
  git-ignored. Nothing sensitive is hard-coded in source, templates, or
  JavaScript.
- SQL injection is mitigated by using SQLAlchemy's parameterized ORM
  queries throughout — no raw string-built SQL anywhere.

## 8. Moving from SQLite to PostgreSQL later

No application code changes are needed. In `.env`, change:
```
DATABASE_URL=postgresql://username:password@host:5432/dbname
```
Install a driver (`pip install psycopg2-binary`), then run
`flask db upgrade` against the new database. SQLAlchemy and Flask-Migrate
handle the rest.

## 9. Known limitations / next steps

- **Email sending is synchronous.** For a small subscriber list this is
  fine, but if you expect hundreds/thousands of subscribers, move the
  loop in `_maybe_notify_subscribers_of_news` (in `routes/admin.py`) to
  a background task queue (e.g. Celery or RQ) so publishing an article
  doesn't block the admin's browser while emails send.
- **Rate limiting** on the public `/api/subscribe` and `/api/contact`
  endpoints isn't implemented (no extra dependency was added for it).
  If spam becomes an issue, add `Flask-Limiter`.
- The rich-text fields (article content, product description) accept
  basic HTML and render it as-is on the public page — only admins can
  write it, so this is safe by design, but there's no WYSIWYG editor
  in the dashboard yet (plain `<textarea>`). You can paste HTML
  directly, or add a JS editor (e.g. TinyMCE/Quill) to `news_form.html`
  / `product_form.html` later.
- Placeholder images are in `static/images/` — replace with your real
  screenshots/logo (see note above).

## 10. Production deployment considerations

- Set `FLASK_ENV=production` (enables secure cookies) and turn off
  `FLASK_DEBUG`.
- Run behind a real WSGI server (e.g. `gunicorn app:app`) behind Nginx,
  not Flask's built-in dev server.
- Serve over HTTPS — required for `SESSION_COOKIE_SECURE` to actually
  protect the session cookie.
- Point `DATABASE_URL` at a managed PostgreSQL instance.
- Store `uploads/` on persistent storage (or move to S3/Cloud Storage)
  if deploying to an ephemeral filesystem (e.g. Heroku-style platforms).
- Rotate `SECRET_KEY` and the Gmail App Password only through your
  hosting platform's environment/secrets manager — never commit `.env`.
