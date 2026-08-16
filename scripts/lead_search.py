import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

import yaml
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lead_store
import scoring
import site_audit
import usage
from sources import google_places, overpass

ROOT = Path(__file__).resolve().parent.parent


class SearchError(Exception):
    pass


def load_settings():
    path = ROOT / "config.yaml"
    if not path.exists():
        raise SearchError("config.yaml is missing from the project folder.")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def google_key():
    load_dotenv(ROOT / ".env")
    return (os.getenv("GOOGLE_MAPS_API_KEY") or "").strip()


def usage_summary(settings=None):
    settings = settings or load_settings()
    limit = settings["protection"]["monthly_call_limit"]
    return {"used": usage.read(ROOT)["calls"], "limit": limit}


def _add_contact_search(leads, template):
    for lead in leads:
        if (lead.get("phone") or "").strip():
            lead["contact_search"] = ""
        else:
            lead["contact_search"] = template.format(name=quote_plus(lead.get("name", "")))
    return leads


def _audit_websites(leads, settings, on_event=None):
    options = settings["audit"]
    urls = [lead["website"] for lead in leads if (lead.get("website") or "").strip()]
    if not urls:
        return 0

    if on_event:
        on_event("Checking {} existing websites".format(len(urls)))

    reports = site_audit.audit_many(urls, settings)

    for lead in leads:
        report = reports.get(lead.get("website") or "")
        if not report:
            continue
        lead["website_score"] = report["score"]
        lead["website_problems"] = report["problems"]
        lead["website_is_poor"] = report["score"] < options["poor_website_below"]

    return len(urls)


def _call_guard(monthly_limit):
    def before_call():
        if usage.read(ROOT)["calls"] >= monthly_limit:
            raise google_places.LimitReached(
                "Monthly limit of {} calls reached. The counter lives in data/usage.json.".format(monthly_limit)
            )
        usage.record_call(ROOT)

    return before_call


def run_search(query, limit=None, source="auto", on_event=None, audit=None):
    query = (query or "").strip()
    if not query:
        raise SearchError("The search is empty.")

    settings = load_settings()
    limit = limit or settings["search"]["default_limit"]
    api_key = google_key()

    if source == "google" and not api_key:
        raise SearchError("Google was requested but GOOGLE_MAPS_API_KEY is empty in .env.")

    use_google = source == "google" or (source == "auto" and api_key)

    if use_google:
        monthly_limit = settings["protection"]["monthly_call_limit"]
        if usage.remaining(ROOT, monthly_limit) == 0:
            raise SearchError(
                "All {} calls for this month are used up. The counter resets on the first of the "
                "month, or change protection.monthly_call_limit in config.yaml.".format(monthly_limit)
            )
        try:
            result = google_places.search(query, limit, settings, api_key, _call_guard(monthly_limit))
        except (google_places.SourceError, google_places.LimitReached) as error:
            raise SearchError(str(error))
        result["source"] = "google"
    else:
        try:
            result = overpass.search(query, limit, settings, on_event)
        except overpass.SourceError as error:
            raise SearchError(str(error))
        result["source"] = "openstreetmap"

    leads = result["leads"]
    if not leads:
        result.update({"rows": [], "path": None, "previous": None, "without_website": 0})
        return result

    leads = _add_contact_search(leads, settings["contact_search_template"])

    run_audit = settings["audit"]["enabled"] if audit is None else audit
    audited = _audit_websites(leads, settings, on_event) if run_audit else 0

    leads = scoring.add_scores(leads, settings)

    previous = lead_store.find_previous(ROOT, query)
    rows = lead_store.merge(leads, lead_store.load(previous))
    try:
        path = lead_store.save(lead_store.output_path(ROOT, query), rows)
    except lead_store.FileLocked as error:
        raise SearchError(str(error))

    result.update(
        {
            "rows": rows,
            "path": path,
            "previous": previous.name if previous else None,
            "without_website": sum(1 for lead in leads if not (lead.get("website") or "").strip()),
            "audited": audited,
            "poor_websites": sum(1 for lead in leads if lead.get("website_is_poor")),
            "query": query,
            "limit": limit,
        }
    )
    return result
