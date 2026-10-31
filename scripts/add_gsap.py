import argparse
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lead_search

VENDOR_FOLDER = "vendor"


class GsapError(Exception):
    pass


def add(folder, settings):
    folder = Path(folder).expanduser()
    if not (folder / "brief.md").is_file():
        raise GsapError("{} holds no brief.md, so it is not a business folder.".format(folder))

    options = settings["gsap"]
    target = folder / "site" / VENDOR_FOLDER
    target.mkdir(parents=True, exist_ok=True)

    added = []
    for name in options["files"]:
        url = options["url"].format(version=options["version"], file=name)
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as error:
            raise GsapError("{} could not be downloaded: {}".format(url, error))
        if options["version"].encode() not in response.content[:400]:
            raise GsapError("{} did not return GSAP {}.".format(url, options["version"]))
        (target / name).write_bytes(response.content)
        added.append("{}/{}".format(VENDOR_FOLDER, name))
    return added


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Puts local copies of GSAP and ScrollTrigger into site/vendor/ of a business folder."
    )
    parser.add_argument("folder", help="The business folder that holds brief.md")
    arguments = parser.parse_args()

    try:
        added = add(arguments.folder, lead_search.load_settings())
    except GsapError as error:
        print("\nERROR: {}\n".format(error))
        raise SystemExit(1)

    print("\nAdded to site/: {}".format(", ".join(added)))
    print("Load them from index.html, in this order, before script.js:\n")
    for path in added:
        print('  <script src="{}" defer></script>'.format(path))
    print()


if __name__ == "__main__":
    main()
