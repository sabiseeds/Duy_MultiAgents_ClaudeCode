"""
File storage manager for task uploads.
Handles file uploads, storage, and retrieval for tasks.
"""
import os
import shutil
import mimetypes
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from shared.models import FileAttachment


class FileStorageManager:
    """Manages file uploads for tasks"""

    UPLOADS_BASE_DIR = Path("uploads")
    ALLOWED_EXTENSIONS = {
        # Images
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg',
        # Documents
        '.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt',
        # Spreadsheets
        '.xls', '.xlsx', '.csv', '.ods',
        # Archives
        '.zip', '.rar', '.7z', '.tar', '.gz',
        # Data
        '.json', '.xml', '.yaml', '.yml',
        # Other
        '.ppt', '.pptx', '.md'
    }
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

    def __init__(self):
        """Initialize file storage manager"""
        self.UPLOADS_BASE_DIR.mkdir(parents=True, exist_ok=True)

    def create_task_upload_folder(self, task_id: str) -> Path:
        """
        Create upload folder for a task.

        Args:
            task_id: Task ID (already has ddmmyyhhmmss prefix)

        Returns:
            Path to the created folder
        """
        task_folder = self.UPLOADS_BASE_DIR / task_id
        task_folder.mkdir(parents=True, exist_ok=True)
        return task_folder

    def validate_file(self, filename: str, file_size: int) -> tuple[bool, Optional[str]]:
        """
        Validate uploaded file.

        Returns:
            (is_valid, error_message)
        """
        # Check extension
        file_ext = Path(filename).suffix.lower()
        if file_ext not in self.ALLOWED_EXTENSIONS:
            return False, f"File type '{file_ext}' not allowed. Allowed: {', '.join(sorted(self.ALLOWED_EXTENSIONS))}"

        # Check size
        if file_size > self.MAX_FILE_SIZE:
            max_mb = self.MAX_FILE_SIZE / (1024 * 1024)
            return False, f"File size exceeds {max_mb}MB limit"

        return True, None

    def save_upload(
        self,
        task_id: str,
        file_content: bytes,
        original_filename: str
    ) -> FileAttachment:
        """
        Save uploaded file and return metadata.

        Args:
            task_id: Task ID
            file_content: File binary content
            original_filename: Original filename from upload

        Returns:
            FileAttachment with metadata
        """
        # Validate
        file_size = len(file_content)
        is_valid, error = self.validate_file(original_filename, file_size)
        if not is_valid:
            raise ValueError(error)

        # Create task folder
        task_folder = self.create_task_upload_folder(task_id)

        # Generate safe filename (keep original name but sanitize)
        safe_filename = self._sanitize_filename(original_filename)
        file_path = task_folder / safe_filename

        # Handle duplicate filenames
        counter = 1
        while file_path.exists():
            stem = Path(safe_filename).stem
            suffix = Path(safe_filename).suffix
            safe_filename = f"{stem}_{counter}{suffix}"
            file_path = task_folder / safe_filename
            counter += 1

        # Write file
        file_path.write_bytes(file_content)

        # Get MIME type
        mime_type, _ = mimetypes.guess_type(original_filename)
        if not mime_type:
            mime_type = "application/octet-stream"

        # Create metadata
        # Use simple string path construction to avoid path resolution issues
        relative_path = str(task_folder / safe_filename).replace('\\', '/')

        return FileAttachment(
            filename=safe_filename,
            original_filename=original_filename,
            file_path=relative_path,
            file_size=file_size,
            mime_type=mime_type
        )

    def get_task_files(self, task_id: str) -> List[Path]:
        """Get all files for a task"""
        task_folder = self.UPLOADS_BASE_DIR / task_id
        if not task_folder.exists():
            return []

        return list(task_folder.glob("*"))

    def get_file_path(self, task_id: str, filename: str) -> Optional[Path]:
        """Get absolute path to a specific file"""
        file_path = self.UPLOADS_BASE_DIR / task_id / filename
        if file_path.exists() and file_path.is_file():
            return file_path
        return None

    def delete_task_files(self, task_id: str):
        """Delete all files for a task"""
        task_folder = self.UPLOADS_BASE_DIR / task_id
        if task_folder.exists():
            shutil.rmtree(task_folder)

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent directory traversal"""
        # Remove path components
        filename = Path(filename).name

        # Remove dangerous characters
        dangerous_chars = ['..', '/', '\\', '\x00', '<', '>', ':', '"', '|', '?', '*']
        for char in dangerous_chars:
            filename = filename.replace(char, '_')

        # Limit length
        if len(filename) > 200:
            stem = Path(filename).stem[:150]
            suffix = Path(filename).suffix
            filename = f"{stem}{suffix}"

        return filename

    def get_file_info(self, file_path: str) -> dict:
        """Get file information as dict"""
        path = Path(file_path)
        if not path.exists():
            return {}

        stat = path.stat()
        mime_type, _ = mimetypes.guess_type(str(path))

        return {
            "filename": path.name,
            "size": stat.st_size,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "mime_type": mime_type or "application/octet-stream",
            "created": datetime.fromtimestamp(stat.st_ctime),
            "modified": datetime.fromtimestamp(stat.st_mtime)
        }


# Singleton instance
file_storage = FileStorageManager()
