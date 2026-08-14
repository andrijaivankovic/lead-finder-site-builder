def izracunaj_bodove(lokal, podesavanja):
    bodovi = podesavanja["bodovi"]
    pragovi = podesavanja["pragovi"]
    zbir = 0

    sajt = (lokal.get("sajt") or "").strip()
    if not sajt:
        zbir += bodovi["nema_sajt"]
    elif lokal.get("sajt_je_los"):
        zbir += bodovi["los_sajt"]

    ocena = lokal.get("ocena")
    if ocena is not None and ocena >= pragovi["dobra_ocena"]:
        zbir += bodovi["dobra_ocena"]

    recenzija = lokal.get("br_recenzija")
    if recenzija is not None:
        if recenzija >= pragovi["mnogo_recenzija"]:
            zbir += bodovi["mnogo_recenzija"]
        elif recenzija >= pragovi["srednje_recenzija"]:
            zbir += bodovi["srednje_recenzija"]
        elif recenzija < pragovi["malo_recenzija"]:
            zbir += bodovi["malo_recenzija"]

    if (lokal.get("telefon") or "").strip():
        zbir += bodovi["ima_telefon"]

    return zbir


def dodaj_bodove(lokali, podesavanja):
    for lokal in lokali:
        lokal["score"] = izracunaj_bodove(lokal, podesavanja)
    return sorted(lokali, key=lambda lokal: lokal["score"], reverse=True)
