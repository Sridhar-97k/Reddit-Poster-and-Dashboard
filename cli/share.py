#!/usr/bin/env python3
"""
Simple Reddit bulk poster with flair support (primary + crossposts).

Excel (sheet 'posts'):
  - title (str)       - link (url)        - subreddit (str)
  - crosspost (csv list of subreddits)

Usage:
  python cli/share.py --excel your_posts.xlsx
  python cli/share.py --excel your_posts.xlsx --dry-run
"""

import argparse, os, sys, time, json
from typing import List, Optional, Dict
import pandas as pd
import praw
from praw.exceptions import APIException, PRAWException, ClientException

# ====================== CONFIG: set your flairs here ======================

# Flair for the **primary submission** (keyed by primary subreddit)
PRIMARY_FLAIRS: Dict[str, Dict[str, str]] = {
    # "mysub": {"flair_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"},
}

# Flair for **crossposts** (keyed by target subreddit)
CROSSPOST_FLAIRS: Dict[str, Dict[str, str]] = {
    # "targetsub": {"flair_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"},
}

SLEEP_SECS = 12.0
SHEET_NAME = "posts"

# ====================== AUTH ======================

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'reddit_config.json')


def load_reddit() -> praw.Reddit:
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: {CONFIG_FILE} not found.", file=sys.stderr)
        print("Run the GUI app first and save your credentials in the Configuration tab.", file=sys.stderr)
        sys.exit(1)

    with open(CONFIG_FILE) as f:
        cfg = json.load(f)

    missing = [k for k in ("client_id", "client_secret", "username", "password") if not cfg.get(k)]
    if missing:
        print(f"Error: Missing fields in config: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    return praw.Reddit(
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        username=cfg["username"],
        password=cfg["password"],
        user_agent=f"RedditBulkPoster/1.0 by {cfg['username']}",
        check_for_async=False,
    )

# ====================== helpers ======================

def split_list(s: str) -> List[str]:
    if not s or str(s).strip() == "":
        return []
    return [p.strip() for p in str(s).split(",") if p.strip()]


def _get_flair_cfg(mapping, sub):
    return mapping.get(sub) or mapping.get(sub.lower()) or mapping.get(sub.capitalize())


def set_link_flair_if_configured(reddit, subreddit_name, submission, mapping):
    cfg = _get_flair_cfg(mapping, subreddit_name)
    if not cfg:
        return None
    flair_id   = (cfg.get("flair_id")   or "").strip()
    flair_text = (cfg.get("flair_text") or "").strip()
    try:
        if flair_id:
            submission.flair.select(flair_id)
            return "flair_id set"
        if flair_text:
            sub = reddit.subreddit(subreddit_name)
            for tmpl in sub.flair.link_templates:
                if (tmpl.get("text") or "").strip().lower() == flair_text.lower():
                    submission.flair.select(tmpl["id"])
                    return "flair_text matched"
            return f"flair_text '{flair_text}' not found"
    except Exception as e:
        return f"flair error: {e}"
    return None

# ====================== main ======================

def main():
    ap = argparse.ArgumentParser(description="Submit link, then crosspost — with flair support.")
    ap.add_argument("--excel", required=True, help="Path to .xlsx with sheet 'posts'")
    ap.add_argument("--dry-run", action="store_true", help="Validate only; no posting")
    args = ap.parse_args()

    try:
        df = pd.read_excel(args.excel, sheet_name=SHEET_NAME, dtype=str)
    except Exception as e:
        print(f"Failed to read Excel: {e}", file=sys.stderr)
        sys.exit(2)

    cols = {c.lower(): c for c in df.columns}
    need = ["title", "link", "subreddit", "crosspost"]
    if not all(n in cols for n in need):
        print("Excel must have columns: title, link, subreddit, crosspost", file=sys.stderr)
        sys.exit(2)

    title_col = cols["title"]; link_col = cols["link"]
    sub_col   = cols["subreddit"]; x_col = cols["crosspost"]
    reddit = load_reddit()

    print("Starting…")
    for i, row in df.iterrows():
        title = (row.get(title_col) or "").strip()
        link  = (row.get(link_col)  or "").strip()
        sub   = (row.get(sub_col)   or "").strip()
        xsubs = split_list(row.get(x_col) or "")

        if not title or not link or not sub:
            print(f"[Row {i}] Missing required field(s). Skipping.")
            continue

        if args.dry_run:
            print(f"[Row {i}] DRY-RUN submit to r/{sub} :: {title} -> {link}")
            for xs in xsubs:
                print(f"[Row {i}] DRY-RUN crosspost to r/{xs}")
            continue

        try:
            submission = reddit.subreddit(sub).submit(title=title, url=link, send_replies=True)
            msg = f"[Row {i}] Posted to r/{sub} → https://www.reddit.com{submission.permalink}"
            status = set_link_flair_if_configured(reddit, sub, submission, PRIMARY_FLAIRS)
            if status:
                msg += f" [{status}]"
            print(msg)
        except (APIException, PRAWException, ClientException) as e:
            print(f"[Row {i}] Post failed ({sub}): {e}")
            continue
        except Exception as e:
            print(f"[Row {i}] Post failed ({sub}): {e}")
            continue

        time.sleep(SLEEP_SECS)

        for xs in xsubs:
            try:
                xpost = submission.crosspost(subreddit=xs, title=title, send_replies=True)
                xmsg = f"[Row {i}] Crossposted to r/{xs} → https://www.reddit.com{xpost.permalink}"
                xstatus = set_link_flair_if_configured(reddit, xs, xpost, CROSSPOST_FLAIRS)
                if xstatus:
                    xmsg += f" [{xstatus}]"
                print(xmsg)
            except Exception as e:
                print(f"[Row {i}] Crosspost failed ({xs}): {e}")
            time.sleep(SLEEP_SECS)

    print("Done.")


if __name__ == "__main__":
    main()
