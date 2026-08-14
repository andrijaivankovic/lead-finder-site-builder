import re
import time

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_SERVERI = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
KORISNICKI_AGENT = "prospect-kit/0.1 (https://github.com/topics/lead-generation)"
TIPOVI_ELEMENATA = ("node", "way", "relation")
POSLOVNI_KLJUCEVI = ("amenity", "shop", "office", "craft", "tourism", "leisure", "healthcare")


class GreskaIzvora(Exception):
    pass


def _geokodiraj(mesto):
    try:
        odgovor = requests.get(
            NOMINATIM_URL,
            params={"q": mesto, "format": "json", "limit": 1},
            headers={"User-Agent": KORISNICKI_AGENT},
            timeout=30,
        )
        odgovor.raise_for_status()
        rezultati = odgovor.json()
    except requests.RequestException as greska:
        raise GreskaIzvora("Nije uspelo povezivanje sa OpenStreetMap pretragom mesta: {}".format(greska))

    if not rezultati:
        return None

    prvi = rezultati[0]
    osm_id = int(prvi["osm_id"])
    if prvi["osm_type"] == "relation":
        return {"area_id": 3600000000 + osm_id, "ime": prvi["display_name"]}
    if prvi["osm_type"] == "way":
        return {"area_id": 2400000000 + osm_id, "ime": prvi["display_name"]}
    return None


def razdvoji_pojam_i_mesto(upit):
    reci = upit.split()
    if len(reci) < 2:
        return None, None, None

    for broj_reci in range(min(3, len(reci) - 1), 0, -1):
        mesto = " ".join(reci[-broj_reci:])
        pojam = " ".join(reci[:-broj_reci])
        oblast = _geokodiraj(mesto)
        time.sleep(1)
        if oblast:
            return pojam, mesto, oblast

    return None, None, None


def _uslovi_po_oznakama(filteri):
    delovi = []
    for filter_oznaka in filteri:
        oznake = "".join('["{}"="{}"]'.format(kljuc, vrednost) for kljuc, vrednost in filter_oznaka.items())
        for tip in TIPOVI_ELEMENATA:
            delovi.append("  {}{}(area.oblast);".format(tip, oznake))
    return "\n".join(delovi)


def _uslovi_po_imenu(pojam):
    obrazac = re.escape(pojam).replace("/", "\\/").replace('"', '\\"')
    delovi = []
    for kljuc in POSLOVNI_KLJUCEVI:
        for tip in TIPOVI_ELEMENATA:
            delovi.append('  {}["{}"]["name"~"{}",i](area.oblast);'.format(tip, kljuc, obrazac))
    return "\n".join(delovi)


def _upit_za_overpass(area_id, uslovi):
    return "[out:json][timeout:90];\narea(id:{})->.oblast;\n(\n{}\n);\nout center tags;".format(area_id, uslovi)


def _posalji_upit(upit_teksta):
    poslednja_greska = None

    for server in OVERPASS_SERVERI:
        try:
            odgovor = requests.post(
                server,
                data={"data": upit_teksta},
                headers={"User-Agent": KORISNICKI_AGENT},
                timeout=120,
            )
            odgovor.raise_for_status()
            return odgovor.json()
        except (requests.RequestException, ValueError) as greska:
            poslednja_greska = greska
            print("  server {} nije odgovorio, prelazim na sledeći".format(server.split("/")[2]))
            time.sleep(2)

    raise GreskaIzvora(
        "Nijedan OpenStreetMap server nije odgovorio. Poslednja greška: {}. "
        "Ovi serveri su besplatni i povremeno preopterećeni - pokušaj ponovo za par minuta.".format(poslednja_greska)
    )


def _adresa_iz_oznaka(oznake):
    ulica = oznake.get("addr:street", "")
    broj = oznake.get("addr:housenumber", "")
    grad = oznake.get("addr:city", "")
    prvi_deo = " ".join(deo for deo in (ulica, broj) if deo).strip()
    return ", ".join(deo for deo in (prvi_deo, grad) if deo)


def _lokal_iz_elementa(element):
    oznake = element.get("tags", {})
    naziv = (oznake.get("name") or "").strip()
    if not naziv:
        return None

    centar = element.get("center", {})
    sirina = element.get("lat", centar.get("lat"))
    duzina = element.get("lon", centar.get("lon"))

    if sirina is not None and duzina is not None:
        maps_link = "https://www.google.com/maps/search/?api=1&query={},{}".format(sirina, duzina)
    else:
        maps_link = "https://www.google.com/maps/search/?api=1&query={}".format(requests.utils.quote(naziv))

    sajt = oznake.get("website") or oznake.get("contact:website") or oznake.get("url") or ""
    telefon = (
        oznake.get("phone")
        or oznake.get("contact:phone")
        or oznake.get("contact:mobile")
        or ""
    )

    return {
        "place_id": "osm:{}/{}".format(element["type"], element["id"]),
        "naziv": naziv,
        "adresa": _adresa_iz_oznaka(oznake),
        "ocena": None,
        "br_recenzija": None,
        "sajt": sajt.strip(),
        "telefon": telefon.strip(),
        "google_maps_link": maps_link,
        "vrsta": oznake.get("amenity") or oznake.get("shop") or oznake.get("craft") or oznake.get("office") or "",
    }


def pretrazi(upit, limit, podesavanja):
    pojam, mesto, oblast = razdvoji_pojam_i_mesto(upit)
    if not oblast:
        raise GreskaIzvora(
            "Nisam prepoznao grad u pretrazi '{}'. Napiši je u obliku: delatnost pa mesto, "
            "na primer \"picerija Novi Sad\".".format(upit)
        )

    delatnosti = podesavanja.get("osm_delatnosti", {})
    filteri = delatnosti.get(pojam.lower())

    if filteri:
        uslovi = _uslovi_po_oznakama(filteri)
        nacin = "po vrsti delatnosti"
    else:
        uslovi = _uslovi_po_imenu(pojam)
        nacin = "po imenu firme"

    podaci = _posalji_upit(_upit_za_overpass(oblast["area_id"], uslovi))

    lokali = []
    videni = set()
    for element in podaci.get("elements", []):
        lokal = _lokal_iz_elementa(element)
        if not lokal or lokal["place_id"] in videni:
            continue
        videni.add(lokal["place_id"])
        lokali.append(lokal)

    return {
        "lokali": lokali[:limit],
        "ukupno_nadjeno": len(lokali),
        "pojam": pojam,
        "mesto": mesto,
        "oblast": oblast["ime"],
        "nacin": nacin,
        "poziva": 0,
    }
