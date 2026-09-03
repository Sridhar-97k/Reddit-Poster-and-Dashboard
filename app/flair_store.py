import os
import csv
import logging
from datetime import datetime

from .csv_utils import safe_row

logger = logging.getLogger(__name__)

HEADERS = ['Subreddit', 'Flair Text', 'Flair ID', 'Mod Only', 'Last Updated']


class FlairStore:
    """CSV-backed cache of link flairs per subreddit.

    Acts as the flair 'database' that powers the flair dropdown in the Posts tab.
    One row per flair; the file is rewritten wholesale on each update (the data
    set is tiny, so this keeps the code simple and the file always consistent).

    In-memory shape:
        self._by_sub = {
            'python': {'updated': '2026-09-03 05:40:00',
                       'flairs': [{'text': 'Tutorial', 'id': 'abc-...', 'mod_only': False}, ...]},
            ...
        }
    """

    def __init__(self, filepath='subreddit_flairs.csv'):
        self.filepath = filepath
        self._by_sub = {}

    # ------------------------------------------------------------------ file

    def initialize(self):
        """Create the store file with a header row if it doesn't already exist."""
        if os.path.exists(self.filepath):
            return
        try:
            with open(self.filepath, 'w', newline='', encoding='utf-8-sig') as f:
                csv.writer(f).writerow(HEADERS)
            logger.info("Created flair store: %s", self.filepath)
        except Exception as e:
            logger.error("Failed to create flair store: %s", e)

    def load(self):
        """Load all rows from the CSV file into memory."""
        self._by_sub = {}
        if not os.path.exists(self.filepath):
            return
        try:
            with open(self.filepath, newline='', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                next(reader, None)  # skip header
                for row in reader:
                    if not row or not row[0]:
                        continue
                    sub = row[0].strip().lower()
                    text = row[1].strip() if len(row) > 1 else ''
                    fid = row[2].strip() if len(row) > 2 else ''
                    mod_only = (row[3].strip().lower() in ('1', 'true', 'yes')
                                if len(row) > 3 else False)
                    updated = row[4].strip() if len(row) > 4 else ''
                    entry = self._by_sub.setdefault(sub, {'updated': '', 'flairs': []})
                    entry['flairs'].append({'text': text, 'id': fid, 'mod_only': mod_only})
                    if updated > entry['updated']:
                        entry['updated'] = updated
            logger.info("Loaded flairs for %d subreddit(s)", len(self._by_sub))
        except Exception as e:
            logger.error("Failed to load flair store: %s", e)
            self._by_sub = {}

    def _save(self):
        try:
            with open(self.filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(HEADERS)
                for sub in sorted(self._by_sub):
                    entry = self._by_sub[sub]
                    for fl in entry['flairs']:
                        writer.writerow(safe_row([
                            sub,
                            fl.get('text', ''),
                            fl.get('id', ''),
                            'TRUE' if fl.get('mod_only') else 'FALSE',
                            entry.get('updated', ''),
                        ]))
            logger.info("Saved flair store (%d subreddit(s))", len(self._by_sub))
            return True
        except Exception as e:
            logger.error("Failed to save flair store: %s", e)
            return False

    # ------------------------------------------------------------------ api

    def update(self, subreddit, flairs):
        """Replace the stored flairs for a subreddit and persist to disk.

        `flairs` is a list of {'text', 'id', 'mod_only'} dicts."""
        self._by_sub[subreddit.strip().lower()] = {
            'updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'flairs': list(flairs),
        }
        self._save()

    def get_texts(self, subreddit):
        """User-selectable flair texts for a subreddit (mod-only excluded, de-duped)."""
        entry = self._by_sub.get((subreddit or '').strip().lower())
        if not entry:
            return []
        out = []
        for fl in entry['flairs']:
            t = fl.get('text', '')
            if t and not fl.get('mod_only') and t not in out:
                out.append(t)
        return out

    def get_id(self, subreddit, text):
        """Template id for an exact (case-insensitive) flair text, or None."""
        entry = self._by_sub.get((subreddit or '').strip().lower())
        if not entry:
            return None
        want = (text or '').strip().lower()
        for fl in entry['flairs']:
            if (fl.get('text', '') or '').strip().lower() == want:
                return fl.get('id') or None
        return None

    def subreddits(self):
        return sorted(self._by_sub.keys())
