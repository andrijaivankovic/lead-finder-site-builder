import csv
import re
import unicodedata
from pathlib import Path

COLUMNS = [
    "score",
    "name",
    "address",
    "rating",
    "review_count",
    "website",
    "website_score",
    "website_problems",
    "phone",
    "google_maps_link",
    "map_pin",
    "contact_search",
    "place_id",
    "status",
]

STATUSES = ["", "contacted", "declined", "accepted"]


class FileLocked(Exception):
    pass


def to_slug(text):
    normalized = unicodedata.normalize("NFKD", text)
    normalized = normalized.replace("đ", "dj").replace("Đ", "Dj")
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug or "search"


def data_dir(root):
    return Path(root) / "data"


def output_path(root, query):
    return data_dir(root) / "leads_{}.csv".format(to_slug(query))


def find_previous(root, query):
    folder = data_dir(root)
    if not folder.exists():
        return None
    current = output_path(root, query)
    if current.exists():
        return current
    dated = sorted(folder.glob("leads_{}_*.csv".format(to_slug(query))))
    return dated[-1] if dated else None


def list_files(root):
    folder = data_dir(root)
    if not folder.exists():
        return []
    files = sorted(folder.glob("leads_*.csv"), key=lambda path: path.stat().st_mtime, reverse=True)
    return [path.name for path in files]


def load(path):
    if not path or not Path(path).exists():
        return {}
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return {row["place_id"]: row for row in csv.DictReader(handle) if row.get("place_id")}


def load_rows(path):
    if not path or not Path(path).exists():
        return []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return [row for row in csv.DictReader(handle) if row.get("place_id")]


def _row_ranking_key(row):
    website_score = str(row.get("website_score", "")).strip()
    return -int(row["score"] or 0), int(website_score) if website_score else -1


def merge(new_leads, existing_rows):
    merged = {}

    for place_id, row in existing_rows.items():
        merged[place_id] = {column: row.get(column, "") for column in COLUMNS}

    for lead in new_leads:
        place_id = lead["place_id"]
        row = merged.get(place_id, {column: "" for column in COLUMNS})
        previous_status = row.get("status", "")
        row.update(
            {
                "score": lead["score"],
                "name": lead.get("name", ""),
                "address": lead.get("address", ""),
                "rating": "" if lead.get("rating") is None else lead["rating"],
                "review_count": "" if lead.get("review_count") is None else lead["review_count"],
                "website": lead.get("website", ""),
                "phone": lead.get("phone", ""),
                "google_maps_link": lead.get("google_maps_link", ""),
                "map_pin": lead.get("map_pin", ""),
                "contact_search": lead.get("contact_search", ""),
                "place_id": place_id,
                "status": previous_status,
            }
        )

        if not (lead.get("website") or "").strip():
            row["website_score"] = ""
            row["website_problems"] = ""
        elif lead.get("website_score") is not None:
            row["website_score"] = lead["website_score"]
            row["website_problems"] = "; ".join(lead.get("website_problems") or [])

        merged[place_id] = row

    rows = list(merged.values())
    rows.sort(key=_row_ranking_key)
    return rows


def save(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
    except PermissionError:
        raise FileLocked(
            "{} is open in another program, most likely Excel. Close it and try again.".format(path.name)
        )
    return path


def update_status(path, place_id, status):
    rows = load_rows(path)
    changed = False
    for row in rows:
        if row["place_id"] == place_id:
            row["status"] = status
            changed = True
    if changed:
        save(path, rows)
    return changed
