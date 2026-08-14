import time

import requests

ENDPOINT = "https://places.googleapis.com/v1/places:searchText"

POLJA = ",".join(
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


class GreskaIzvora(Exception):
    pass


class LimitDostignut(Exception):
    pass


def _lokal_iz_odgovora(mesto):
    naziv = (mesto.get("displayName") or {}).get("text", "").strip()
    telefon = mesto.get("nationalPhoneNumber") or mesto.get("internationalPhoneNumber") or ""

    return {
        "place_id": mesto.get("id", ""),
        "naziv": naziv,
        "adresa": mesto.get("formattedAddress", ""),
        "ocena": mesto.get("rating"),
        "br_recenzija": mesto.get("userRatingCount"),
        "sajt": (mesto.get("websiteUri") or "").strip(),
        "telefon": telefon.strip(),
        "google_maps_link": mesto.get("googleMapsUri", ""),
        "vrsta": mesto.get("primaryType", ""),
        "status_poslovanja": mesto.get("businessStatus", ""),
    }


def pretrazi(upit, limit, podesavanja, api_kljuc, pre_poziva):
    po_strani = podesavanja["pretraga"]["google_po_strani"]
    najvise = min(limit, podesavanja["pretraga"]["google_max_po_pretrazi"])

    zaglavlja = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_kljuc,
        "X-Goog-FieldMask": POLJA,
    }

    lokali = []
    izbaceno_zatvorenih = 0
    poziva = 0
    token = None
    prekinuto_zbog_limita = False

    while len(lokali) < najvise:
        try:
            pre_poziva()
        except LimitDostignut:
            if not lokali:
                raise
            prekinuto_zbog_limita = True
            break

        telo = {"textQuery": upit, "pageSize": min(po_strani, najvise - len(lokali))}
        if token:
            telo["pageToken"] = token

        try:
            odgovor = requests.post(ENDPOINT, headers=zaglavlja, json=telo, timeout=60)
            poziva += 1
            if odgovor.status_code == 403:
                raise GreskaIzvora(
                    "Google je odbio ključ (403). Proveri da je Places API (New) uključen "
                    "i da ključ nije ograničen na drugi API."
                )
            if odgovor.status_code == 429:
                raise GreskaIzvora("Google javlja da je kvota potrošena (429). Sačekaj ili podigni dnevnu kvotu.")
            odgovor.raise_for_status()
            podaci = odgovor.json()
        except requests.RequestException as greska:
            raise GreskaIzvora("Google Places API nije odgovorio: {}".format(greska))

        for mesto in podaci.get("places", []):
            lokal = _lokal_iz_odgovora(mesto)
            if not lokal["naziv"]:
                continue
            if lokal["status_poslovanja"] and lokal["status_poslovanja"] != "OPERATIONAL":
                izbaceno_zatvorenih += 1
                continue
            lokali.append(lokal)

        token = podaci.get("nextPageToken")
        if not token:
            break
        time.sleep(1)

    return {
        "lokali": lokali[:najvise],
        "ukupno_nadjeno": len(lokali),
        "izbaceno_zatvorenih": izbaceno_zatvorenih,
        "poziva": poziva,
        "prekinuto_zbog_limita": prekinuto_zbog_limita,
    }
