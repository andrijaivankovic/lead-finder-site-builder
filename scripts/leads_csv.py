import csv
import re
import unicodedata
from datetime import date
from pathlib import Path

KOLONE = [
    "score",
    "naziv",
    "adresa",
    "ocena",
    "br_recenzija",
    "sajt",
    "telefon",
    "google_maps_link",
    "kontakt_pretraga",
    "place_id",
    "status",
]


def u_slug(tekst):
    bez_kvacica = unicodedata.normalize("NFKD", tekst)
    bez_kvacica = bez_kvacica.replace("đ", "dj").replace("Đ", "Dj")
    bez_kvacica = "".join(znak for znak in bez_kvacica if not unicodedata.combining(znak))
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", bez_kvacica).strip("-").lower()
    return slug or "pretraga"


def putanja_izlaza(koren, upit):
    ime = "leads_{}_{}.csv".format(u_slug(upit), date.today().isoformat())
    return Path(koren) / "data" / ime


def pronadji_prethodni(koren, upit):
    folder = Path(koren) / "data"
    if not folder.exists():
        return None
    kandidati = sorted(folder.glob("leads_{}_*.csv".format(u_slug(upit))))
    return kandidati[-1] if kandidati else None


def ucitaj(putanja):
    if not putanja or not Path(putanja).exists():
        return {}
    with open(putanja, newline="", encoding="utf-8-sig") as fajl:
        return {red["place_id"]: red for red in csv.DictReader(fajl) if red.get("place_id")}


def spoji(novi_lokali, stari_redovi):
    spojeno = {}

    for place_id, stari in stari_redovi.items():
        spojeno[place_id] = {kolona: stari.get(kolona, "") for kolona in KOLONE}

    for lokal in novi_lokali:
        place_id = lokal["place_id"]
        red = spojeno.get(place_id, {kolona: "" for kolona in KOLONE})
        stari_status = red.get("status", "")
        red.update(
            {
                "score": lokal["score"],
                "naziv": lokal.get("naziv", ""),
                "adresa": lokal.get("adresa", ""),
                "ocena": "" if lokal.get("ocena") is None else lokal["ocena"],
                "br_recenzija": "" if lokal.get("br_recenzija") is None else lokal["br_recenzija"],
                "sajt": lokal.get("sajt", ""),
                "telefon": lokal.get("telefon", ""),
                "google_maps_link": lokal.get("google_maps_link", ""),
                "kontakt_pretraga": lokal.get("kontakt_pretraga", ""),
                "place_id": place_id,
                "status": stari_status,
            }
        )
        spojeno[place_id] = red

    redovi = list(spojeno.values())
    redovi.sort(key=lambda red: int(red["score"] or 0), reverse=True)
    return redovi


def sacuvaj(putanja, redovi):
    putanja = Path(putanja)
    putanja.parent.mkdir(parents=True, exist_ok=True)
    with open(putanja, "w", newline="", encoding="utf-8-sig") as fajl:
        pisac = csv.DictWriter(fajl, fieldnames=KOLONE)
        pisac.writeheader()
        pisac.writerows(redovi)
    return putanja
