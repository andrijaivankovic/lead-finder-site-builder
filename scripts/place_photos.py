import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))

import image_tools
import lead_search
from find_stock_photos import _slug

PLACE_DETAILS = "https://places.googleapis.com/v1/places/{}"
PHOTO_MEDIA = "https://places.googleapis.com/v1/{}/media"
ROOT = lead_search.ROOT

NOTICE = (
    "REFERENCE ONLY. These photographs belong to Google users and business owners. "
    "Use them to understand how the place looks and to guide image choices. "
    "Never put them on a website you build."
)


class PlacePhotoError(Exception):
    pass


def _api_key():
    load_dotenv(ROOT / ".env")
    key = (os.getenv("GOOGLE_MAPS_API_KEY") or "").strip()
    if not key:
        raise PlacePhotoError("GOOGLE_MAPS_API_KEY is empty in .env. See SETUP.md, section 2.")
    return key


def _photo_names(place_id, key, limit):
    try:
        response = requests.get(
            PLACE_DETAILS.format(place_id),
            headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": "id,displayName,photos"},
            timeout=30,
        )
        if response.status_code == 403:
            raise PlacePhotoError("Google rejected the key (403). Check that Places API (New) is enabled.")
        if response.status_code == 404:
            raise PlacePhotoError("Google does not know place_id {}.".format(place_id))
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as error:
        raise PlacePhotoError("Google Places API did not respond: {}".format(error))

    name = (payload.get("displayName") or {}).get("text", "")
    return name, [photo["name"] for photo in payload.get("photos", [])[:limit]]


def _download_photo(photo_name, key, max_width, destination):
    response = requests.get(
        PHOTO_MEDIA.format(photo_name),
        headers={"X-Goog-Api-Key": key},
        params={"maxWidthPx": max_width, "skipHttpRedirect": "false"},
        timeout=60,
    )
    response.raise_for_status()
    destination.write_bytes(response.content)
    return destination


def collect(place_id, settings, out_dir=None, on_event=None):
    options = settings["reference_photos"]
    key = _api_key()

    business, photo_names = _photo_names(place_id, key, options["max_per_business"])
    if not photo_names:
        raise PlacePhotoError("Google has no photographs for this place.")

    out_dir = Path(out_dir) if out_dir else ROOT / "assets" / "reference" / _slug(business or place_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    references = []
    for position, photo_name in enumerate(photo_names, start=1):
        target = out_dir / "reference_{}.jpg".format(position)
        if on_event:
            on_event("downloading reference {} of {}".format(position, len(photo_names)))
        try:
            _download_photo(photo_name, key, options["max_width"], target)
        except requests.RequestException:
            continue

        width, height = image_tools.dimensions(target)
        references.append(
            {
                "file": target.name,
                "width": width,
                "height": height,
                "palette": image_tools.dominant_colours(target, options["palette_colors"]),
                "description": "",
            }
        )

    manifest = {
        "business": business,
        "place_id": place_id,
        "usage": NOTICE,
        "atmosphere": "",
        "photos": references,
    }
    (out_dir / "reference.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "READ_ME_FIRST.txt").write_text(NOTICE + "\n", encoding="utf-8")

    return manifest, out_dir


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Downloads Google photographs of one business as a visual reference, never for the site itself."
    )
    parser.add_argument("place_id", help="The place_id column from the leads CSV")
    parser.add_argument("--out", help="Output folder, defaults to assets/reference/<business>")
    arguments = parser.parse_args()

    try:
        settings = lead_search.load_settings()
        manifest, out_dir = collect(
            arguments.place_id, settings, arguments.out, on_event=lambda message: print("  " + message)
        )
    except PlacePhotoError as error:
        print("\nERROR: {}\n".format(error))
        raise SystemExit(1)

    print("\n{}".format(manifest["business"] or arguments.place_id))
    print("Folder: {}\n".format(out_dir))

    for photo in manifest["photos"]:
        print("  {:<16} {:>5}x{:<5} {}".format(
            photo["file"], photo["width"], photo["height"], " ".join(photo["palette"])
        ))

    print("\n{}\n".format(NOTICE))


if __name__ == "__main__":
    main()
