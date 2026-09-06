import re
import logging
from datetime import datetime

from PyQt5.QtCore import QThread, pyqtSignal
from praw.exceptions import RedditAPIException
from prawcore.exceptions import Forbidden

logger = logging.getLogger(__name__)


def link_flair_label(template):
    """Visible text for a link-flair template, handling richtext/emoji flairs
    whose plain `text` field is empty."""
    text = (template.get('text') or '').strip()
    if text:
        return text
    segments = template.get('richtext') or []
    return ''.join(seg.get('t', '') for seg in segments).strip()


def _from_mod_template(t):
    """Normalize one r/<sub>/api/link_flair_v2 template (moderator view)."""
    return {
        'id': t.get('id'),
        'text': t.get('text') or '',
        'richtext': t.get('richtext') or [],
        'mod_only': bool(t.get('mod_only')),
    }


def _from_selectable_choice(c):
    """Normalize one /api/flairselector choice (regular-user view).

    That endpoint only ever returns templates the account may actually apply,
    so mod_only is False by construction."""
    return {
        'id': c.get('flair_template_id'),
        'text': c.get('flair_text') or '',
        'richtext': c.get('flair_richtext') or [],
        'mod_only': False,
    }


def fetch_link_flairs(subreddit):
    """Return a subreddit's link-flair templates as normalized dicts with the
    keys 'id', 'text', 'richtext' and 'mod_only'.

    Prefers `flair.link_templates` (r/<sub>/api/link_flair_v2), which lists every
    template including mod-only ones. That endpoint is mod-privileged, though —
    plenty of subreddits answer a non-moderator with 403 — so on Forbidden fall
    back to `user_selectable()` (/api/flairselector), the same call the Reddit
    submit page makes. The fallback sees only user-selectable templates, which is
    exactly the set we can attach at submit time anyway.

    Both shapes are normalized to one dict so callers need not know which
    endpoint answered."""
    try:
        return [_from_mod_template(t) for t in subreddit.flair.link_templates]
    except Forbidden:
        logger.info("r/%s: link_flair_v2 forbidden (not a moderator) — "
                    "falling back to the user-selectable flair list", subreddit)
        return [_from_selectable_choice(c)
                for c in subreddit.flair.link_templates.user_selectable()]


