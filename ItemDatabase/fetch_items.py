"""Fetch the full AION 2 item list from shugo.gg's public API and cache it locally.

This is a standalone test script — not wired into cont_ToDo_app. Run it directly:
    python fetch_items.py
"""

import json
import urllib.request
from pathlib import Path

API_URL = "https://shugo.gg/api/items/all"
OUTPUT_PATH = Path(__file__).parent / "data" / "items_all.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://shugo.gg/",
    "Origin": "https://shugo.gg",
    "Accept": "application/json",
}


def fetch_items() -> dict:
    request = urllib.request.Request(API_URL, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main():
    print(f"Fetching {API_URL} ...")
    data = fetch_items()
    items = data.get("items", [])
    print(f"Got {len(items)} items (totalItems={data.get('totalItems')}).")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
