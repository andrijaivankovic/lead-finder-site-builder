import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import image_tools
import lead_search

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
MANIFEST_NAME = "assets.json"


class AssetError(Exception):
    pass


def _images_in(folder):
    return sorted(
        path
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def scan(folder, settings):
    folder = Path(folder)
    if not folder.is_dir():
        raise AssetError("{} is not a folder.".format(folder))

    images = _images_in(folder)
    if not images:
        raise AssetError("No images found in {}.".format(folder))

    entries = []
    for path in images:
        try:
            width, height = image_tools.dimensions(path)
            palette = image_tools.dominant_colours(path, settings["asset_sorting"]["logo_colors"])
        except OSError:
            continue
        entries.append(
            {
                "file": str(path.relative_to(folder)).replace("\\", "/"),
                "width": width,
                "height": height,
                "palette": palette,
                "category": "",
                "description": "",
            }
        )

    manifest = {
        "folder": str(folder),
        "categories": settings["asset_sorting"]["categories"],
        "brand_colors": [],
        "images": entries,
    }
    _write_manifest(folder, manifest)
    return manifest


def _write_manifest(folder, manifest):
    (Path(folder) / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def apply(folder, settings, on_event=None):
    folder = Path(folder)
    manifest_path = folder / MANIFEST_NAME
    if not manifest_path.exists():
        raise AssetError("{} does not exist. Run the scan first.".format(manifest_path))

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    allowed = set(settings["asset_sorting"]["categories"])
    unlabelled = [entry for entry in manifest["images"] if not entry["category"]]
    if unlabelled:
        raise AssetError(
            "{} of {} images still have an empty category. Fill them in {} first.".format(
                len(unlabelled), len(manifest["images"]), MANIFEST_NAME
            )
        )

    moved = 0
    for entry in manifest["images"]:
        category = entry["category"].strip().lower()
        if category not in allowed:
            raise AssetError(
                "'{}' is not one of the allowed categories: {}".format(category, ", ".join(sorted(allowed)))
            )

        source = folder / entry["file"]
        if not source.exists():
            continue

        target = folder / category / source.name
        if source.resolve() == target.resolve():
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        entry["file"] = "{}/{}".format(category, source.name)
        moved += 1
        if on_event:
            on_event("{} -> {}".format(source.name, category))

        if category == "logo" and not manifest["brand_colors"]:
            manifest["brand_colors"] = entry["palette"][: settings["asset_sorting"]["logo_colors"]]

    _write_manifest(folder, manifest)
    return manifest, moved


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Builds an image manifest for a folder, then files the images into category folders."
    )
    parser.add_argument("folder", help="Folder holding the unsorted images")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Move the images according to the categories already written in assets.json",
    )
    arguments = parser.parse_args()

    try:
        settings = lead_search.load_settings()
        if arguments.apply:
            manifest, moved = apply(arguments.folder, settings, on_event=lambda line: print("  " + line))
            print("\nMoved {} images.".format(moved))
            if manifest["brand_colors"]:
                print("Brand colours from the logo: {}".format(" ".join(manifest["brand_colors"])))
            print()
            return

        manifest = scan(arguments.folder, settings)
    except AssetError as error:
        print("\nERROR: {}\n".format(error))
        raise SystemExit(1)

    print("\nFound {} images in {}\n".format(len(manifest["images"]), manifest["folder"]))
    for entry in manifest["images"]:
        print("  {:<34} {:>5}x{:<5} {}".format(
            entry["file"], entry["width"], entry["height"], " ".join(entry["palette"][:3])
        ))

    print("\nWritten to {}".format(Path(manifest["folder"]) / MANIFEST_NAME))
    print("Fill in category and description for each image, then run the same command with --apply.")
    print("Allowed categories: {}\n".format(", ".join(manifest["categories"])))


if __name__ == "__main__":
    main()
