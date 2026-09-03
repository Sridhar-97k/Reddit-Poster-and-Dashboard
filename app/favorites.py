import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class FavoritesManager:
    def __init__(self, filepath='subreddit_favorites.json'):
        self.filepath = filepath
        self.favorites = []  # list of {'name': str, 'added': iso str}

    def load(self):
        try:
            with open(self.filepath) as f:
                self.favorites = json.load(f).get('favorites', [])
            logger.info(f"Loaded {len(self.favorites)} favorites")
        except FileNotFoundError:
            self.favorites = []
        except Exception as e:
            logger.error(f"Failed to load favorites: {e}")
            self.favorites = []

    def save(self):
        try:
            with open(self.filepath, 'w') as f:
                json.dump({'favorites': self.favorites, 'last_updated': datetime.now().isoformat()}, f, indent=4)
            logger.info(f"Saved {len(self.favorites)} favorites")
            return True
        except Exception as e:
            logger.error(f"Failed to save favorites: {e}")
            return False

    def add(self, name):
        """Add a subreddit by name (lowercase, no r/ prefix). Returns False if already exists."""
        name = name.lower().removeprefix('r/')
        if any(f['name'] == name for f in self.favorites):
            return False
        self.favorites.append({'name': name, 'added': datetime.now().isoformat()})
        self.save()
        return True

    def remove(self, name):
        """Remove a subreddit by name. Returns False if not found."""
        before = len(self.favorites)
        self.favorites = [f for f in self.favorites if f['name'] != name]
        if len(self.favorites) == before:
            return False
        self.save()
        return True

    def sorted_by_name(self):
        """Return favorites sorted alphabetically by name."""
        return sorted(self.favorites, key=lambda x: x['name'])
