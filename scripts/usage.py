import json
from datetime import datetime
from pathlib import Path


def _putanja(koren):
    return Path(koren) / "data" / "usage.json"


def _tekuci_mesec():
    return datetime.now().strftime("%Y-%m")


def procitaj(koren):
    putanja = _putanja(koren)
    mesec = _tekuci_mesec()
    if not putanja.exists():
        return {"mesec": mesec, "poziva": 0}
    zapis = json.loads(putanja.read_text(encoding="utf-8"))
    if zapis.get("mesec") != mesec:
        return {"mesec": mesec, "poziva": 0}
    return {"mesec": mesec, "poziva": int(zapis.get("poziva", 0))}


def preostalo(koren, mesecni_limit):
    return max(0, mesecni_limit - procitaj(koren)["poziva"])


def zabelezi_poziv(koren):
    zapis = procitaj(koren)
    zapis["poziva"] += 1
    putanja = _putanja(koren)
    putanja.parent.mkdir(parents=True, exist_ok=True)
    putanja.write_text(json.dumps(zapis, ensure_ascii=False, indent=2), encoding="utf-8")
    return zapis["poziva"]
