# Reddit Dashboard

A Windows desktop application for batch-posting to Reddit, tracking karma, and managing post workflows — without touching the Reddit website.

![Platform](https://img.shields.io/badge/platform-Windows-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)

---

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

Or double-click `run_app.bat` (installs nothing — you must run `pip install -r requirements.txt` first).

To build a standalone `.exe`:
```bash
pip install pyinstaller
python scripts/build_exe.py
# output: dist/RedditDashboard.exe
```

---

## Reddit App Setup (one-time)

1. Go to [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)
2. Click **Create App** → choose type **script**
3. Set redirect URI to `http://localhost:8080`
4. Copy **Client ID** (under the app name) and **Client Secret**
5. In the app, go to **Configuration** tab → enter credentials → **Save** → **Test Connection**

Credentials are stored in `data/reddit_config.json`. Do not commit this file.

---

## Features

### Search & import
- Query Reddit directly using Lucene syntax (e.g., `title:python url:github.com`)
- View thumbnail previews of search results
- Select and load search results directly into the Import tab with one click

### Built-in spreadsheet editor
The **Import Excel** tab is an editable grid — no external Excel needed:
- Type directly into cells
- `Ctrl+C` / `Ctrl+V` copy and paste (compatible with Excel clipboard format)
- Paste to a larger selection tiles the data to fill it
- Fill handle (blue square at bottom-right of selection) — drag to repeat values or continue an arithmetic series (`1, 2, 3` → `4, 5, 6`)
- `Delete` clears selected cells
- Import from / export to `.xlsx` at any time

Post columns: **subreddit** · **title** · **url** · **flair** (optional)

### Batch submission
- Configurable delay between posts (default 30 s; Reddit enforces ~10 min for new accounts)
- On rate-limit error, waits the Reddit-mandated time and retries once automatically
- Live progress log and stop button

### Post-submission results
- View a comprehensive summary of successful and failed posts after a batch submission
- Review exact error reasons for failed posts (e.g., rate limits, missing flair)
- One-click export of the results log to an Excel file

### Karma tracker
- View and refresh scores for your N most recent posts
- Search posts by subreddit
- One-click bulk karma update for all entries in the post log
- Export to Excel

### Subreddit favourites
- Save frequently used subreddits; usage count increments automatically after each successful post
- Import from your post history or a text file
- Generate a pre-filled template spreadsheet from your favourites list

---

## CLI Tools

Both tools read credentials from `data/reddit_config.json`.

```bash
# Bulk poster with crosspost support
python cli/share.py --excel posts.xlsx
python cli/share.py --excel posts.xlsx --dry-run

# List post flair templates for a subreddit
python cli/flair.py --subreddit python
python cli/flair.py --subreddit python --csv data/python_flairs.csv
```

`cli/share.py` reads an Excel sheet named **posts** with columns `title`, `link`, `subreddit`, `crosspost` (comma-separated list of subreddits for crossposting). Configure per-subreddit flairs via `PRIMARY_FLAIRS` / `CROSSPOST_FLAIRS` dicts at the top of the file.

---

## Repository Layout

```
reddit_share/
├── main.py                  # Entry point
├── run_app.bat              # Windows launcher
├── requirements.txt
│
├── app/                     # GUI application package
│   ├── dashboard.py         # Main window — assembles tabs, owns Reddit connection
│   ├── workers.py           # Background threads (QThread subclasses)
│   ├── post_log.py          # Post log Excel operations
│   ├── favorites.py         # Favourites JSON operations
│   ├── utils.py             # Shared Excel export helper
│   ├── tabs/                # One QWidget per tab
│   │   ├── search_tab.py    # Reddit search and import
│   │   ├── import_tab.py    # Posts spreadsheet editor
│   │   ├── submit_tab.py    # Batch submitter
│   │   ├── results_tab.py   # Post-submission summary and log
│   │   ├── karma_tab.py     # Karma tracker
│   │   ├── subreddits_tab.py# Subreddit favourites manager
│   │   └── config_tab.py    # Credentials configuration
│   └── widgets/
│       └── spreadsheet.py   # SpreadsheetWidget (editable grid)
│
├── cli/
│   ├── share.py             # Bulk poster + crossposting
│   └── flair.py             # Flair template lister
│
├── scripts/
│   └── build_exe.py         # PyInstaller wrapper
│
└── data/                    # Runtime data — do not commit
    ├── reddit_config.json
    ├── subreddit_favorites.json
    └── reddit_posts_log.xlsx
```

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| "invalid_grant" on connect | Username/password wrong, or 2FA enabled (disable it) |
| "401 Unauthorized" | Client ID or Secret is wrong; app type must be "script" |
| Posts fail after the first | Increase delay in Batch Submit tab; Reddit rate-limits link posts heavily for new accounts |
| Flair not applied | Run `cli/flair.py` to get the exact flair IDs, then set them in `cli/share.py` |
| Excel import shows no rows | Row 1 must be headers; all of subreddit, title, and url must be filled |

---

## Security

- `data/reddit_config.json` stores credentials in plain text — keep it out of version control
- No telemetry, no cloud connection, no data leaves your machine

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `praw` | Reddit API |
| `PyQt5` | Desktop GUI |
| `openpyxl` | Excel read/write |
| `pandas` | CLI Excel parsing (`cli/share.py`) |
| `requests` | HTTP (PRAW dependency) |
