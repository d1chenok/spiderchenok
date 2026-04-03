#!/usr/bin/env python3
import asyncio
import json
import os
from collections import Counter
from twikit import Client

TARGET_USERNAME = "d1chenok1"
MIN_MUTUAL_FOLLOWERS = 7
MIN_FOLLOWERS = 500
MAX_FOLLOWERS = 2000
MAX_FOLLOWING_RATIO = 0.25
DELAY = 3
CHECKPOINT_FILE = "checkpoint.json"
RESULTS_FILE = "results.json"
COOKIES_FILE = "cookies.json"

async def fetch_all_pages(initial_result, label="", delay=DELAY):
    items = list(initial_result)
    current = initial_result
    page = 1
    if label:
        print(f"    page {page}: {len(items)} {label}")
    while getattr(current, "next_cursor", None):
        await asyncio.sleep(delay)
        try:
            current = await current.next()
            batch = list(current)
            if not batch:
                break
            items.extend(batch)
            page += 1
            if label:
                print(f"    page {page}: +{len(batch)} {label} (total {len(items)})")
        except Exception as exc:
            print(f"    pagination stopped: {exc}")
            break
    return items

def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            data = json.load(f)
        return set(data.get("processed", [])), Counter(data.get("counter", {})), data.get("map", {})
    return set(), Counter(), {}

def save_checkpoint(processed, counter, acc_map):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump({"processed": list(processed), "counter": dict(counter), "map": acc_map}, f, indent=2, ensure_ascii=False)

async def main():
    print("=" * 40)
    print(f"spiderchenok | target: @{TARGET_USERNAME}")
    print(f"mutual >= {MIN_MUTUAL_FOLLOWERS} | followers {MIN_FOLLOWERS}-{MAX_FOLLOWERS} | ratio <= {MAX_FOLLOWING_RATIO}")
    print("=" * 40)
    client = Client("en-US")
    if os.path.exists(COOKIES_FILE):
        print("\nLoading saved session...")
        client.load_cookies(COOKIES_FILE)
    else:
        print("\nFirst run - please log in.")
        username = input("  Username (without @): ").strip()
        email = input("  Email: ").strip()
        password = input("  Password: ").strip()
        await client.login(auth_info_1=username, auth_info_2=email, password=password)
        client.save_cookies(COOKIES_FILE)
        print("  Session saved to cookies.json")
    print(f"\nFetching @{TARGET_USERNAME}...")
    target = await client.get_user_by_screen_name(TARGET_USERNAME)
    print(f"  @{target.screen_name} | {target.followers_count} followers")
    print(f"\nFetching followers...")
    raw = await target.get_followers(count=200)
    all_followers = await fetch_all_pages(raw, label="followers")
    print(f"Total followers: {len(all_followers)}")
    processed, counter, acc_map = load_checkpoint()
    if processed:
        print(f"\nResuming: {len(processed)} already done.")
    print(f"\nProcessing followers...")
    for i, follower in enumerate(all_followers):
        fid = str(follower.id)
        if fid in processed:
            print(f"[{i+1}/{len(all_followers)}] @{follower.screen_name} - cached")
            continue
        print(f"[{i+1}/{len(all_followers)}] @{follower.screen_name} ({follower.followers_count} flw)...")
        await asyncio.sleep(DELAY)
        try:
            raw_following = await follower.get_following(count=200)
            following_list = await fetch_all_pages(raw_following, label="following")
            for acc in following_list:
                aid = str(acc.id)
                counter[aid] += 1
                if aid not in acc_map:
                    acc_map[aid] = {"username": acc.screen_name, "name": acc.name, "followers": acc.followers_count, "following": acc.following_count}
            processed.add(fid)
        except Exception as exc:
            print(f"  error: {exc} - skipping")
            continue
        if len(processed) % 10 == 0:
            save_checkpoint(processed, counter, acc_map)
            print(f"  [checkpoint saved - {len(processed)} done]")
    save_checkpoint(processed, counter, acc_map)
    print(f"\nBuilding results...")
    results = []
    for aid, mutual in counter.items():
        if mutual < MIN_MUTUAL_FOLLOWERS or aid not in acc_map:
            continue
        acc = acc_map[aid]
        if acc["username"].lower() == TARGET_USERNAME.lower():
            continue
        flw = acc["followers"]
        ing = acc["following"]
        if not (MIN_FOLLOWERS <= flw <= MAX_FOLLOWERS):
            continue
        ratio = (ing / flw) if flw > 0 else 0.0
        if ratio > MAX_FOLLOWING_RATIO:
            continue
        results.append({"username": acc["username"], "name": acc["name"], "followers": flw, "following": ing, "ratio": round(ratio, 3), "mutual_count": mutual})
    results.sort(key=lambda x: x["mutual_count"], reverse=True)
    print(f"\n{'='*40}")
    print(f"Found {len(results)} matching accounts")
    print(f"{'='*40}\n")
    for r in results:
        print(f"@{r['username']} ({r['name']}) | {r['followers']} flw | ratio {r['ratio']} | {r['mutual_count']} mutual")
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {RESULTS_FILE}")
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)

if __name__ == "__main__":
    asyncio.run(main())
