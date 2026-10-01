#!/usr/bin/env python3
"""Hämtar statslåneräntan från Riksgälden och skriver slr.json till bolånekalkylen.

Användning: python scripts/hamta_slr.py [sökväg till slr.json]
Skriptet ändrar inte filen om hämtningen eller tolkningen misslyckas.
"""
import datetime
import json
import os
import re
import sys
import tempfile
import urllib.request

URL = "https://www.riksgalden.se/globalassets/dokument_sve/statslaneranta/statslanerantor.csv"
FRAN = "2000-01-01"          # äldre veckor behövs inte i verktyget
MIN_RADER = 100

RE_DATUM = re.compile(r"\d{4}-\d{2}-\d{2}")
RE_RANTA = re.compile(r"-?\d{1,2}[,.]\d{1,4}")


def hamta() -> str:
    req = urllib.request.Request(URL, headers={"User-Agent": "bolanekalkyl-slr/1.0 (GitHub Actions)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8-sig", errors="replace")


def tolka(text: str) -> list:
    rader = {}
    for line in text.splitlines():
        c = [x.strip().strip('"').strip() for x in line.split(";")]
        if len(c) < 2 or not RE_DATUM.fullmatch(c[0]) or not RE_RANTA.fullmatch(c[1]):
            continue
        datetime.date.fromisoformat(c[0])          # ogiltigt datum ger undantag
        if c[0] < FRAN:
            continue
        v = round(float(c[1].replace(",", ".")), 4)
        if not -10 < v < 30:
            raise ValueError(f"Orimligt värde {v} för {c[0]}")
        rader[c[0]] = v                             # dubbletter vid årsskiften har samma ränta
    return sorted(rader.items())


def skriv(serie: list, ut: str) -> None:
    senaste = serie[-1]
    huvud = {"kalla": URL, "senaste": {"datum": senaste[0], "ranta": senaste[1]}}
    text = json.dumps(huvud, ensure_ascii=False)[:-1] + ',"serie":[\n'
    text += ",\n".join(json.dumps([d, v]) for d, v in serie) + "\n]}\n"
    mapp = os.path.dirname(os.path.abspath(ut))
    fd, tmp = tempfile.mkstemp(dir=mapp, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, ut)


def main() -> int:
    ut = sys.argv[1] if len(sys.argv) > 1 else "slr.json"
    try:
        serie = tolka(hamta())
    except Exception as e:  # noqa: BLE001
        print(f"Fel: {e}. {ut} lämnas orörd.", file=sys.stderr)
        return 1
    if len(serie) < MIN_RADER:
        print(f"Fel: bara {len(serie)} rader tolkades. {ut} lämnas orörd.", file=sys.stderr)
        return 1
    senaste = serie[-1]
    alder = (datetime.date.today() - datetime.date.fromisoformat(senaste[0])).days
    if alder > 21:
        print(f"Varning: senaste värdet är {alder} dagar gammalt ({senaste[0]}).", file=sys.stderr)
    skriv(serie, ut)
    print(f"OK: {len(serie)} veckor, senaste {senaste[0]} = {senaste[1]} %")
    return 0


if __name__ == "__main__":
    sys.exit(main())
