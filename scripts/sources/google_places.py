import time

import requests

ENDPOINT = "https://places.googleapis.com/v1/places:searchText"

FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.rating",
        "places.userRatingCount",
        "places.websiteUri",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.googleMapsUri",
        "places.primaryType",
        "places.businessStatus",
        "nextPageToken",
    ]
)


class SourceError(Exception):
    pass


class LimitReached(Exception):
    pass


def _lead_from_place(place):
    name = (place.get("displayName") or {}).get("text", "").strip()
    phone = place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber") or ""

    return {
        "place_id": place.get("id", ""),
        "name": name,
        "address": place.get("formattedAddress", ""),
        "rating": place.get("rating"),
        "review_count": place.get("userRatingCount"),
        "website": (place.get("websiteUri") or "").strip(),
        "phone": phone.strip(),
        "google_maps_link": place.get("googleMapsUri", ""),
        "category": place.get("primaryType", ""),
        "business_status": place.get("businessStatus", ""),
    }


def search(query, limit, settings, api_key, before_call):
    page_size = settings["search"]["google_page_size"]
    maximum = min(limit, settings["search"]["google_max_per_search"])

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }

    leads = []
    closed_dropped = 0
    calls = 0
    token = None
    stopped_at_limit = False

    while len(leads) < maximum:
        try:
            before_call()
        except LimitReached:
            if not leads:
                raise
            stopped_at_limit = True
            break

        body = {"textQuery": query, "pageSize": min(page_size, maximum - len(leads))}
        if token:
            body["pageToken"] = token

        try:
            response = requests.post(ENDPOINT, headers=headers, json=body, timeout=60)
            calls += 1
            if response.status_code == 403:
                raise SourceError(
                    "Google rejected the key (403). Check that Places API (New) is enabled "
                    "and that the key is not restricted to a different API."
                )
            if response.status_code == 429:
                raise SourceError("Google reports the quota is used up (429). Wait, or raise the daily quota.")
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as error:
            raise SourceError("Google Places API did not respond: {}".format(error))

        for place in data.get("places", []):
            lead = _lead_from_place(place)
            if not lead["name"]:
                continue
            if lead["business_status"] and lead["business_status"] != "OPERATIONAL":
                closed_dropped += 1
                continue
            leads.append(lead)

        token = data.get("nextPageToken")
        if not token:
            break
        time.sleep(1)

    return {
        "leads": leads[:maximum],
        "total_found": len(leads),
        "closed_dropped": closed_dropped,
        "calls": calls,
        "stopped_at_limit": stopped_at_limit,
    }
