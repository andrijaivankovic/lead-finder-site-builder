import re
import time

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
USER_AGENT = "lead-finder-site-builder/0.1 (https://github.com/andrijaivankovic/lead-finder-site-builder)"
ELEMENT_TYPES = ("node", "way", "relation")
BUSINESS_KEYS = ("amenity", "shop", "office", "craft", "tourism", "leisure", "healthcare")


class SourceError(Exception):
    pass


def _geocode(place):
    try:
        response = requests.get(
            NOMINATIM_URL,
            params={"q": place, "format": "json", "limit": 1, "addressdetails": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()
        results = response.json()
    except requests.RequestException as error:
        raise SourceError("Could not reach the OpenStreetMap place lookup: {}".format(error))

    if not results:
        return None

    first = results[0]
    osm_id = int(first["osm_id"])
    country = (first.get("address") or {}).get("country_code", "")
    if first["osm_type"] == "relation":
        return {"area_id": 3600000000 + osm_id, "name": first["display_name"], "country": country}
    if first["osm_type"] == "way":
        return {"area_id": 2400000000 + osm_id, "name": first["display_name"], "country": country}
    return None


def split_term_and_place(query):
    words = query.split()
    if len(words) < 2:
        return None, None, None

    for word_count in range(min(3, len(words) - 1), 0, -1):
        place = " ".join(words[-word_count:])
        term = " ".join(words[:-word_count])
        area = _geocode(place)
        time.sleep(1)
        if area:
            return term, place, area

    return None, None, None


def _tag_conditions(filters):
    parts = []
    for tag_filter in filters:
        tags = "".join('["{}"="{}"]'.format(key, value) for key, value in tag_filter.items())
        for element_type in ELEMENT_TYPES:
            parts.append("  {}{}(area.searchArea);".format(element_type, tags))
    return "\n".join(parts)


def _name_conditions(term):
    pattern = re.escape(term).replace("/", "\\/").replace('"', '\\"')
    parts = []
    for key in BUSINESS_KEYS:
        for element_type in ELEMENT_TYPES:
            parts.append('  {}["{}"]["name"~"{}",i](area.searchArea);'.format(element_type, key, pattern))
    return "\n".join(parts)


def _build_query(area_id, conditions):
    return "[out:json][timeout:90];\narea(id:{})->.searchArea;\n(\n{}\n);\nout center tags;".format(
        area_id, conditions
    )


def _send_query(query_text, on_event=None):
    last_error = None

    for server in OVERPASS_SERVERS:
        try:
            response = requests.post(
                server,
                data={"data": query_text},
                headers={"User-Agent": USER_AGENT},
                timeout=120,
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as error:
            last_error = error
            if on_event:
                on_event("{} did not respond, trying the next server".format(server.split("/")[2]))
            time.sleep(2)

    raise SourceError(
        "No OpenStreetMap server responded. Last error: {}. These servers are free and "
        "frequently overloaded, so try again in a few minutes.".format(last_error)
    )


def _address_from_tags(tags):
    street = tags.get("addr:street", "")
    number = tags.get("addr:housenumber", "")
    city = tags.get("addr:city", "")
    street_line = " ".join(part for part in (street, number) if part).strip()
    return ", ".join(part for part in (street_line, city) if part)


def _category_from_tags(tags):
    cuisine = (tags.get("cuisine") or "").split(";")[0].strip()
    if cuisine:
        return cuisine
    for key in ("amenity", "shop", "craft", "office", "tourism", "leisure", "healthcare"):
        if tags.get(key):
            return tags[key]
    return ""


def _lead_from_element(element, place):
    tags = element.get("tags", {})
    name = (tags.get("name") or "").strip()
    if not name:
        return None

    center = element.get("center", {})
    latitude = element.get("lat", center.get("lat"))
    longitude = element.get("lon", center.get("lon"))

    address = _address_from_tags(tags)
    parts = [name]
    if address:
        parts.append(address)
    if place and place.lower() not in address.lower():
        parts.append(place)
    maps_link = "https://www.google.com/maps/search/?api=1&query={}".format(
        requests.utils.quote(", ".join(parts))
    )

    if latitude is not None and longitude is not None:
        map_pin = "https://www.google.com/maps/search/?api=1&query={},{}".format(latitude, longitude)
    else:
        map_pin = ""

    website = tags.get("website") or tags.get("contact:website") or tags.get("url") or ""
    phone = tags.get("phone") or tags.get("contact:phone") or tags.get("contact:mobile") or ""

    return {
        "place_id": "osm:{}/{}".format(element["type"], element["id"]),
        "name": name,
        "address": address,
        "rating": None,
        "review_count": None,
        "website": website.strip(),
        "phone": phone.strip(),
        "google_maps_link": maps_link,
        "map_pin": map_pin,
        "category": _category_from_tags(tags),
    }


def search(query, limit, settings, on_event=None):
    term, place, area = split_term_and_place(query)
    if not area:
        raise SourceError(
            "Could not recognise a place in '{}'. Write the search as a category followed by "
            "a place, for example \"pizzeria Novi Sad\".".format(query)
        )

    categories = settings.get("osm_categories", {})
    filters = categories.get(term.lower())

    if filters:
        conditions = _tag_conditions(filters)
        method = "category"
    else:
        conditions = _name_conditions(term)
        method = "name"

    data = _send_query(_build_query(area["area_id"], conditions), on_event)

    leads = []
    seen = set()
    for element in data.get("elements", []):
        lead = _lead_from_element(element, place)
        if not lead or lead["place_id"] in seen:
            continue
        seen.add(lead["place_id"])
        leads.append(lead)

    return {
        "leads": leads[:limit],
        "total_found": len(leads),
        "term": term,
        "place": place,
        "area": area["name"],
        "country": area.get("country", ""),
        "method": method,
        "calls": 0,
    }
