import argparse
import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

import yaml
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))

import leads_csv
import scoring
import usage
from sources import google_places, overpass

KOREN = Path(__file__).resolve().parent.parent


def _ucitaj_podesavanja():
    putanja = KOREN / "config.yaml"
    if not putanja.exists():
        _zaustavi("Nema fajla config.yaml u folderu projekta.")
    return yaml.safe_load(putanja.read_text(encoding="utf-8"))


def _zaustavi(poruka):
    print("\nGRESKA: {}\n".format(poruka))
    raise SystemExit(1)


def _skrati(tekst, sirina):
    tekst = str(tekst or "")
    if len(tekst) <= sirina:
        return tekst
    return tekst[: sirina - 1] + "…"


def _ispisi_tabelu(redovi, koliko):
    zaglavlja = ["#", "bodovi", "naziv", "ocena", "recenzija", "sajt", "telefon"]
    sirine = [3, 6, 34, 5, 9, 6, 16]

    linija = "+".join("-" * (sirina + 2) for sirina in sirine)
    print(linija)
    print(
        "|".join(
            " {} ".format(zaglavlje.ljust(sirina)) for zaglavlje, sirina in zip(zaglavlja, sirine)
        )
    )
    print(linija)

    for mesto, red in enumerate(redovi[:koliko], start=1):
        ima_sajt = "NEMA" if not (red.get("sajt") or "").strip() else "ima"
        celije = [
            str(mesto),
            str(red.get("score", "")),
            _skrati(red.get("naziv"), sirine[2]),
            str(red.get("ocena") or "-"),
            str(red.get("br_recenzija") or "-"),
            ima_sajt,
            _skrati(red.get("telefon") or "-", sirine[6]),
        ]
        print("|".join(" {} ".format(celija.ljust(sirina)) for celija, sirina in zip(celije, sirine)))

    print(linija)


def _dodaj_kontakt_pretragu(lokali, sablon):
    for lokal in lokali:
        if (lokal.get("telefon") or "").strip():
            lokal["kontakt_pretraga"] = ""
        else:
            lokal["kontakt_pretraga"] = sablon.format(naziv=quote_plus(lokal.get("naziv", "")))
    return lokali


def _napravi_kocnicu(mesecni_limit):
    def pre_poziva():
        potroseno = usage.procitaj(KOREN)["poziva"]
        if potroseno >= mesecni_limit:
            raise google_places.LimitDostignut(
                "Dostignut mesecni limit od {} poziva. Brojac je u data/usage.json.".format(mesecni_limit)
            )
        usage.zabelezi_poziv(KOREN)

    return pre_poziva


def _pretrazi_google(upit, limit, podesavanja, api_kljuc):
    mesecni_limit = podesavanja["zastita"]["mesecni_limit_poziva"]
    preostalo = usage.preostalo(KOREN, mesecni_limit)

    print("Izvor: Google Places API (New)")
    print("Poziva iskorišćeno ovog meseca: {} od {}\n".format(mesecni_limit - preostalo, mesecni_limit))

    if preostalo == 0:
        _zaustavi(
            "Potrošio si svih {} poziva za ovaj mesec. Brojač se resetuje prvog u mesecu, "
            "ili ga promeni u config.yaml pod zastita.mesecni_limit_poziva.".format(mesecni_limit)
        )

    try:
        return google_places.pretrazi(upit, limit, podesavanja, api_kljuc, _napravi_kocnicu(mesecni_limit))
    except google_places.LimitDostignut as greska:
        _zaustavi(str(greska))
    except google_places.GreskaIzvora as greska:
        _zaustavi(str(greska))


def _pretrazi_osm(upit, limit, podesavanja):
    print("Izvor: OpenStreetMap (besplatan, bez ključa)")
    print("Upozorenje: OpenStreetMap nema ocene ni broj recenzija.")
    print("Zato od pet kriterijuma rade samo dva - 'nema sajt' i 'ima telefon'.")
    print("Rangiranje je zato grublje nego sa Google ključem.\n")

    try:
        return overpass.pretrazi(upit, limit, podesavanja)
    except overpass.GreskaIzvora as greska:
        _zaustavi(str(greska))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Pronalazi lokalne firme i rangira ih kao kandidate za sajt.")
    parser.add_argument("upit", help='Na primer: "picerija Novi Sad"')
    parser.add_argument("--limit", type=int, default=None, help="Najviše koliko rezultata")
    parser.add_argument("--izvor", choices=["auto", "google", "osm"], default="auto")
    argumenti = parser.parse_args()

    load_dotenv(KOREN / ".env")
    podesavanja = _ucitaj_podesavanja()
    limit = argumenti.limit or podesavanja["pretraga"]["podrazumevani_limit"]
    api_kljuc = (os.getenv("GOOGLE_MAPS_API_KEY") or "").strip()

    if argumenti.izvor == "google" and not api_kljuc:
        _zaustavi("Tražio si Google, a GOOGLE_MAPS_API_KEY je prazan u .env fajlu.")

    koristi_google = argumenti.izvor == "google" or (argumenti.izvor == "auto" and api_kljuc)

    print('\nPretraga: "{}"'.format(argumenti.upit))
    print("Limit: {}\n".format(limit))

    if koristi_google:
        rezultat = _pretrazi_google(argumenti.upit, limit, podesavanja, api_kljuc)
    else:
        rezultat = _pretrazi_osm(argumenti.upit, limit, podesavanja)
        print("Prepoznato: delatnost '{}' u mestu '{}' ({})".format(
            rezultat["pojam"], rezultat["mesto"], rezultat["nacin"]
        ))
        print("Oblast: {}\n".format(rezultat["oblast"]))

    lokali = rezultat["lokali"]
    if not lokali:
        print("Nijedan rezultat. Probaj drugačiji pojam ili proveri kako se mesto zove na mapi.\n")
        return

    lokali = _dodaj_kontakt_pretragu(lokali, podesavanja["kontakt_pretraga_sablon"])
    lokali = scoring.dodaj_bodove(lokali, podesavanja)

    prethodni = leads_csv.pronadji_prethodni(KOREN, argumenti.upit)
    stari_redovi = leads_csv.ucitaj(prethodni)
    redovi = leads_csv.spoji(lokali, stari_redovi)
    putanja = leads_csv.sacuvaj(leads_csv.putanja_izlaza(KOREN, argumenti.upit), redovi)

    bez_sajta = sum(1 for lokal in lokali if not (lokal.get("sajt") or "").strip())

    print("Nađeno: {} firmi, od toga {} bez sajta.".format(len(lokali), bez_sajta))
    if rezultat.get("izbaceno_zatvorenih"):
        print("Izbačeno kao zatvoreno: {}".format(rezultat["izbaceno_zatvorenih"]))
    if prethodni:
        print("Spojeno sa: {} (tvoji statusi su sačuvani)".format(prethodni.name))
    if rezultat.get("prekinuto_zbog_limita"):
        print("Pretraga je prekinuta jer je dostignut mesečni limit poziva.")
    print("Snimljeno u: {}\n".format(putanja))

    _ispisi_tabelu(redovi, 15)

    if rezultat.get("poziva"):
        potroseno = usage.procitaj(KOREN)["poziva"]
        mesecni_limit = podesavanja["zastita"]["mesecni_limit_poziva"]
        print("\nPotrošeno poziva u ovoj pretrazi: {}".format(rezultat["poziva"]))
        print("Ukupno ovog meseca: {} od {}".format(potroseno, mesecni_limit))

    print()


if __name__ == "__main__":
    main()