class RedditWorker(QThread):
    """Submits a list of posts to Reddit one by one on a background thread."""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, reddit, posts_data, start_index=0, delay_secs=30):
        super().__init__()
        self.reddit = reddit
        self.posts_data = posts_data
        self.start_index = start_index
        self.delay_secs = delay_secs
        self.is_running = True

    def _interruptible_sleep(self, total_secs):
        """Sleep in 1-second chunks so stop() can interrupt a long wait."""
        for _ in range(total_secs):
            if not self.is_running:
                break
            self.msleep(1000)

    def _parse_ratelimit_wait(self, error_msg):
        """Return seconds to wait extracted from a RATELIMIT error message."""
        m = re.search(r'try again in (\d+) minute', error_msg, re.IGNORECASE)
        if m:
            return int(m.group(1)) * 60
        m = re.search(r'try again in (\d+) second', error_msg, re.IGNORECASE)
        if m:
            return int(m.group(1))
        return 600  # conservative fallback: 10 minutes

    @staticmethod
    def _template_label(template):
        return link_flair_label(template)

    def _resolve_flair_id(self, sub, subreddit, flair_text, idx):
        """Resolve `flair_text` to a link-flair template id for r/<subreddit>.

        Uses the subreddit's link-flair templates (not a submission's choices) so
        the flair can be attached *at submit time* — required by subreddits that
        enforce flair before a post is accepted. Returns the template id, or None
        if nothing matched (in which case the available flairs are logged)."""
        try:
            templates = fetch_link_flairs(sub)
        except Exception as e:
            self.progress.emit(idx + 1, f"⚠️ Could not load flairs for r/{subreddit}: {str(e)[:60]}")
            logger.warning("Could not load link flair templates for r/%s: %s", subreddit, e)
            return None

        want = flair_text.strip().lower()
        # Only user-selectable (non mod-only) templates can be applied on submit
        labels = [(t, self._template_label(t).lower())
                  for t in templates if not t.get('mod_only')]

        matched = (
            next((t for t, lbl in labels if lbl and lbl == want), None)
            or next((t for t, lbl in labels if lbl and want in lbl), None)
            or next((t for t, lbl in labels if lbl and lbl in want), None)
        )
        if matched:
            return matched['id']

        # No match — dump the full template list to the background log for debugging
        logger.warning("Flair '%s' not matched in r/%s — %d template(s):",
                       flair_text, subreddit, len(templates))
        for t in templates:
            logger.warning(
                "  id=%s | text=%r | label=%r | mod_only=%s",
                t.get('id'), t.get('text'), self._template_label(t), t.get('mod_only'),
            )
        available = [self._template_label(t) or '(blank/editable)'
                     for t in templates if not t.get('mod_only')]
        if available:
            self.progress.emit(idx + 1,
                f"⚠️ Flair '{flair_text}' not found in r/{subreddit}. Available: {', '.join(available)}")
        else:
            self.progress.emit(idx + 1,
                f"⚠️ r/{subreddit} has no user-selectable link flairs (or flair is disabled)")
        return None

    def _try_submit(self, subreddit, title, url, flair_text, idx):
        """Submit one post — attaching flair at submit time — and return it."""
        sub = self.reddit.subreddit(subreddit)

        flair_id = None
        if flair_text:
            flair_id = self._resolve_flair_id(sub, subreddit, flair_text, idx)

        if flair_id:
            submission = sub.submit(title=title, url=url, flair_id=flair_id)
            self.progress.emit(idx + 1, f"Submitted to r/{subreddit} with flair '{flair_text}'")
        else:
            submission = sub.submit(title=title, url=url)

        return submission

    def run(self):
        results = {
            'successful': [],
            'failed': [],
            'total': len(self.posts_data)
        }

        for idx, post in enumerate(self.posts_data):
            if not self.is_running:
                break

            subreddit = post.get('subreddit', '').strip()
            title = post.get('title', '').strip()
            url = post.get('url', '').strip()
            flair_text = post.get('flair', '').strip()
            row_num = self.start_index + idx

            if not subreddit or not title or not url:
                results['failed'].append({
                    'row': row_num,
                    'reason': 'Missing required fields',
                    'post': post
                })
                logger.warning("Skipped row %s: missing required field(s) — subreddit=%r title=%r url=%r",
                               row_num, subreddit, title, url)
                self.progress.emit(idx + 1, f"Skipped row {row_num}: Missing data")
                continue

            try:
                submission = self._try_submit(subreddit, title, url, flair_text, idx)
                results['successful'].append({
                    'row': row_num,
                    'subreddit': subreddit,
                    'title': title,
                    'url': submission.url,
                    'permalink': f"https://reddit.com{submission.permalink}",
                    'id': submission.id
                })
                self.progress.emit(idx + 1, f"✅ Posted to r/{subreddit}: {title[:50]}...")

            except RedditAPIException as e:
                is_ratelimit = any(
                    getattr(item, 'error_type', '') == 'RATELIMIT' for item in e.items
                )
                if is_ratelimit:
                    wait_secs = self._parse_ratelimit_wait(str(e))
                    self.progress.emit(idx + 1, f"⏳ Rate limited — waiting {wait_secs}s then retrying r/{subreddit}...")
                    self._interruptible_sleep(wait_secs)
                    if not self.is_running:
                        break
                    try:
                        submission = self._try_submit(subreddit, title, url, flair_text, idx)
                        results['successful'].append({
                            'row': row_num,
                            'subreddit': subreddit,
                            'title': title,
                            'url': submission.url,
                            'permalink': f"https://reddit.com{submission.permalink}",
                            'id': submission.id
                        })
                        self.progress.emit(idx + 1, f"✅ Posted to r/{subreddit} (after rate limit wait): {title[:50]}...")
                    except Exception as retry_e:
                        results['failed'].append({'row': row_num, 'reason': str(retry_e), 'post': post})
                        logger.error("Retry failed row %s (r/%s): %s", row_num, subreddit, retry_e, exc_info=True)
                        self.progress.emit(idx + 1, f"❌ Retry failed row {row_num}: {str(retry_e)[:50]}")
                else:
                    results['failed'].append({'row': row_num, 'reason': str(e), 'post': post})
                    logger.error("Submit failed row %s (r/%s): %s", row_num, subreddit, e, exc_info=True)
                    self.progress.emit(idx + 1, f"❌ Failed row {row_num}: {str(e)[:50]}")

            except Exception as e:
                results['failed'].append({'row': row_num, 'reason': str(e), 'post': post})
                logger.error("Error submitting row %s (r/%s): %s", row_num, subreddit, e, exc_info=True)
                self.progress.emit(idx + 1, f"❌ Error row {row_num}: {str(e)[:50]}")

            if self.is_running and idx < len(self.posts_data) - 1:
                self.progress.emit(idx + 1, f"⏱️ Waiting {self.delay_secs}s before next post...")
                self._interruptible_sleep(self.delay_secs)

        self.finished.emit(results)

    def stop(self):
        self.is_running = False


