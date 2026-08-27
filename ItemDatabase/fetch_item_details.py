"""Bulk-fetch full per-item details (substats, required level, etc.) from
shugo.gg's batch-details API and cache them locally under data/details/ --
the same files ItemDetailCache reads from disk at runtime.

Goal (User-Wunsch, 2026-08-25): make the shipped app fully independent of
shugo.gg at runtime. ItemDetailCache already caches each item's detail to
disk the first time a real user's app fetches it live -- but that only
covers items someone happened to click on. This script instead pre-warms
the ENTIRE catalog ahead of time, as part of the periodic (User: "maximal
monatlich") data-refresh routine alongside fetch_items.py/fetch_skills.py/
etc. -- run this by hand before cutting a release, commit the resulting
data/details/*.json files, and no end user's running app ever needs to
reach shugo.gg's details endpoint at all.

Resumable: skips any item id that already has a cached data/details/{id}.json
file, so re-running only fetches what's actually missing (new items since
last run, or ones that failed before).

Standalone test script — not wired into cont_ToDo_app. Run it directly:
    python fetch_item_details.py
"""

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://shugo.gg/api/items/batch-details"
ITEMS_PATH = Path(__file__).parent / "data" / "items_all.json"
DETAILS_DIR = Path(__file__).parent / "data" / "details"

HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://shugo.gg/",
    "Origin": "https://shugo.gg",
    "Accept": "application/json",
}

# Confirmed via a live probe (see ItemDetailCache._MAX_BATCH_SIZE in app.py):
# the endpoint hard-rejects anything past this with HTTP 400.
BATCH_SIZE = 50

# Considerate pacing -- this is a one-off maintenance script run by hand,
# not something that needs to race to finish; a short pause between
# requests keeps this from hammering a third-party service.
DELAY_BETWEEN_BATCHES_SECONDS = 1.0


def fetch_batch(item_ids: list[int]) -> list[dict]:
    body = json.dumps({"itemIds": item_ids}).encode("utf-8")
    request = urllib.request.Request(API_URL, data=body, headers=HEADERS, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    return payload.get("items") or []


def main():
    data = json.loads(ITEMS_PATH.read_text(encoding="utf-8"))
    items = data.get("items", data) if isinstance(data, dict) else data
    all_ids = [it["id"] for it in items if it.get("id")]
    print(f"Catalog has {len(all_ids)} items total.")

    DETAILS_DIR.mkdir(parents=True, exist_ok=True)
    missing_ids = [i for i in all_ids if not (DETAILS_DIR / f"{i}.json").exists()]
    print(f"{len(all_ids) - len(missing_ids)} already cached, {len(missing_ids)} to fetch.")

    if not missing_ids:
        print("Nothing to do -- every item already has a cached detail file.")
        return

    written = 0
    failed_batches = 0
    total_batches = (len(missing_ids) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_num, start in enumerate(range(0, len(missing_ids), BATCH_SIZE), 1):
        chunk = missing_ids[start:start + BATCH_SIZE]
        try:
            details = fetch_batch(chunk)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            print(f"  batch {batch_num}/{total_batches}: FAILED ({e}) -- will retry on next run")
            failed_batches += 1
            time.sleep(DELAY_BETWEEN_BATCHES_SECONDS)
            continue

        for detail in details:
            item_id = detail.get("id")
            if not item_id:
                continue
            (DETAILS_DIR / f"{item_id}.json").write_text(
                json.dumps(detail, ensure_ascii=False), encoding="utf-8"
            )
            written += 1

        print(f"  batch {batch_num}/{total_batches}: {len(details)} details written")
        time.sleep(DELAY_BETWEEN_BATCHES_SECONDS)

    print(f"\nDone. {written} new detail files written, {failed_batches} batches failed (re-run to retry).")


if __name__ == "__main__":
    main()
