# Quick Start Guide - Admin Dashboard

## ✅ System Status
Everything is ready to use. No additional setup needed.

## Access the Admin Dashboard

### Step 1: Ensure Server is Running
```bash
cd company_website
python app.py
```
Server will be available at: http://127.0.0.1:5000

### Step 2: Login to Admin
1. Go to http://127.0.0.1:5000/admin/login
2. Username: `admin`
3. Password: Use the one you created with `flask create-admin`

### Step 3: Navigate to Admin Sections
- **What We Offer** - Manage services (sidebar → "What We Offer")
- **Featured Projects** - Manage projects (sidebar → "Featured Projects")

---

## Managing Service Offers (What We Offer)

### View All Offers
1. Click "What We Offer" in sidebar
2. See list of all service offers
3. Each row shows: Order #, Title, Icon, Status (Active/Inactive), Actions

### Add New Offer
1. Click "Add Offer" button (top right)
2. Fill in form:
   - **Title** (required) - Service name
   - **Icon** (optional) - Remix Icon class (e.g., `ri-code-s-slash-line`)
   - **Description** (required) - Service description
   - **Button URL** (optional) - Link for "Learn more" button
   - **Button label** (optional) - Text for button (default: "Learn more")
   - **Display order** - Number determining position (lower numbers first)
   - **Active** - Check to show on public website
3. Click "Save Offer"

### Edit Offer
1. Click "Edit" button next to offer
2. Modify fields as needed
3. Click "Save Offer"

### Disable Offer (Hide without Deleting)
1. Click "Edit" button next to offer
2. Uncheck "Active on public website"
3. Click "Save Offer"
4. Offer is removed from public site but stays in database

### Delete Offer (Permanent)
1. Click "Delete" button next to offer
2. Confirm deletion
3. Offer is permanently removed

### Change Offer Order
1. Click "Edit" button next to offer
2. Change "Display order" number
3. Click "Save Offer"
4. Public website will show offers in this order

---

## Managing Featured Projects

### View All Projects
1. Click "Featured Projects" in sidebar
2. See list with thumbnail, title, category, order, status
3. Shows which projects are active/inactive

### Add New Project
1. Click "Add Project" button
2. Fill in form:
   - **Project title** (required)
   - **Category** (optional) - Project type/technology
   - **Short description** (required) - Brief summary
   - **Full description** (optional) - Detailed info
   - **Live project URL** (optional) - Link to deployed project
   - **GitHub/project URL** (optional) - Link to repository
   - **Display order** - Number determining position
   - **Project image** (optional) - Upload JPG, PNG, GIF, or WebP
   - **Active** - Check to show on public website
3. Click "Save Project"

### Edit Project
1. Click "Edit" button
2. Modify fields
3. To change image: Upload new image (old one replaced)
4. Click "Save Project"

### Disable Project
1. Click "Edit" button
2. Uncheck "Active on public website"
3. Click "Save Project"

### Delete Project
1. Click "Delete" button
2. Confirm deletion
3. Project and its image are removed

### Change Project Order
1. Click "Edit" button
2. Change "Display order"
3. Click "Save Project"

---

## Viewing Public Website

### See Your Changes
1. Go to http://127.0.0.1:5000 (homepage)
2. Scroll to "What We Offer" section - see all active service offers
3. Scroll to "Our Featured Projects" section - see active projects
4. Changes appear immediately (no page refresh needed)

### What You'll See
- **Service Offers**: Cards with icon, title, description, optional "Learn more" link
- **Featured Projects**: Cards with image, title, description, category, links to live project/GitHub

### What Won't Show
- Offers/projects with "Active" unchecked
- Deleted offers/projects

---

## Image Upload for Projects

### Supported Formats
- JPG / JPEG
- PNG
- GIF
- WebP

### Size Limit
- Maximum 5MB per image

### Upload Process
1. When adding/editing project, click "Choose File" under "Project image"
2. Select image from your computer
3. Image preview shows below
4. Save project - image uploaded and stored

### Image Management
- Uploading new image when editing replaces old one
- Deleting project removes image
- Missing images show placeholder on website

---

## Database and Data Safety

### Automatic Backups
- All changes saved to `instance/company.db`
- Database persists between server restarts
- No manual backup needed for testing

### Data Integrity
- All timestamps automatic (created_at, updated_at)
- No data loss
- Delete is permanent (use disable if you want to keep data)

### Reset Database (If Needed)
```bash
# Stop the server
# Delete database
rm instance/company.db

# Recreate database
flask db upgrade

# Create admin user again
flask create-admin
```

---

## Keyboard Shortcuts / Quick Tips

| Action | How To |
|--------|-------|
| List view | Click menu item in sidebar |
| Add new | Click "Add" button (top right) |
| Edit | Click "Edit" button in table |
| Delete | Click "Delete" button (confirm) |
| View public site | Click "View Site" in sidebar (opens in new tab) |
| Logout | Click "Logout" at bottom of sidebar |

---

## Troubleshooting

### Changes not appearing on public website
- Refresh browser (F5)
- Check "Active" box on the offer/project
- Restart server if needed

### Can't login
- Check username and password
- Create new admin: `flask create-admin`
- Verify server is running

### Can't upload image
- Check file format (must be JPG, PNG, GIF, or WebP)
- Check file size (max 5MB)
- Make sure `uploads/projects/` folder exists

### Server won't start
```bash
pip install -r requirements.txt
flask db upgrade
python app.py
```

---

## Support

All features are documented in:
- `IMPLEMENTATION_REPORT.md` - Complete technical details
- `ADMIN_DASHBOARD_SUMMARY.md` - Feature reference

---

**Everything is ready to use. Start managing your content now!** 🚀