class UserPostsWorker(QThread):
    """Fetches the authenticated user's submissions on a background thread.

    Handles three uses via its arguments:
      - recent view   : limit=N, no filter
      - full sync      : limit=None (whole history)
      - subreddit search: subreddit_filter set (case-insensitive substring)

    Emits progress(count_scanned) as it goes so long operations can show a bar.
    """
    progress = pyqtSignal(int)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, reddit, limit=None, subreddit_filter=None, title_filter=None,
                 sort_by_score=False):
        super().__init__()
        self.reddit = reddit
        self.limit = limit
        self.subreddit_filter = (subreddit_filter or '').strip().lower() or None
        self.title_filter = (title_filter or '').strip().lower() or None
        self.sort_by_score = sort_by_score
        self.is_running = True

    def run(self):
        try:
            user = self.reddit.user.me()
            posts = []
            for scanned, s in enumerate(user.submissions.new(limit=self.limit), 1):
                if not self.is_running:
                    break
                sub_name = s.subreddit.display_name
                sub_ok = self.subreddit_filter is None or self.subreddit_filter in sub_name.lower()
                title_ok = self.title_filter is None or self.title_filter in (s.title or '').lower()
                if sub_ok and title_ok:
                    posts.append({
                        'id': s.id,
                        'subreddit': sub_name,
                        'title': s.title,
                        'score': s.score,
                        'comments': s.num_comments,
                        'created': datetime.fromtimestamp(s.created_utc),
                        'url': s.url,
                        'permalink': f"https://reddit.com{s.permalink}",
                    })
                self.progress.emit(scanned)
            if self.sort_by_score:
                posts.sort(key=lambda p: p['score'], reverse=True)
            logger.info("UserPostsWorker: %d post(s) collected", len(posts))
            self.finished.emit(posts)
        except Exception as e:
            logger.error(f"UserPostsWorker: {e}", exc_info=True)
            self.error.emit(str(e))

    def stop(self):
        self.is_running = False


class FlairFetchWorker(QThread):
    """Fetches link-flair templates for a set of subreddits on a background thread."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)   # {subreddit_lower: [ {'text', 'id', 'mod_only'}, … ]}
    error = pyqtSignal(str)

    def __init__(self, reddit, subreddits):
        super().__init__()
        self.reddit = reddit
        self.subreddits = subreddits
        self.is_running = True

    def run(self):
        result = {}
        for sub in self.subreddits:
            if not self.is_running:
                break
            try:
                templates = fetch_link_flairs(self.reddit.subreddit(sub))
                flairs = [
                    {'text': link_flair_label(t), 'id': t.get('id'), 'mod_only': t['mod_only']}
                    for t in templates
                ]
                result[sub] = flairs
                self.progress.emit(f"r/{sub}: {len(flairs)} flair(s)")
                logger.info("FlairFetchWorker: r/%s → %d flair(s)", sub, len(flairs))
            except Exception as e:
                # Skip failed subreddits (private/banned/typo); reported via the summary
                self.progress.emit(f"r/{sub}: failed — {str(e)[:60]}")
                logger.warning("FlairFetchWorker: r/%s failed: %s", sub, e, exc_info=True)
        self.finished.emit(result)

    def stop(self):
        self.is_running = False
