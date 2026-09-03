# Reddit Dashboard

A Windows desktop app for **batch-posting links to Reddit**, managing flairs, and tracking karma — all from a spreadsheet-style interface, without touching the Reddit website.

![Platform](https://img.shields.io/badge/platform-Windows-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## Highlights

- 📋 **Spreadsheet editor** — compose posts in a spreadsheet-style grid (copy/paste, fill-handle, export `.csv` backup)
- 🔍 **Search & import** — find posts on Reddit with Lucene syntax and load them straight into your queue
- 🎨 **Flair database** — pull a subreddit's real flairs with one click and pick them from a dropdown; flair is attached *at submit time* so **flair-required subreddits work**
- 🚀 **Batch submission** — post many links with a configurable delay, automatic rate-limit back-off, and a detailed live log
- 📊 **Karma tracker** — refresh scores/comments for your recent posts and everything you've logged
- 🔒 **Local only** — credentials and data never leave your machine; nothing is committed to the repo

---

## Quick Start

```bash
git clone <your-fork-url> reddit_share
cd reddit_share
pip install -r requirements.txt
python main.py
```

On Windows you can also double-click **`run_app.bat`** (run `pip install -r requirements.txt` once first).

To build a standalone executable, double-click **`build.bat`** or run:

```bash
python scripts/build_exe.py     # → dist/RedditDashboard.exe
```

The build runs inside a dedicated, isolated virtual environment (`.build-venv/`) containing only this app's declared dependencies plus PyInstaller — so the executable is reproducible across machines and free of unrelated bloat. Four clearly-labelled stages: prepare build env → generate icons → clean → bundle.

---

## Reddit App Setup (one-time)

You need your own Reddit "script" app to get an API key. This is free and takes a minute.

1. Go to **[reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)**
2. Click **Create App** (or **Create Another App**) → choose type **script**
3. Set the redirect URI to `http://localhost:8080`
4. Copy the **Client ID** (the string under the app's name) and the **Client Secret**
5. Launch the app → **⚙️ Configuration** tab → enter Client ID, Client Secret, your Reddit username and password → **Save** → **Test Connection**

Your credentials are written to `data/reddit_config.json`, which is **git-ignored** and stays on your machine. A template is provided at [`data/reddit_config.example.json`](data/reddit_config.example.json).

> **Note:** The password grant used here requires **2FA to be disabled** on the account (a Reddit limitation for script apps). Accounts that sign in only via Google/Apple have no Reddit password and won't work.

---

## Typical Workflow

1. **⚙️ Configuration** — enter and test your credentials (once).
2. **📂 Posts** — type or paste rows into the grid: `subreddit`, `title`, `url`, and optional `flair`. (Or use **🔍 Search** to find posts and load them here.)
3. **🎨 Get Flairs** — click it on the Posts tab to fetch the current flairs for every subreddit in your grid. Then click any **Flair** cell to pick from a dropdown.
4. **🚀 Batch Submit** — set the delay, hit **Start**, and watch the live log.
5. **✅ Results** — review what succeeded/failed (with reasons); export to CSV if you like.
6. **📊 Karma Stats** — later, refresh scores for your posts.

---

## Tabs Reference

### ⚙️ Configuration
Enter your Reddit API credentials and test the connection. Saved to `data/reddit_config.json`.

### ⭐ Subreddits
Save frequently used subreddits (usage auto-increments after each successful post), import them from your post history or a text file, and generate a pre-filled template spreadsheet.

### 🔍 Search
Query Reddit using Lucene field operators (e.g. `title:python url:github.com`, `flair:"Discussion"`). Browse results with thumbnails, copy links, and load selected rows straight into the Posts grid.

### 📂 Posts
An editable, spreadsheet-style grid — no external file required:

| Column | Meaning |
|--------|---------|
| `subreddit` | Target subreddit (no `r/` prefix needed) |
| `title` | Post title |
| `url` | Link to submit |
| `flair` | *(optional)* flair name — pick from the dropdown after **Get Flairs** |

Editing niceties: `Ctrl+C` / `Ctrl+V` (Excel-compatible clipboard), paste-to-fill tiling, fill-handle drag (repeats values or continues a series like `1,2,3 → 4,5,6`), and `Delete` to clear. You can **Export to CSV** for a backup, but composing posts happens entirely in this grid — there's no import step.

### 🚀 Batch Submit
Submits every valid row one by one.

- **Delay between posts** — default **10 s** (raise it if you get rate-limited).
- **Automatic rate-limit handling** — on a Reddit `RATELIMIT` error, it waits the mandated time and retries once.
- **Detailed log** — timestamped per-post progress plus an end-of-run summary with permalinks and failure reasons. Failures are also written to the terminal/stdout log with full tracebacks.

> Reddit rate-limits link posts heavily, especially for newer or low-karma accounts (often ~10 minutes between link posts). If posts fail after the first, increase the delay.

### 📊 Karma Stats
Refresh score/comment counts for your N most recent posts, search your posts by subreddit, bulk-update karma for everything in the post log, and export to CSV. All posts you submit are logged to `data/reddit_posts_log.csv`.

### ✅ Results
A summary of the last batch: success/failure counts, success rate, per-post reasons, and one-click export.

---

## Flairs

Some subreddits **require** a flair before a post is accepted. This app handles that:

1. Put your subreddits in the Posts grid and click **🎨 Get Flairs**. It fetches each subreddit's link-flair templates and caches them in `data/subreddit_flairs.csv` (a small, viewable "database").
2. Click a **Flair** cell → choose from the dropdown of that subreddit's flairs (the field stays editable, so you can also type a custom value).
3. On submit, the app resolves your flair text to the flair's template ID and **attaches it at submission time**, satisfying flair-required subreddits.

Matching is case-insensitive: it tries an exact match first, then a substring match, and skips mod-only flairs you can't apply. If nothing matches, the available flairs are listed in the log so you can see exactly what the subreddit offers.

---

## CLI Tools

Reads credentials from `data/reddit_config.json` (set them up via the GUI first).

```bash
# List a subreddit's post-flair templates (id + text)
python cli/flair.py --subreddit python
python cli/flair.py --subreddit python --csv data/python_flairs.csv
```

`cli/flair.py` prints each link-flair template's `id`, `text`, colors, and whether it's mod-only — handy for discovering the exact flair text to use in the Posts grid. Use `--csv` to save the list to a file.

---

## Repository Layout

```
reddit_share/
├── main.py                  # Entry point (QApplication setup)
├── run_app.bat              # Windows launcher (run the app)
├── build.bat                # Windows launcher (build the .exe)
├── requirements.txt
│
├── app/                     # GUI application package
│   ├── dashboard.py         # Main window — assembles tabs, owns the Reddit connection
│   ├── workers.py           # Background threads (submit, karma, flair fetch)
│   ├── post_log.py          # Post-log CSV operations
│   ├── favorites.py         # Favourites JSON operations
│   ├── flair_store.py       # Flair database (CSV-backed cache)
│   ├── utils.py             # Shared CSV-export helper
│   ├── tabs/                # One QWidget per tab
│   │   ├── config_tab.py    # Credentials
│   │   ├── subreddits_tab.py# Favourites manager
│   │   ├── search_tab.py    # Reddit search & import
│   │   ├── import_tab.py    # Posts spreadsheet + Get Flairs
│   │   ├── submit_tab.py    # Batch submitter
│   │   ├── karma_tab.py     # Karma tracker
│   │   └── results_tab.py   # Submission summary
│   └── widgets/
│       └── spreadsheet.py   # SpreadsheetWidget (editable grid)
│
├── cli/
│   └── flair.py             # Flair template lister
│
├── scripts/
│   ├── build_exe.py         # Build framework (installs deps, builds the .exe)
│   └── make_icons.py        # Generates the app icon (PNG + ICO)
│
├── assets/                  # App icon (icon.png / icon.ico)
│
└── data/                    # Runtime data — git-ignored (except the template)
    ├── reddit_config.example.json   # ← committed template
    ├── reddit_config.json           # your credentials (ignored)
    ├── subreddit_favorites.json     # (ignored)
    ├── subreddit_flairs.csv         # flair DB (ignored)
    └── reddit_posts_log.csv         # post history (ignored)
```

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| `invalid_grant` on connect | Wrong username/password, or **2FA is enabled** (disable it), or the account uses Google/Apple sign-in (no Reddit password) |
| `401 Unauthorized` | Client ID or Secret is wrong; the Reddit app type must be **script** |
| Post fails on a subreddit that needs flair | Click **🎨 Get Flairs**, then pick the flair from the dropdown before submitting |
| Flair "not found" | The log lists the subreddit's actual flairs — copy the exact text; note some flairs are mod-only and can't be applied |
| Posts fail after the first | Increase the delay in **Batch Submit**; Reddit rate-limits link posts heavily |
| A row is skipped on submit | `subreddit`, `title`, and `url` must all be filled for a row to be submitted |

---

## Security & Privacy

- Credentials live only in `data/reddit_config.json` (plain text, **git-ignored**). Never commit it — use `reddit_config.example.json` as the shareable template.
- No telemetry, no cloud, no third-party servers. The app talks only to Reddit's API.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `praw` | Reddit API client |
| `PyQt5` | Desktop GUI |
| `requests` | HTTP (thumbnails, PRAW dependency) |

---

## License

Released under the MIT License — see [LICENSE](LICENSE). You're free to use, modify, and distribute it.
