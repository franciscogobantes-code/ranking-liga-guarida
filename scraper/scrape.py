#!/usr/bin/env python3
"""Descarga los torneos "Liga Weekly" de La Guarida del Dragón desde melee.gg
y escribe site/data.json con las victorias/derrotas de cada jugador por torneo.

Solo usa la biblioteca estándar. Los torneos ya terminados que estén en el
data.json anterior se reutilizan para no volver a pedirlos.
"""
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ORG_ID = 16078
BASE = "https://melee.gg"
FILTRO = "liga weekly"
STATUS_TERMINADO = 4
OUT = Path(__file__).resolve().parent.parent / "site" / "data.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")

MATCH_COLUMNS = [
    ("TableNumber", True, True),
    ("PodNumber", True, True),
    ("Teams", False, False),
    ("Decklists", False, False),
    ("ResultString", False, False),
]


def datatables_body(columns, length=500):
    p = {"draw": "1", "start": "0", "length": str(length),
         "search[value]": "", "search[regex]": "false",
         "order[0][column]": "0", "order[0][dir]": "asc"}
    for i, (name, searchable, orderable) in enumerate(columns):
        p[f"columns[{i}][data]"] = name
        p[f"columns[{i}][name]"] = name
        p[f"columns[{i}][searchable]"] = str(searchable).lower()
        p[f"columns[{i}][orderable]"] = str(orderable).lower()
        p[f"columns[{i}][search][value]"] = ""
        p[f"columns[{i}][search][regex]"] = "false"
    return urllib.parse.urlencode(p).encode()


def request(path, body=None, tries=4):
    url = BASE + path
    headers = {"User-Agent": UA, "Accept": "application/json, text/javascript, text/html, */*; q=0.01",
               "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
               "Origin": BASE, "Referer": f"{BASE}/Hub/Organization/{ORG_ID}"}
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        headers["X-Requested-With"] = "XMLHttpRequest"
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers=headers,
                                         method="POST" if body is not None else "GET")
            with urllib.request.urlopen(req, timeout=40) as r:
                text = r.read().decode("utf-8")
            time.sleep(0.4)
            return text
        except urllib.error.HTTPError as e:
            if attempt == tries - 1:
                cuerpo = e.read()[:300].decode("utf-8", "replace")
                raise RuntimeError(f"Falló {url}: HTTP {e.code} {dict(e.headers).get('Server','')} | {cuerpo}") from e
            time.sleep(2 * (attempt + 1))
        except Exception as e:  # noqa: BLE001
            if attempt == tries - 1:
                raise RuntimeError(f"Falló {url}: {e}") from e
            time.sleep(2 * (attempt + 1))


def norm(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


class RoundIds(HTMLParser):
    """Lee los data-id de los botones de ronda del bloque de emparejamientos."""

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.ids = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.depth:
            if tag == "div":
                self.depth += 1
            if "round-selector" in (a.get("class") or "").split() and a.get("data-id"):
                self.ids.append(a["data-id"])
        elif a.get("id") == "pairings-round-selector-container":
            self.depth = 1

    def handle_endtag(self, tag):
        if self.depth and tag == "div":
            self.depth -= 1


def scrape_tournament(t):
    parser = RoundIds()
    parser.feed(request(f"/Tournament/View/{t['ID']}"))
    rounds = list(dict.fromkeys(parser.ids))
    players = {}
    first_match = None
    body = datatables_body(MATCH_COLUMNS)
    for rid in rounds:
        data = json.loads(request(f"/Match/GetRoundMatches/{rid}", body)).get("data") or []
        for m in data:
            created = m.get("DateCreated")
            if created and (first_match is None or created < first_match):
                first_match = created
            comps = m.get("Competitors") or []
            names = []
            for c in comps:
                ps = (c.get("Team") or {}).get("Players") or []
                u = " / ".join(p.get("Username") or p.get("DisplayName") or "?" for p in ps)
                names.append(u)
                players.setdefault(u, [0, 0, 0])
            if len(comps) == 1:          # bye = victoria
                players[names[0]][0] += 1
                continue
            if len(comps) < 2 or not m.get("HasResult"):
                continue
            a = comps[0].get("GameWinsAndGameByes") or 0
            b = comps[1].get("GameWinsAndGameByes") or 0
            if a > b:
                players[names[0]][0] += 1; players[names[1]][1] += 1
            elif b > a:
                players[names[1]][0] += 1; players[names[0]][1] += 1
            else:
                players[names[0]][2] += 1; players[names[1]][2] += 1
    return {
        "id": t["ID"],
        "name": " ".join((t.get("Name") or "").split()),
        # La fecha del primer emparejamiento es más confiable que la fecha
        # declarada del torneo (algunos torneos tienen mal la fecha en Melee).
        "date": first_match or t.get("StartDate"),
        "status": t.get("Status"),
        "res": [[u, w, l, d] for u, (w, l, d) in players.items()],
    }


def main():
    prev = {}
    if OUT.exists():
        try:
            prev = {x["id"]: x for x in json.loads(OUT.read_text())["tournaments"]}
        except Exception:  # noqa: BLE001
            prev = {}

    hub = json.loads(request(f"/Hub/SearchOrganizationTournaments/{ORG_ID}",
                             urllib.parse.urlencode({"draw": 1, "start": 0, "length": 1000}).encode()))
    candidatos = [t for t in hub.get("data") or [] if FILTRO in norm(t.get("Name"))]
    print(f"{len(candidatos)} torneos Liga Weekly en Melee")

    out = []
    for t in candidatos:
        old = prev.get(t["ID"])
        if old and old.get("status") == STATUS_TERMINADO and t.get("Status") == STATUS_TERMINADO:
            out.append(old)
            continue
        r = scrape_tournament(t)
        print(f"  {r['id']} {r['name']}: {len(r['res'])} jugadores (status {r['status']})")
        if r["res"]:
            out.append(r)

    if not out:
        sys.exit("No se encontró ningún torneo; no se sobrescribe data.json")

    out.sort(key=lambda x: x["date"])
    payload = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "tournaments": out}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    print(f"Escrito {OUT} con {len(out)} torneos")


if __name__ == "__main__":
    try:
        main()
    except BaseException as e:  # noqa: BLE001
        # Mensaje visible como anotación en la pestaña Actions
        msg = str(e).replace("\n", " ")[:900]
        print(f"::error title=Scraper::{type(e).__name__}: {msg}")
        raise
