import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lead_search


def _truncate(text, width):
    text = str(text or "")
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


def _print_table(rows, count):
    headers = ["#", "score", "name", "rating", "reviews", "website", "site score", "phone"]
    widths = [3, 5, 32, 6, 7, 7, 10, 16]

    divider = "+".join("-" * (width + 2) for width in widths)
    print(divider)
    print("|".join(" {} ".format(header.ljust(width)) for header, width in zip(headers, widths)))
    print(divider)

    for position, row in enumerate(rows[:count], start=1):
        has_website = "none" if not (row.get("website") or "").strip() else "yes"
        cells = [
            str(position),
            str(row.get("score", "")),
            _truncate(row.get("name"), widths[2]),
            str(row.get("rating") or "-"),
            str(row.get("review_count") or "-"),
            has_website,
            str(row.get("website_score") or "-"),
            _truncate(row.get("phone") or "-", widths[7]),
        ]
        print("|".join(" {} ".format(cell.ljust(width)) for cell, width in zip(cells, widths)))

    print(divider)


def _report_progress(message):
    print("  {}".format(message))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Finds local businesses and ranks them as website candidates.")
    parser.add_argument("query", help='For example: "pizzeria Novi Sad"')
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of results")
    parser.add_argument("--source", choices=["auto", "google", "osm"], default="auto")
    parser.add_argument("--no-audit", action="store_true", help="Skip checking the existing websites")
    arguments = parser.parse_args()

    print('\nSearch: "{}"'.format(arguments.query))

    try:
        summary = lead_search.usage_summary()
        if arguments.source != "osm" and lead_search.google_key():
            print("Source: Google Places API (New)")
            print("Calls used this month: {} of {}\n".format(summary["used"], summary["limit"]))
        else:
            print("Source: OpenStreetMap (free, no key)")
            print("Warning: OpenStreetMap has no ratings and no review counts.")
            print("Only two of the five scoring rules apply, so ranking is coarse.\n")

        result = lead_search.run_search(
            arguments.query,
            limit=arguments.limit,
            source=arguments.source,
            on_event=_report_progress,
            audit=not arguments.no_audit,
        )
    except lead_search.SearchError as error:
        print("\nERROR: {}\n".format(error))
        raise SystemExit(1)

    if not result["leads"]:
        print("No results. Try a different term, or check how the place is named on the map.\n")
        return

    if result["source"] == "openstreetmap":
        print("Recognised: '{}' in '{}' (matched by {})".format(result["term"], result["place"], result["method"]))
        print("Area: {}\n".format(result["area"]))

    print("Found: {} businesses, {} of them without a website.".format(
        len(result["leads"]), result["without_website"]
    ))
    if result.get("audited"):
        print("Checked {} existing websites, {} of them scored poorly enough to be worth pitching.".format(
            result["audited"], result["poor_websites"]
        ))
    if result.get("closed_dropped"):
        print("Dropped as closed: {}".format(result["closed_dropped"]))
    if result.get("previous"):
        print("Merged with: {} (your statuses were kept)".format(result["previous"]))
    if result.get("stopped_at_limit"):
        print("Search stopped early because the monthly call limit was reached.")
    print("Saved to: {}\n".format(result["path"]))

    _print_table(result["rows"], 15)

    if result.get("calls"):
        summary = lead_search.usage_summary()
        print("\nCalls used by this search: {}".format(result["calls"]))
        print("Total this month: {} of {}".format(summary["used"], summary["limit"]))

    print()


if __name__ == "__main__":
    main()
