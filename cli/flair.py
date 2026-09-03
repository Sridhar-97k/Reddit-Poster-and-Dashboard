#!/usr/bin/env python3
"""
List link flair (post flair) templates for a subreddit.

Usage:
  python cli/flair.py --subreddit python
  python cli/flair.py --subreddit python --csv data/python_flairs.csv
"""

import argparse
import csv
import json
import os
import sys

import praw
from praw.exceptions import RedditAPIException, PRAWException, ClientException

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'reddit_config.json')


def load_reddit() -> praw.Reddit:
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: {CONFIG_FILE} not found.", file=sys.stderr)
        print("Run the GUI app and save credentials in the Configuration tab.", file=sys.stderr)
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
        user_agent=f"FlairLister/1.0 by {cfg['username']}",
        check_for_async=False,
    )


def main():
    ap = argparse.ArgumentParser(description="Print link flair IDs for a subreddit.")
    ap.add_argument("--subreddit", required=True, help="Subreddit name (without r/)")
    ap.add_argument("--csv", dest="csv_path", default=None, help="Optional path to save CSV")
    args = ap.parse_args()

    reddit = load_reddit()
    sub_name = args.subreddit.strip().lstrip("r/")

    try:
        templates = list(reddit.subreddit(sub_name).flair.link_templates)
    except (RedditAPIException, PRAWException, ClientException) as e:
        print(f"Failed to fetch flairs for r/{sub_name}: {e}", file=sys.stderr)
        sys.exit(1)

    if not templates:
        print(f"No link flair templates found for r/{sub_name}.")
        return

    header = ["id", "text", "text_color", "background_color", "mod_only", "allow_user_edits"]
    print(f"Link flairs for r/{sub_name}:")
    print("-" * 80)
    print("{:<38}  {:<30}  {:<10}  {:<16}  {:<8}  {}".format(*header))
    print("-" * 80)

    rows = []
    for t in templates:
        row = {k: t.get(k, "") for k in header}
        rows.append(row)
        print("{:<38}  {:<30}  {:<10}  {:<16}  {:<8}  {}".format(
            row["id"], str(row["text"])[:30], row["text_color"],
            row["background_color"], str(row["mod_only"]), str(row["allow_user_edits"])
        ))

    if args.csv_path:
        try:
            with open(args.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=header)
                writer.writeheader()
                writer.writerows(rows)
            print(f"\nSaved CSV → {args.csv_path}")
        except Exception as e:
            print(f"Could not write CSV: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
