import os
import uuid
import logging
from typing import Dict, Any
from fastapi import UploadFile, HTTPException, status

logger = logging.getLogger("upload_service")

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

ALLOWED_VIDEO_TYPES = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
}

MAX_IMAGE_SIZE = 10 * 1024 * 1024   # 10 MB
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB


def ensure_upload_dir():
    os.makedirs(UPLOAD_DIR, exist_ok=True)


async def save_uploaded_file(file: UploadFile) -> Dict[str, Any]:
    ensure_upload_dir()

    content_type = file.content_type or ""
    if content_type in ALLOWED_IMAGE_TYPES:
        max_size = MAX_IMAGE_SIZE
        ext = ALLOWED_IMAGE_TYPES[content_type]
        file_category = "image"
    elif content_type in ALLOWED_VIDEO_TYPES:
        max_size = MAX_VIDEO_SIZE
        ext = ALLOWED_VIDEO_TYPES[content_type]
        file_category = "video"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{content_type}'. Allowed types: JPEG, PNG, GIF, WebP, MP4, WebM, QuickTime.",
        )

    unique_name = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(UPLOAD_DIR, unique_name)

    total_bytes = 0
    chunk_size = 1024 * 1024  # 1MB chunks

    try:
        with open(dest_path, "wb") as f:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > max_size:
                    f.close()
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                    max_mb = max_size // (1024 * 1024)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"File size exceeds maximum allowed limit of {max_mb}MB for {file_category}s.",
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        logger.error(f"Error saving upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process uploaded file.",
        )

    return {
        "url": f"/uploads/{unique_name}",
        "filename": unique_name,
        "content_type": content_type,
        "size_bytes": total_bytes,
        "category": file_category,
    }
