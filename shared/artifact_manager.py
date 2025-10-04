"""
Artifact manager for organizing all generated files.
Keeps project root clean by storing outputs in dedicated directories.
"""
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import shutil


class ArtifactManager:
    """Manages artifact storage and organization"""

    def __init__(self, base_dir: str = "artifacts"):
        """
        Initialize artifact manager.

        Args:
            base_dir: Base directory for all artifacts (default: "artifacts")
        """
        self.base_dir = Path(base_dir)

        # Create subdirectories
        self.results_dir = self.base_dir / "results"  # HTML results
        self.uploads_dir = self.base_dir / "uploads"  # Task uploads
        self.reports_dir = self.base_dir / "reports"  # Analysis reports
        self.data_dir = self.base_dir / "data"        # JSON/CSV outputs
        self.images_dir = self.base_dir / "images"    # Visualizations
        self.temp_dir = self.base_dir / "temp"        # Temporary files

        # Create all directories
        for directory in [self.results_dir, self.uploads_dir, self.reports_dir,
                         self.data_dir, self.images_dir, self.temp_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def get_task_results_dir(self, task_id: str) -> Path:
        """
        Get results directory for a specific task.
        Creates: artifacts/results/{task_id}_{timestamp}/

        Args:
            task_id: Task ID (already timestamped)

        Returns:
            Path to task results directory
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        task_dir = self.results_dir / f"{task_id}_{timestamp}"
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir

    def get_task_uploads_dir(self, task_id: str) -> Path:
        """
        Get uploads directory for a specific task.
        Creates: artifacts/uploads/{task_id}/

        Args:
            task_id: Task ID

        Returns:
            Path to task uploads directory
        """
        task_dir = self.uploads_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir

    def save_html_result(
        self,
        task_id: str,
        subtask_id: str,
        agent_id: str,
        html_content: str,
        execution_time: float
    ) -> str:
        """
        Save HTML result to artifacts/results/{task_id}_{timestamp}/

        Returns:
            Relative path to saved file
        """
        task_dir = self.get_task_results_dir(task_id)
        filename = f"{subtask_id}_{agent_id}.html"
        file_path = task_dir / filename

        # Wrap content in full HTML if needed
        if not html_content.strip().lower().startswith("<!doctype") and \
           not html_content.strip().lower().startswith("<html"):
            full_html = self._wrap_html(task_id, subtask_id, agent_id,
                                       html_content, execution_time)
        else:
            full_html = html_content

        file_path.write_text(full_html, encoding='utf-8')

        # Return path using simple string construction to avoid path resolution issues
        return str(file_path).replace('\\', '/')

    def save_report(
        self,
        filename: str,
        content: str,
        subfolder: Optional[str] = None
    ) -> str:
        """
        Save report file to artifacts/reports/

        Args:
            filename: Report filename
            content: Report content
            subfolder: Optional subfolder within reports/

        Returns:
            Relative path to saved file
        """
        if subfolder:
            report_dir = self.reports_dir / subfolder
            report_dir.mkdir(parents=True, exist_ok=True)
        else:
            report_dir = self.reports_dir

        file_path = report_dir / filename
        file_path.write_text(content, encoding='utf-8')

        return str(file_path).replace('\\', '/')

    def save_data(
        self,
        filename: str,
        content: str,
        subfolder: Optional[str] = None
    ) -> str:
        """
        Save data file (JSON, CSV, etc.) to artifacts/data/

        Args:
            filename: Data filename
            content: Data content
            subfolder: Optional subfolder within data/

        Returns:
            Relative path to saved file
        """
        if subfolder:
            data_path = self.data_dir / subfolder
            data_path.mkdir(parents=True, exist_ok=True)
        else:
            data_path = self.data_dir

        file_path = data_path / filename
        file_path.write_text(content, encoding='utf-8')

        return str(file_path).replace('\\', '/')

    def save_image(
        self,
        filename: str,
        content: bytes,
        subfolder: Optional[str] = None
    ) -> str:
        """
        Save image file to artifacts/images/

        Args:
            filename: Image filename
            content: Image binary content
            subfolder: Optional subfolder within images/

        Returns:
            Relative path to saved file
        """
        if subfolder:
            image_path = self.images_dir / subfolder
            image_path.mkdir(parents=True, exist_ok=True)
        else:
            image_path = self.images_dir

        file_path = image_path / filename
        file_path.write_bytes(content)

        return str(file_path).replace('\\', '/')

    def cleanup_temp(self):
        """Clean temporary directory"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            self.temp_dir.mkdir(parents=True, exist_ok=True)

    def get_artifact_info(self) -> Dict[str, Any]:
        """
        Get information about artifact storage.

        Returns:
            Dictionary with artifact statistics
        """
        def count_files(directory: Path) -> int:
            if not directory.exists():
                return 0
            return sum(1 for _ in directory.rglob('*') if _.is_file())

        def get_size_mb(directory: Path) -> float:
            if not directory.exists():
                return 0.0
            total = sum(f.stat().st_size for f in directory.rglob('*') if f.is_file())
            return round(total / (1024 * 1024), 2)

        return {
            "base_directory": str(self.base_dir),
            "results": {
                "count": count_files(self.results_dir),
                "size_mb": get_size_mb(self.results_dir)
            },
            "uploads": {
                "count": count_files(self.uploads_dir),
                "size_mb": get_size_mb(self.uploads_dir)
            },
            "reports": {
                "count": count_files(self.reports_dir),
                "size_mb": get_size_mb(self.reports_dir)
            },
            "data": {
                "count": count_files(self.data_dir),
                "size_mb": get_size_mb(self.data_dir)
            },
            "images": {
                "count": count_files(self.images_dir),
                "size_mb": get_size_mb(self.images_dir)
            },
            "total_files": count_files(self.base_dir),
            "total_size_mb": get_size_mb(self.base_dir)
        }

    def _wrap_html(
        self,
        task_id: str,
        subtask_id: str,
        agent_id: str,
        content: str,
        execution_time: float
    ) -> str:
        """Wrap content in HTML template"""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Task Result - {subtask_id}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .content {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1, h2, h3 {{ color: #333; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #667eea;
            color: white;
        }}
        pre {{
            background: #f4f4f4;
            padding: 15px;
            border-radius: 4px;
            overflow-x: auto;
        }}
        code {{
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }}
        .metadata {{
            font-size: 0.9em;
            color: #666;
            margin-top: 10px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Agent Task Result</h1>
        <div class="metadata">
            <strong>Task ID:</strong> {task_id}<br>
            <strong>Subtask ID:</strong> {subtask_id}<br>
            <strong>Agent:</strong> {agent_id}<br>
            <strong>Execution Time:</strong> {execution_time:.2f}s<br>
            <strong>Timestamp:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        </div>
    </div>
    <div class="content">
        {content}
    </div>
</body>
</html>"""


# Singleton instance
artifact_manager = ArtifactManager()
