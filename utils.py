"""
Small shared helpers: slug generation and safe image uploads.
"""

import os
import re
import uuid

from flask import current_app
from werkzeug.utils import secure_filename


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "item"


def make_unique_slug(base_text: str, model, exclude_id=None) -> str:
    """Generate a slug from base_text, appending -2, -3, ... on collision."""
    base = slugify(base_text)
    slug = base
    counter = 2
    while True:
        query = model.query.filter_by(slug=slug)
        if exclude_id is not None:
            query = query.filter(model.id != exclude_id)
        if query.first() is None:
            return slug
        slug = f"{base}-{counter}"
        counter += 1


def allowed_image(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]


# Magic-byte signatures for the image types we accept. Checking these (not
# just the extension) stops someone renaming an arbitrary/executable file
# to ".jpg" and having it accepted.
_IMAGE_SIGNATURES = {
    b"\xff\xd8\xff": "jpg",
    b"\x89PNG\r\n\x1a\n": "png",
    b"GIF87a": "gif",
    b"GIF89a": "gif",
    b"RIFF": "webp",  # followed by 'WEBP' at byte offset 8, checked separately
}


def _looks_like_image(file_storage) -> bool:
    header = file_storage.stream.read(16)
    file_storage.stream.seek(0)
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return True
    for sig in _IMAGE_SIGNATURES:
        if sig != b"RIFF" and header.startswith(sig):
            return True
    return False


def save_uploaded_image(file_storage, subfolder: str):
    """
    Validate and save an uploaded image safely.

    - Checks the extension against an allow-list.
    - Checks the actual file bytes (magic numbers), not just the extension.
    - Never trusts the original filename: generates a random one instead.
    - Saves under uploads/<subfolder>/.

    Returns the relative path (e.g. "news/ab12cd34.jpg") to store in the DB,
    or None if no file was provided.
    Raises ValueError with a user-friendly message if the file is invalid.
    """
    if not file_storage or file_storage.filename == "":
        return None

    filename = secure_filename(file_storage.filename)
    if not allowed_image(filename):
        raise ValueError("Unsupported file type. Please upload a PNG, JPG, GIF, or WEBP image.")

    if not _looks_like_image(file_storage):
        raise ValueError("The uploaded file does not look like a valid image.")

    ext = filename.rsplit(".", 1)[1].lower()
    safe_name = f"{uuid.uuid4().hex}.{ext}"

    upload_root = current_app.config["UPLOAD_FOLDER"]
    target_dir = os.path.join(upload_root, subfolder)
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, safe_name)

    file_storage.save(target_path)
    return f"{subfolder}/{safe_name}"
