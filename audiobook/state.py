"""SQLite-backed chapter status tracking for the audiobook pipeline."""

import os
import sqlite3
from datetime import datetime, timezone


class ChapterDB:
    """Tracks series metadata and per-chapter processing status in a SQLite database.

    The database lives alongside the output files (typically ``{output_dir}/audiobook.db``)
    and acts as a single source of truth for what has been scraped, what needs processing,
    and what has failed.

    Usage::

        with ChapterDB("output/audiobook.db") as db:
            db.upsert_series("My Series", narrator="travis_baldree")
            db.register("My Series", "Chapter 1", "/path/to/raw.txt")
            db.mark_processing("/path/to/raw.txt", "/path/to/output.wav")
            db.mark_done("/path/to/raw.txt")
    """

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS series (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        url TEXT,
        source TEXT,
        narrator TEXT,
        latest_url TEXT,
        last_scraped_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS chapters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        series_id INTEGER NOT NULL REFERENCES series(id),
        title TEXT NOT NULL,
        published_date TEXT,
        source_url TEXT,
        chapter_index INTEGER,
        raw_path TEXT NOT NULL UNIQUE,
        output_path TEXT,
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK(status IN ('pending','processing','done','failed')),
        error TEXT,
        retry_count INTEGER NOT NULL DEFAULT 0,
        scraped_at TEXT NOT NULL DEFAULT (datetime('now')),
        checked_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_chapters_series_status
        ON chapters(series_id, status);
    """

    def __init__(self, db_path):
        self._db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(self._SCHEMA)
        self._conn.commit()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _now(self):
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # ── Series ──────────────────────────────────────────────────────

    def upsert_series(self, name, url=None, source=None, narrator=None, latest_url=None):
        """Insert or update a series by name. Returns the series id."""
        now = self._now()
        cur = self._conn.execute("SELECT id FROM series WHERE name = ?", (name,))
        row = cur.fetchone()
        if row:
            self._conn.execute(
                """UPDATE series
                   SET url = COALESCE(?, url),
                       source = COALESCE(?, source),
                       narrator = COALESCE(?, narrator),
                       latest_url = COALESCE(?, latest_url),
                       last_scraped_at = ?,
                       updated_at = ?
                   WHERE id = ?""",
                (url, source, narrator, latest_url, now, now, row["id"]),
            )
            self._conn.commit()
            return row["id"]
        else:
            cur = self._conn.execute(
                """INSERT INTO series (name, url, source, narrator, latest_url,
                                      last_scraped_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, url, source, narrator, latest_url, now, now, now),
            )
            self._conn.commit()
            return cur.lastrowid

    def get_series(self, name):
        """Return a series row as a dict, or None."""
        cur = self._conn.execute("SELECT * FROM series WHERE name = ?", (name,))
        row = cur.fetchone()
        return dict(row) if row else None

    # ── Chapter registration ────────────────────────────────────────

    def register(self, series_name, title, raw_path, published_date=None,
                 source_url=None, chapter_index=None):
        """Idempotent chapter registration. Returns the chapter id."""
        series = self.get_series(series_name)
        if not series:
            series_id = self.upsert_series(series_name)
        else:
            series_id = series["id"]

        now = self._now()
        cur = self._conn.execute("SELECT id FROM chapters WHERE raw_path = ?", (raw_path,))
        row = cur.fetchone()
        if row:
            return row["id"]

        cur = self._conn.execute(
            """INSERT INTO chapters
                   (series_id, title, published_date, source_url,
                    chapter_index, raw_path, scraped_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (series_id, title, published_date, source_url,
             chapter_index, raw_path, now, now, now),
        )
        self._conn.commit()
        return cur.lastrowid

    # ── Status transitions ──────────────────────────────────────────

    def mark_processing(self, raw_path, output_path):
        now = self._now()
        self._conn.execute(
            "UPDATE chapters SET status='processing', output_path=?, updated_at=? WHERE raw_path=?",
            (output_path, now, raw_path),
        )
        self._conn.commit()

    def mark_done(self, raw_path, output_path=None):
        now = self._now()
        if output_path:
            self._conn.execute(
                "UPDATE chapters SET status='done', error=NULL, output_path=?, updated_at=? WHERE raw_path=?",
                (output_path, now, raw_path),
            )
        else:
            self._conn.execute(
                "UPDATE chapters SET status='done', error=NULL, updated_at=? WHERE raw_path=?",
                (now, raw_path),
            )
        self._conn.commit()

    def mark_failed(self, raw_path, error):
        now = self._now()
        self._conn.execute(
            """UPDATE chapters
               SET status='failed', error=?, retry_count=retry_count+1, updated_at=?
               WHERE raw_path=?""",
            (str(error), now, raw_path),
        )
        self._conn.commit()

    def mark_checked(self, raw_path):
        now = self._now()
        self._conn.execute(
            "UPDATE chapters SET checked_at=?, updated_at=? WHERE raw_path=?",
            (now, now, raw_path),
        )
        self._conn.commit()

    def update_source_url(self, chapter_id, source_url):
        """Set the source_url on a chapter row."""
        now = self._now()
        self._conn.execute(
            "UPDATE chapters SET source_url=?, updated_at=? WHERE id=?",
            (source_url, now, chapter_id),
        )
        self._conn.commit()

    def reset_chapter(self, raw_path):
        """Reset a chapter to pending status for reprocessing."""
        now = self._now()
        self._conn.execute(
            "UPDATE chapters SET status='pending', error=NULL, output_path=NULL, updated_at=? WHERE raw_path=?",
            (now, raw_path),
        )
        self._conn.commit()

    # ── Queries ─────────────────────────────────────────────────────

    def get_chapter_by_id(self, chapter_id):
        """Return a chapter row as a dict, or None."""
        cur = self._conn.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def get_actionable(self, series_name):
        """Return chapters that need processing (pending or failed), ordered for processing."""
        series = self.get_series(series_name)
        if not series:
            return []
        cur = self._conn.execute(
            """SELECT * FROM chapters
               WHERE series_id = ? AND status IN ('pending', 'failed')
               ORDER BY COALESCE(chapter_index, 999999), published_date, raw_path""",
            (series["id"],),
        )
        return [dict(r) for r in cur.fetchall()]

    def get_chapters(self, series_name, status=None):
        """All chapters for a series, optionally filtered by status."""
        series = self.get_series(series_name)
        if not series:
            return []
        if status:
            cur = self._conn.execute(
                "SELECT * FROM chapters WHERE series_id = ? AND status = ? ORDER BY raw_path",
                (series["id"], status),
            )
        else:
            cur = self._conn.execute(
                "SELECT * FROM chapters WHERE series_id = ? ORDER BY raw_path",
                (series["id"],),
            )
        return [dict(r) for r in cur.fetchall()]

    def summary(self, series_name=None):
        """Return status counts: ``{'pending': N, 'processing': N, 'done': N, 'failed': N}``."""
        counts = {"pending": 0, "processing": 0, "done": 0, "failed": 0}
        if series_name:
            series = self.get_series(series_name)
            if not series:
                return counts
            cur = self._conn.execute(
                "SELECT status, COUNT(*) FROM chapters WHERE series_id = ? GROUP BY status",
                (series["id"],),
            )
        else:
            cur = self._conn.execute("SELECT status, COUNT(*) FROM chapters GROUP BY status")
        for row in cur.fetchall():
            counts[row[0]] = row[1]
        return counts

    # ── Backward compatibility ──────────────────────────────────────

    def sync_filesystem(self, series_name, raws_dir, output_dir):
        """Reconcile DB state with the filesystem.

        1. Reset stale 'processing' rows back to 'pending' (crash recovery).
        2. Register any .txt files in *raws_dir* not yet tracked.
        3. Mark chapters whose output .mp3 or .wav already exists as 'done'.
        """
        series = self.get_series(series_name)
        if not series:
            return
        series_id = series["id"]
        now = self._now()

        # 1. Reset stale processing → pending
        reset_cur = self._conn.execute(
            "UPDATE chapters SET status='pending', updated_at=? WHERE series_id=? AND status='processing'",
            (now, series_id),
        )
        if reset_cur.rowcount:
            print(f"[sync] {series_name}: reset {reset_cur.rowcount} stale processing → pending")

        # 2. Register untracked .txt files
        registered = 0
        if os.path.isdir(raws_dir):
            for fname in os.listdir(raws_dir):
                if not fname.endswith(".txt") or fname.endswith("_cleaned.txt"):
                    continue
                raw_path = os.path.join(raws_dir, fname)
                # Derive title from filename: strip date prefix and extension
                base = os.path.splitext(fname)[0]
                title = base.split("_", 1)[-1] if "_" in base else base
                # Extract published_date from filename prefix if it looks like a date
                parts = base.split("_", 1)
                published_date = parts[0] if len(parts) > 1 else None
                existing = self._conn.execute(
                    "SELECT id FROM chapters WHERE raw_path = ?", (raw_path,)
                ).fetchone()
                self.register(series_name, title, raw_path, published_date=published_date)
                if not existing:
                    registered += 1
        if registered:
            print(f"[sync] {series_name}: registered {registered} new chapter(s) from filesystem")

        # 3. Mark chapters with existing output as done
        marked = 0
        cur = self._conn.execute(
            "SELECT raw_path FROM chapters WHERE series_id=? AND status != 'done'",
            (series_id,),
        )
        for row in cur.fetchall():
            raw = row["raw_path"]
            base = os.path.splitext(os.path.basename(raw))[0]
            mp3 = os.path.join(output_dir, f"{base}.mp3")
            wav = os.path.join(output_dir, f"{base}.wav")
            if os.path.exists(mp3) or os.path.exists(wav):
                self._conn.execute(
                    "UPDATE chapters SET status='done', output_path=?, updated_at=? WHERE raw_path=?",
                    (mp3 if os.path.exists(mp3) else wav, now, raw),
                )
                marked += 1
        if marked:
            print(f"[sync] {series_name}: marked {marked} chapter(s) done from existing audio")

        # 4. Reset 'done' chapters whose output no longer exists → pending
        reverted = 0
        cur = self._conn.execute(
            "SELECT raw_path, output_path FROM chapters WHERE series_id=? AND status='done'",
            (series_id,),
        )
        for row in cur.fetchall():
            out = row["output_path"]
            if out and not os.path.exists(out):
                self._conn.execute(
                    "UPDATE chapters SET status='pending', output_path=NULL, updated_at=? WHERE raw_path=?",
                    (now, row["raw_path"]),
                )
                reverted += 1
        if reverted:
            print(f"[sync] {series_name}: reverted {reverted} chapter(s) to pending (output missing)")

        # 5. Remove DB entries whose raw .txt no longer exists on disk
        removed = 0
        cur = self._conn.execute(
            "SELECT id, raw_path FROM chapters WHERE series_id=?",
            (series_id,),
        )
        for row in cur.fetchall():
            if not os.path.exists(row["raw_path"]):
                self._conn.execute("DELETE FROM chapters WHERE id=?", (row["id"],))
                removed += 1
        if removed:
            print(f"[sync] {series_name}: removed {removed} stale chapter(s) (raw file missing)")

        self._conn.commit()
