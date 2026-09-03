import os
import sys
import csv
import subprocess
import logging
from datetime import datetime

from .csv_utils import safe_row

logger = logging.getLogger(__name__)

HEADERS = [
    'Post ID', 'Posted Date', 'Posted Time', 'Subreddit',
    'Title', 'URL', 'Reddit Link', 'Score', 'Comments',
    'Last Updated', 'Status', 'Notes'
]

# Column indices used when updating rows in place
COL_ID, COL_SCORE, COL_COMMENTS, COL_UPDATED = 0, 7, 8, 9


class PostLog:
    def __init__(self, filepath='reddit_posts_log.csv'):
        self.filepath = filepath

    def initialize(self):
        """Create the log file with a header row if it doesn't already exist."""
        if os.path.exists(self.filepath):
            logger.info(f"Post log exists: {self.filepath}")
            return
        try:
            with open(self.filepath, 'w', newline='', encoding='utf-8-sig') as f:
                csv.writer(f).writerow(HEADERS)
            logger.info(f"Created post log: {self.filepath}")
        except Exception as e:
            logger.error(f"Failed to create post log: {e}")

    def log_post(self, post_data):
        """Append one successfully submitted post to the log."""
        try:
            now = datetime.now()
            row = [
                post_data.get('id', ''),
                now.strftime('%Y-%m-%d'),
                now.strftime('%H:%M:%S'),
                post_data.get('subreddit', ''),
                post_data.get('title', ''),
                post_data.get('url', ''),
                post_data.get('permalink', ''),
                post_data.get('score', 0),
                post_data.get('comments', 0),
                now.strftime('%Y-%m-%d %H:%M:%S'),
                'Posted',
                '',
            ]
            with open(self.filepath, 'a', newline='', encoding='utf-8-sig') as f:
                csv.writer(f).writerow(safe_row(row))
            logger.info(f"Logged post: {post_data.get('title', '')[:40]}")
            return True
        except Exception as e:
            logger.error(f"Failed to log post: {e}")
            return False

    def upsert_posts(self, posts):
        """Insert or update posts (matched by id). Used to sync the user's full
        submission history into the log. `posts` is a list of dicts with keys
        id, subreddit, title, url, permalink, score, comments, and created
        (a datetime). Returns the number of posts processed."""
        rows = self._read() or [list(HEADERS)]
        if not rows:
            rows = [list(HEADERS)]
        index = {r[COL_ID]: r for r in rows[1:] if r and r[COL_ID]}

        for p in posts:
            pid = p.get('id', '')
            if not pid:
                continue
            row = index.get(pid)
            if row is None:
                row = [''] * len(HEADERS)
                row[COL_ID] = pid
                rows.append(row)
                index[pid] = row
            self._pad(row)
            created = p.get('created')
            if created is not None:
                row[1] = created.strftime('%Y-%m-%d')
                row[2] = created.strftime('%H:%M:%S')
            row[3] = p.get('subreddit', '')
            row[4] = p.get('title', '')
            row[5] = p.get('url', '')
            row[6] = p.get('permalink', '')
            row[COL_SCORE] = p.get('score', 0)
            row[COL_COMMENTS] = p.get('comments', 0)
            row[COL_UPDATED] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            if not row[10]:
                row[10] = 'Posted'

        self._write(rows)
        return len(posts)

    def update_karma(self, post_id, score, comments):
        """Update score and comment count for a specific post ID."""
        rows = self._read()
        if rows is None:
            return False
        for row in rows[1:]:
            if row and row[COL_ID] == post_id:
                self._pad(row)
                row[COL_SCORE] = score
                row[COL_COMMENTS] = comments
                row[COL_UPDATED] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                return self._write(rows)
        logger.warning(f"Post {post_id} not found in log")
        return False

    def get_stats(self):
        """Return aggregate stats from the log, or None on error."""
        rows = self._read()
        if rows is None:
            return None
        try:
            data = [r for r in rows[1:] if r and r[COL_ID]]
            total_posts = len(data)
            total_karma = sum(self._as_int(r, COL_SCORE) for r in data)
            total_comments = sum(self._as_int(r, COL_COMMENTS) for r in data)
            return {
                'total_posts': total_posts,
                'total_karma': total_karma,
                'total_comments': total_comments,
                'avg_karma': total_karma / total_posts if total_posts > 0 else 0,
            }
        except Exception as e:
            logger.error(f"Failed to get log stats: {e}")
            return None

    def open_file(self):
        """Open the log file in the system default application."""
        if not os.path.exists(self.filepath):
            return False
        try:
            if sys.platform == 'win32':
                os.startfile(self.filepath)
            elif sys.platform == 'darwin':
                subprocess.run(['open', self.filepath], check=False)
            else:
                subprocess.run(['xdg-open', self.filepath], check=False)
            return True
        except Exception as e:
            logger.error(f"Failed to open log file: {e}")
            return False

    # ------------------------------------------------------------------ helpers

    def _read(self):
        if not os.path.exists(self.filepath):
            return None
        try:
            with open(self.filepath, newline='', encoding='utf-8-sig') as f:
                return list(csv.reader(f))
        except Exception as e:
            logger.error(f"Failed to read post log: {e}")
            return None

    def _write(self, rows):
        try:
            with open(self.filepath, 'w', newline='', encoding='utf-8-sig') as f:
                csv.writer(f).writerows(safe_row(r) for r in rows)
            return True
        except Exception as e:
            logger.error(f"Failed to write post log: {e}")
            return False

    @staticmethod
    def _pad(row, size=len(HEADERS)):
        while len(row) < size:
            row.append('')

    @staticmethod
    def _as_int(row, idx):
        try:
            return int(float(row[idx])) if idx < len(row) and row[idx] != '' else 0
        except (ValueError, TypeError):
            return 0
