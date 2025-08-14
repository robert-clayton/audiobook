import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ChapterProgress:
    """Represents the progress of a single chapter."""

    series_name: str
    chapter_title: str
    chapter_url: str
    status: str  # 'pending', 'scraped', 'tts_generated', 'audio_processed', 'completed', 'failed'
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    file_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        if self.started_at:
            data["started_at"] = self.started_at.isoformat()
        if self.completed_at:
            data["completed_at"] = self.completed_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChapterProgress":
        """Create from dictionary."""
        if data.get("started_at"):
            data["started_at"] = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            data["completed_at"] = datetime.fromisoformat(data["completed_at"])
        return cls(**data)


class ProgressTracker:
    """Tracks progress of audiobook generation operations."""

    def __init__(self, progress_file: Path = Path("progress.json")):
        self.progress_file = progress_file
        self.progress: Dict[str, ChapterProgress] = {}
        self.load_progress()

    def load_progress(self) -> None:
        """Load progress from file."""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.progress = {
                        key: ChapterProgress.from_dict(value)
                        for key, value in data.items()
                    }
            except Exception as e:
                print(f"Warning: Could not load progress file: {e}")
                self.progress = {}

    def save_progress(self) -> None:
        """Save progress to file."""
        try:
            data = {key: progress.to_dict() for key, progress in self.progress.items()}
            with open(self.progress_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Could not save progress file: {e}")

    def get_chapter_key(self, series_name: str, chapter_title: str) -> str:
        """Generate a unique key for a chapter."""
        return f"{series_name}:{chapter_title}"

    def add_chapter(
        self, series_name: str, chapter_title: str, chapter_url: str
    ) -> None:
        """Add a new chapter to track."""
        key = self.get_chapter_key(series_name, chapter_title)
        if key not in self.progress:
            self.progress[key] = ChapterProgress(
                series_name=series_name,
                chapter_title=chapter_title,
                chapter_url=chapter_url,
                status="pending",
            )
            self.save_progress()

    def update_status(
        self,
        series_name: str,
        chapter_title: str,
        status: str,
        error_message: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> None:
        """Update the status of a chapter."""
        key = self.get_chapter_key(series_name, chapter_title)
        if key in self.progress:
            progress = self.progress[key]
            progress.status = status
            progress.error_message = error_message
            progress.file_path = file_path

            if status == "pending":
                progress.started_at = datetime.now()
            elif status in ["completed", "failed"]:
                progress.completed_at = datetime.now()

            self.save_progress()

    def get_pending_chapters(
        self, series_name: Optional[str] = None
    ) -> List[ChapterProgress]:
        """Get all pending chapters, optionally filtered by series."""
        pending = [
            progress
            for progress in self.progress.values()
            if progress.status == "pending"
        ]

        if series_name:
            pending = [p for p in pending if p.series_name == series_name]

        return pending

    def get_completed_chapters(
        self, series_name: Optional[str] = None
    ) -> List[ChapterProgress]:
        """Get all completed chapters, optionally filtered by series."""
        completed = [
            progress
            for progress in self.progress.values()
            if progress.status == "completed"
        ]

        if series_name:
            completed = [p for p in completed if p.series_name == series_name]

        return completed

    def get_failed_chapters(
        self, series_name: Optional[str] = None
    ) -> List[ChapterProgress]:
        """Get all failed chapters, optionally filtered by series."""
        failed = [
            progress
            for progress in self.progress.values()
            if progress.status == "failed"
        ]

        if series_name:
            failed = [p for p in failed if p.series_name == series_name]

        return failed

    def reset_series(self, series_name: str) -> None:
        """Reset all chapters for a series to pending status."""
        for progress in self.progress.values():
            if progress.series_name == series_name:
                progress.status = "pending"
                progress.started_at = None
                progress.completed_at = None
                progress.error_message = None
        self.save_progress()

    def clear_completed(self) -> None:
        """Remove all completed chapters from tracking."""
        keys_to_remove = [
            key
            for key, progress in self.progress.items()
            if progress.status == "completed"
        ]
        for key in keys_to_remove:
            del self.progress[key]
        self.save_progress()

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of progress."""
        total = len(self.progress)
        completed = len(self.get_completed_chapters())
        failed = len(self.get_failed_chapters())
        pending = len(self.get_pending_chapters())

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "completion_rate": (completed / total * 100) if total > 0 else 0,
        }
