import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))

import image_tools
import lead_search

PEXELS_SEARCH = "https://api.pexels.com/v1/search"
ROOT = lead_search.ROOT


class StockPhotoError(Exception):
    pass


def _slug(text):
    normalised = unicodedata.normalize("NFKD", text).replace("đ", "dj").replace("Đ", "Dj")
    normalised = "".join(char for char in normalised if not unicodedata.combining(char))
    return re.sub(r"[^a-zA-Z0-9]+", "-", normalised).strip("-").lower() or "business"


def _api_key():
    load_dotenv(ROOT / ".env")
    key = (os.getenv("PEXELS_API_KEY") or "").strip()
    if not key:
        raise StockPhotoError("PEXELS_API_KEY is empty in .env. See SETUP.md, section 1.")
    return key


def _search(query, key, options):
    try:
        response = requests.get(
            PEXELS_SEARCH,
            headers={"Authorization": key},
            params={"query": query, "per_page": 30, "orientation": "landscape", "size": "large"},
            timeout=30,
        )
        if response.status_code == 401:
            raise StockPhotoError("Pexels rejected the key. Check PEXELS_API_KEY in .env.")
        if response.status_code == 429:
            raise StockPhotoError("Pexels rate limit reached (200 calls per hour). Wait and retry.")
        response.raise_for_status()
    except requests.RequestException as error:
        raise StockPhotoError("Pexels did not respond: {}".format(error))

    return response.json().get("photos", [])


def _acceptable(photo, options):
    if photo.get("width", 0) < options["min_width"]:
        return False
    if not image_tools.is_landscape(photo.get("width", 0), photo.get("height", 1)):
        return False
    description = (photo.get("alt") or "").lower()
    return not any(word in description for word in options["skip_alt_keywords"])


def _download(photo, destination):
    url = photo["src"].get("large2x") or photo["src"].get("large") or photo["src"]["original"]
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    destination.write_bytes(response.content)
    return destination


def collect(plan, out_dir, settings, on_event=None):
    options = settings["stock_photos"]
    key = _api_key()
    out_dir = Path(out_dir)

    collected = []
    seen_ids = set()

    for purpose, queries in plan["queries"].items():
        folder = out_dir / purpose
        folder.mkdir(parents=True, exist_ok=True)
        taken_for_purpose = 0

        for query in queries:
            if taken_for_purpose >= options["per_purpose"] or len(collected) >= options["max_total"]:
                break
            if on_event:
                on_event('searching "{}" for {}'.format(query, purpose))

            for photo in _search(query, key, options):
                if taken_for_purpose >= options["per_purpose"] or len(collected) >= options["max_total"]:
                    break
                if photo["id"] in seen_ids or not _acceptable(photo, options):
                    continue

                target = folder / "{}_{}.jpg".format(purpose, photo["id"])
                try:
                    _download(photo, target)
                except requests.RequestException:
                    continue

                width, height = image_tools.dimensions(target)
                seen_ids.add(photo["id"])
                taken_for_purpose += 1
                collected.append(
                    {
                        "file": str(target.relative_to(out_dir)).replace("\\", "/"),
                        "purpose": purpose,
                        "query": query,
                        "width": width,
                        "height": height,
                        "description": photo.get("alt") or "",
                        "pexels_url": photo["url"],
                        "photographer": photo["photographer"],
                        "photographer_url": photo["photographer_url"],
                        "licence": "Pexels licence, free for commercial use, attribution appreciated",
                    }
                )

    sources = {
        "business": plan.get("business", ""),
        "source": "Pexels",
        "photos": collected,
    }
    (out_dir / "sources.json").write_text(
        json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return collected


def plan_for_category(category, settings, business="", note=""):
    plans = settings["stock_photos"]["plans"]
    key = (category or "").strip().lower()
    queries = plans.get(key)
    matched = bool(queries)

    if not matched:
        label = key or "local business"
        queries = {
            purpose: [text.format(category=label) for text in terms]
            for purpose, terms in plans["default"].items()
        }
    else:
        queries = {purpose: list(terms) for purpose, terms in queries.items()}

    note = (note or "").strip()
    if note:
        label = key or "local business"
        for purpose in ("hero", "interior"):
            if purpose in queries:
                queries[purpose].insert(0, "{} {}".format(note, label))

    return {"business": business, "category": category, "matched": matched, "queries": queries}


def _plan_from_arguments(arguments, settings):
    if arguments.plan:
        path = Path(arguments.plan)
        if not path.exists():
            raise StockPhotoError("Plan file {} does not exist.".format(path))
        return json.loads(path.read_text(encoding="utf-8"))

    if arguments.category:
        return plan_for_category(
            arguments.category, settings, arguments.business or "", arguments.note or ""
        )

    if not arguments.query:
        raise StockPhotoError("Give --category, or --plan, or at least one --query.")

    return {"business": arguments.business or "", "queries": {arguments.purpose: arguments.query}}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Downloads free Pexels photographs for a business, grouped by where they go on the site."
    )
    parser.add_argument("--plan", help="JSON file holding the business name and one query list per purpose")
    parser.add_argument("--category", help="Trade of the business, which picks a ready query plan from config.yaml")
    parser.add_argument("--note", help="Optional words about how the place looks, to sharpen the search")
    parser.add_argument("--query", action="append", help="A single search term, repeatable")
    parser.add_argument("--purpose", default="gallery", help="Where the --query photos belong on the site")
    parser.add_argument("--business", help="Business name, used for the output folder")
    parser.add_argument("--out", help="Output folder, defaults to assets/stock/<business>")
    arguments = parser.parse_args()

    try:
        settings = lead_search.load_settings()
        plan = _plan_from_arguments(arguments, settings)
        business = plan.get("business") or "stock"
        out_dir = Path(arguments.out) if arguments.out else ROOT / "assets" / "stock" / _slug(business)

        print("\nBusiness: {}".format(business or "not given"))
        if plan.get("category"):
            fit = "ready plan" if plan.get("matched") else "generic plan, no entry in config.yaml"
            print("Trade: {} ({})".format(plan["category"], fit))
        print("Folder: {}\n".format(out_dir))

        collected = collect(plan, out_dir, settings, on_event=lambda message: print("  " + message))
    except StockPhotoError as error:
        print("\nERROR: {}\n".format(error))
        raise SystemExit(1)

    if not collected:
        print("\nNothing matched the filters. Try broader search terms.\n")
        return

    print("\nDownloaded {} photographs:\n".format(len(collected)))
    for photo in collected:
        print("  {:<28} {:>5}x{:<5} {}".format(
            photo["file"], photo["width"], photo["height"], photo["photographer"]
        ))
    print("\nCredits written to {}\n".format(out_dir / "sources.json"))


if __name__ == "__main__":
    main()
