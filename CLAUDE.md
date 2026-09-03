# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the GUI desktop app  (or double-click run_app.bat)
python main.py

# Run the CLI tool
python cli/flair.py --subreddit python
python cli/flair.py --subreddit python --csv data/python_flairs.csv

# Build Windows executable  (or double-click build.bat)
# Builds inside an isolated .build-venv (only requirements + PyInstaller) so the
# .exe is reproducible and slim. → dist/RedditDashboard.exe
python scripts/build_exe.py

# Install dependencies (run_app.bat/build.bat assume these are installed)
pip install -r requirements.txt
```

## Repository layout

```
reddit_share/
├── main.py                  # Entry point (QApplication setup)
├── run_app.bat              # Windows double-click launcher (run)
├── build.bat                # Windows double-click launcher (build .exe)
├── requirements.txt         # pip dependencies
│
├── app/                     # GUI application package
│   ├── __init__.py          # Exports ROOT_DIR, DATA_DIR
│   ├── dashboard.py         # RedditDashboard(QMainWindow) — assembles tabs, owns reddit instance
│   ├── workers.py           # RedditWorker, UserPostsWorker, FlairFetchWorker (QThread subclasses)
│   ├── post_log.py          # PostLog — CSV operations on reddit_posts_log.csv
│   ├── favorites.py         # FavoritesManager — JSON favorites CRUD
│   ├── utils.py             # export_table_to_csv() shared helper
│   ├── tabs/
│   │   ├── config_tab.py    # ConfigTab(QWidget) — credential form
│   │   ├── subreddits_tab.py# SubredditsTab(QWidget) — favorites management UI
│   │   ├── import_tab.py    # ImportTab(QWidget) — editable SpreadsheetWidget + CSV export
│   │   ├── submit_tab.py    # SubmitTab(QWidget) — batch submission + progress
│   │   ├── karma_tab.py     # KarmaTab(QWidget) — karma stats, search, bulk update
│   │   └── results_tab.py   # ResultsTab(QWidget) — submission results table
│   └── widgets/
│       └── spreadsheet.py   # SpreadsheetWidget — Excel-like editing (copy/paste, fill handle)
│
├── cli/
│   └── flair.py             # Lists link flair templates for a subreddit
│
├── scripts/
│   ├── build_exe.py         # Isolated-venv build framework (prep→icons→clean→bundle)
│   └── make_icons.py        # Generates assets/icon.png + icon.ico from Qt painter
│
├── assets/                  # App icon (committed)
│   ├── icon.png             # 256x256 window/taskbar icon
│   └── icon.ico             # multi-size Windows .exe icon
│
└── data/                    # Runtime data — do not commit (except the template)
    ├── reddit_config.example.json  # committed credential template
    ├── reddit_config.json   # Reddit API credentials
    ├── subreddit_favorites.json
    ├── subreddit_flairs.csv # flair database
    └── reddit_posts_log.csv
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

**`cli/flair.py`** — lists post flair templates for a subreddit. Reads `data/reddit_config.json`. Use `--csv` to save output.

> A bulk-poster CLI (`cli/share.py`, Excel-driven) was removed. The GUI's Batch Submit tab is the batch-posting path. Re-add an Excel/CLI flow only if the need returns.
