# DeeCoder Technologies — Full-Stack Website

Your original HTML/CSS front end, now backed by a real Flask + SQLAlchemy
application: dynamic News and Products, a newsletter, contact forms with a
persistent admin inbox and conversation history, and Gmail email notifications.

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
│   ├── product_video.py         # ProductVideo
│   ├── subscriber.py             # Subscriber
│   └── contact.py                # ContactMessage + ContactMessageActivity
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
├── uploads/videos/                       # Product preview videos (MP4/WEBM)
├── uploads/video-thumbnails/             # Optional product video thumbnails
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
  NOTIFICATION_EMAIL=your-newsletter-inbox@gmail.com
  CONTACT_NOTIFICATION_EMAIL=deecodertechnologiesworldwide@gmail.com
   ```
   Never put these values anywhere except `.env` — they are read only from
   environment variables (see `config.py` and `services/email_service.py`)
   and are never sent to the browser or hard-coded anywhere.

  `NOTIFICATION_EMAIL` receives newsletter notifications. Contact-form
  notifications use `CONTACT_NOTIFICATION_EMAIL`, which defaults to the public
  contact address shown on the website. Set it explicitly if that inbox changes.
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
The contact migrations add phone storage, the persistent inbox and conversation
history, and the newer archive/trash, priority, internal-note, and reply-history
fields. Deploy all pending migrations with `flask db upgrade` after backing up
production data.

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

### Product video previews

Use **Product Videos** in the admin dashboard to upload, edit, or remove
homepage video previews. Videos are stored in `uploads/videos/` and
optional thumbnails in `uploads/video-thumbnails/`; the additive
`20261010_product_videos` migration stores their metadata in the database.
MP4 and WEBM files have no duration limit and are accepted up to 500 MB by
default. New uploads use 8 MiB chunks; configure
`MAX_VIDEO_UPLOAD_MB` for the total file limit and `VIDEO_UPLOAD_CHUNK_MB`
for the individual request size. Hosting storage quotas and request limits
still apply. Files are stored in their original quality. Apply the migration with
`flask db upgrade` before using the new admin section. The homepage player
uses custom play/pause, seek, time, volume, and fullscreen controls rather
than browser-native controls; the timeline supports pointer, touch, and
keyboard seeking.

## 5. How subscriber notifications work

- Visitors subscribe via the **"Stay in touch"** box in the footer
  (AJAX — no page reload). Duplicate emails are detected and simply
  return a friendly "already subscribed" message.
- Every subscriber gets a one-click **unsubscribe link** in every email
  (`/unsubscribe/<token>`), and admins can also deactivate or remove
  subscribers from **Subscribers** in the dashboard.
- Subscriber emails are never exposed on the public website.

## 6. Contact inbox and conversation workflow

- The homepage and Contact page use the same backend endpoint. Submissions
  are validated, rate-limited, deduplicated by submission token, saved in the
  database, and sent to the configured business inbox. The visitor receives a
  separate confirmation email.
- In the authenticated admin dashboard, **Contact Messages** supports search,
  status/read/priority filters, date filtering, sorting, pagination, archive,
  and a recoverable Trash folder. The dashboard shows inbox statistics and
  supports bulk actions; bulk approvals/declines update status without sending
  email.
  Opening a message marks it read; read state is separate from its request
  workflow status (**New**, **In Progress**, **Approved**, or **Declined**).
- Administrators can reply to visitors, accept or reject requests with an
  optional note, and see the persisted conversation and outgoing email
  attempt history. Replies include an editable recipient and subject; those
  values and failed attempts are stored for retries. Failed messages can be
  retried from the message details. Administrators can add private notes and
  set priorities; these stay in the admin dashboard and activity history.
- Deleting a message moves it to Trash. It can be restored or permanently
  deleted from there. Individual decisions send a clearly confirmed
  acceptance/decline email, and changing a decision later is recorded.
- Email statuses describe SMTP submission acceptance, not inbox delivery.
  The configured Gmail SMTP service does not provide a reliable delivery
  receipt or provider message ID, so the dashboard does not claim delivery.
- Apply `20261016_contact_phone`, `20261016_contact_workflow`, and
  `20261016_contact_management` with
  `flask db upgrade` after backing up an existing production database.

## 7. Security notes

- Passwords: Werkzeug `generate_password_hash` / `check_password_hash`
  — never stored or logged in plain text.
- Sessions: Flask's signed session cookie, `HttpOnly`, `SameSite=Lax`,
  and marked `Secure` automatically once `FLASK_ENV=production`.
- CSRF: `Flask-WTF`'s `CSRFProtect` protects every admin form. The contact
JSON endpoint validates the token rendered into its form; other public JSON
endpoints do not use session-based admin privileges.
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
- **Newsletter signup rate limiting** is not implemented. Contact messages
  already have a per-IP rate limit and honeypot protection; if newsletter spam
  becomes an issue, add a suitable limit to `/api/subscribe`.
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

## 11. Search engine setup

Set `SITE_URL` in the production environment to the exact public HTTPS origin
(for example, `https://www.your-real-domain.com`, without a path). Do not use
the example text literally. With no valid HTTPS origin configured, the app
omits canonical/absolute social metadata and returns HTTP 503 for
`/sitemap.xml` rather than publishing URLs for localhost or a placeholder.
After changing the setting, reload the app and check `/robots.txt` and
`/sitemap.xml`. The sitemap contains public company pages and published news
and products. The robots file requests that crawlers avoid admin, API,
unsubscribe, and uploaded-file paths; this is not an access-control mechanism.

### Google Search Console

1. Open [Google Search Console](https://search.google.com/search-console/) and
   add the official domain as a **Domain** property.
2. Verify ownership by adding the DNS TXT record Google provides at your
   domain registrar. Verification is complete only when Google confirms it.
3. In the verified property, open **Sitemaps**, enter `sitemap.xml`, and submit.
4. Use **URL inspection** for the canonical homepage, run the live test, and
   request indexing if appropriate.
5. Review **Pages** and **Performance** periodically for indexing issues and
   branded query impressions/clicks. Search Console does not guarantee a
   Knowledge Panel.

### Bing Webmaster Tools

1. Add the official HTTPS site at
   [Bing Webmaster Tools](https://www.bing.com/webmasters/).
2. Verify ownership using a Bing-provided DNS record or another offered method.
3. Submit `https://YOUR_OFFICIAL_DOMAIN/sitemap.xml` under **Sitemaps** (replace
   the placeholder with the actual domain).
4. Review URL inspection, indexing status, and search performance in Bing.

### Structured-data checks

- Test the public homepage and `/about` with
  [Google's Rich Results Test](https://search.google.com/test/rich-results/).
- Validate the JSON-LD with
  [Schema Markup Validator](https://validator.schema.org/).
- The website emits an `Organization` entity only when a real HTTPS `SITE_URL`
  is configured. Unverified social profiles, postal addresses, founding dates,
  and company identifiers are intentionally not asserted.
- Before enabling production SEO, confirm the exact official HTTPS domain,
  which footer social accounts are official, whether `static/images/g6jYI.jpg`
  is an approved logo or should be replaced, and any verified postal address,
  founding date, registration identifier, or DeeCoder Academy relationship.
  The current repository documentation describes its image assets as
  placeholders; therefore the structured data does not claim a verified logo.
