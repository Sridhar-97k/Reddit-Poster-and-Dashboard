# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the GUI desktop app
python main.py

# Run the CLI tools
python cli/share.py --excel posts.xlsx
python cli/share.py --excel posts.xlsx --dry-run
python cli/flair.py --subreddit python
python cli/flair.py --subreddit python --csv data/python_flairs.csv

# Build Windows executable
python scripts/build_exe.py

# Install dependencies
pip install -r requirements.txt
pip install pyinstaller  # only needed for building .exe
```

## Repository layout

```
reddit_share/
├── main.py                  # Entry point (QApplication setup)
├── run_app.bat              # Windows double-click launcher
├── requirements.txt         # pip dependencies
│
├── app/                     # GUI application package
│   ├── __init__.py          # Exports ROOT_DIR, DATA_DIR
│   ├── dashboard.py         # RedditDashboard(QMainWindow) — assembles tabs, owns reddit instance
│   ├── workers.py           # RedditWorker, KarmaWorker, BulkKarmaUpdateWorker (QThread subclasses)
│   ├── post_log.py          # PostLog — openpyxl operations on reddit_posts_log.xlsx
│   ├── favorites.py         # FavoritesManager — JSON favorites CRUD
│   ├── utils.py             # export_table_to_excel() shared helper
│   ├── tabs/
│   │   ├── config_tab.py    # ConfigTab(QWidget) — credential form
│   │   ├── subreddits_tab.py# SubredditsTab(QWidget) — favorites management UI
│   │   ├── import_tab.py    # ImportTab(QWidget) — editable SpreadsheetWidget + Excel I/O
│   │   ├── submit_tab.py    # SubmitTab(QWidget) — batch submission + progress
│   │   ├── karma_tab.py     # KarmaTab(QWidget) — karma stats, search, bulk update
│   │   └── results_tab.py   # ResultsTab(QWidget) — submission results table
│   └── widgets/
│       └── spreadsheet.py   # SpreadsheetWidget — Excel-like editing (copy/paste, fill handle)
│
├── cli/
│   ├── share.py             # Bulk poster CLI (reads data/reddit_config.json)
│   └── flair.py             # Lists link flair templates for a subreddit
│
├── scripts/
│   └── build_exe.py         # PyInstaller wrapper
│
└── data/                    # Runtime data — do not commit
    ├── reddit_config.json   # Reddit API credentials
    ├── subreddit_favorites.json
    └── reddit_posts_log.xlsx
```

## Architecture

**`app/__init__.py`** exports `DATA_DIR` (absolute path to `data/`). `dashboard.py` imports it to pass concrete file paths into `PostLog`, `FavoritesManager`, and `ConfigTab` — those classes accept filepath as a constructor argument and have no hardcoded paths.

**Dependency injection:** `dashboard.py` owns the `praw.Reddit` instance and passes `self._get_reddit` (a callable) to every tab that needs Reddit access. Tabs call it on-demand; the dashboard caches the instance keyed on the credential tuple and only rebuilds when credentials change or are saved.

**Cross-tab signals wired in `dashboard._build_ui`:**
- `ConfigTab.credentials_saved` → invalidates cached reddit instance
- `ConfigTab.test_requested` → `dashboard._test_connection()`
- `SubmitTab.submission_finished(dict)` → `dashboard._on_submission_finished()` → `ResultsTab.show_results()` + tab switch

**`SubmitTab`** receives `get_posts` (callable to `ImportTab.get_posts`) and calls it at submit time to read the live table state — no stale cached list.

**`post_log.py` and `favorites.py` have no Qt dependency** — pure Python, independently testable.

**`app/widgets/spreadsheet.py` — `SpreadsheetWidget`:** multi-cell Ctrl+C/V (TSV, Excel-compatible), tiling paste, Delete to clear, fill handle drag with arithmetic series detection. The `_FillHandle` overlay widget uses `grabMouse()` during drag and a `QRubberBand` for preview.

## Thread safety

All PRAW API calls happen inside worker threads (`app/workers.py`), never on the main thread. UI updates flow through Qt signals. Worker references are held as instance variables on the tab to prevent GC while running. `dashboard.closeEvent` calls each tab's `stop_*_on_close()` with a 3-second wait before terminating.

## CLI tools

**`cli/share.py`** — bulk poster. Reads `data/reddit_config.json`. Excel sheet named `posts` with columns `title`, `link`, `subreddit`, `crosspost` (CSV). Configure flairs in `PRIMARY_FLAIRS` / `CROSSPOST_FLAIRS` dicts at the top of the file.

**`cli/flair.py`** — lists post flair templates for a subreddit. Reads same config file. Use `--csv` to save output.
