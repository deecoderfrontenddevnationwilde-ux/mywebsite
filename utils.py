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


def save_uploaded_image(file_storage, subfolder: str, max_size_bytes: int | None = None):
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

    if max_size_bytes is not None:
        file_storage.stream.seek(0, os.SEEK_END)
        file_size = file_storage.stream.tell()
        file_storage.stream.seek(0)
        if file_size > max_size_bytes:
            raise ValueError("The image exceeds the image upload limit.")

    if not _looks_like_image(file_storage):
        raise ValueError("The uploaded file does not look like a valid image.")

    ext = filename.rsplit(".", 1)[1].lower()
    safe_name = f"{uuid.uuid4().hex}.{ext}"

    upload_root = current_app.config["UPLOAD_FOLDER"]
    target_dir = os.path.join(upload_root, subfolder)
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, safe_name)

    try:
        file_storage.save(target_path)
    except OSError:
        try:
            os.remove(target_path)
        except FileNotFoundError:
            pass
        except OSError:
            current_app.logger.exception("Could not remove incomplete image upload %s", target_path)
        raise
    return f"{subfolder}/{safe_name}"


def save_uploaded_video(file_storage):
    """Validate and save an MP4 or WebM video under uploads/videos/."""
    if not file_storage or file_storage.filename == "":
        return None

    filename = secure_filename(file_storage.filename)
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in {"mp4", "webm"}:
        raise ValueError("Unsupported video type. Please upload an MP4 or WEBM video.")

    stream = file_storage.stream
    stream.seek(0, os.SEEK_END)
    file_size = stream.tell()
    stream.seek(0)
    max_size = current_app.config["MAX_VIDEO_UPLOAD_MB"] * 1024 * 1024
    if file_size == 0:
        raise ValueError("The selected video file is empty.")
    if file_size > max_size:
        raise ValueError(
            f"The video exceeds the {current_app.config['MAX_VIDEO_UPLOAD_MB']} MB upload limit."
        )

    header = stream.read(12)
    stream.seek(0)
    is_mp4 = extension == "mp4" and len(header) >= 8 and header[4:8] == b"ftyp"
    is_webm = extension == "webm" and header.startswith(b"\x1a\x45\xdf\xa3")
    if not (is_mp4 or is_webm):
        raise ValueError("The uploaded file does not match a supported MP4 or WEBM video.")

    safe_name = f"{uuid.uuid4().hex}.{extension}"
    target_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "videos")
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, safe_name)
    try:
        file_storage.save(target_path)
    except OSError:
        try:
            os.remove(target_path)
        except FileNotFoundError:
            pass
        except OSError:
            current_app.logger.exception("Could not remove incomplete video upload %s", target_path)
        raise
    return f"videos/{safe_name}"


def delete_uploaded_file(relative_path: str) -> bool:
    """Remove a file stored beneath UPLOAD_FOLDER; return False on cleanup errors."""
    if not relative_path:
        return True

    upload_root = os.path.realpath(current_app.config["UPLOAD_FOLDER"])
    file_path = os.path.realpath(os.path.join(upload_root, relative_path))
    try:
        is_within_uploads = os.path.commonpath((upload_root, file_path)) == upload_root
    except ValueError:
        is_within_uploads = False
    if not is_within_uploads:
        current_app.logger.warning("Refusing to remove an upload outside the upload directory.")
        return False

    try:
        os.remove(file_path)
    except FileNotFoundError:
        return True
    except OSError:
        current_app.logger.exception("Could not remove uploaded file %s", relative_path)
        return False
    return True
