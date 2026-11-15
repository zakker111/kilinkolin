"""Kide.app — real student events in Tampere.

Kide is the ticketing platform most Tampere student organisations use. Its public
product list carries the event name, the organiser, a free-text place and a real
start **and** end time, which the music feed does not have. It carries no
coordinates, so build.py resolves the place against the venue registry and drops
anything it cannot put on a real address — nothing is guessed here.

Source: https://api.kide.app/api/products?city=Tampere (public JSON, no key).
"""
import datetime as dt
import json
import urllib.request
from zoneinfo import ZoneInfo

URL = "https://api.kide.app/api/products?city=Tampere"
TZ = ZoneInfo("Europe/Helsinki")
MAX_EVENTS = 80          # keep one build bounded; the daily refresh picks up the rest
SKIP_WORDS = ("jäsenyys", "membership", "kausikortti", "season card", "lahjakortti",
              "gift card", " Lippu", "lippupaketti")


def fetch():
    """Return (events, status). Each event is a plain dict; never raises."""
    try:
        req = urllib.request.Request(
            URL, headers={"User-Agent": "kilinkolin/0.11 (+https://github.com/zakker111/kilinkolin)"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        products = payload.get("model") or []
    except Exception as exc:  # noqa: BLE001 - a broken source must not blank the site
        return [], f"FAILED: {exc}"

    today = dt.date.today()
    out, seen = [], set()
    for p in products:
        try:
            raw_from = p.get("dateActualFrom")
            if not raw_from:
                continue
            starts = dt.datetime.fromisoformat(raw_from).astimezone(TZ)
            ends = dt.datetime.fromisoformat(p["dateActualUntil"]).astimezone(TZ) if p.get("dateActualUntil") else None
            if starts.date() < today:
                continue
            title = (p.get("name") or "").strip()
            if not title or any(w.lower() in title.lower() for w in SKIP_WORDS):
                continue
            minutes = round((ends - starts).total_seconds() / 60) if ends else 0
            if minutes < 30:
                # no trustworthy end: let the model fall back to its typical duration
                minutes = 0
            # one product per organiser: four clubs selling the same jam are one event, even when
            # each spells the campus differently ("TAMK C3 Game Studio", "TAMK Games Academy", …)
            place = " ".join((p.get("place") or "").split())
            key = (starts.date().isoformat(), starts.strftime("%H:%M"), " ".join(title.lower().split()))
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "date": starts.date().isoformat(),
                "time": starts.strftime("%H:%M"),
                "title": title,
                "place": place,
                "organizer": (p.get("companyName") or "").strip(),
                "minutes": minutes,
                "free": _price(p.get("minPrice")) == 0,
            })
        except (ValueError, TypeError, KeyError, AttributeError):
            continue  # one malformed product must not lose the whole source
        if len(out) >= MAX_EVENTS:
            break
    return out, "OK"


def _price(value):
    """minPrice arrives as a number or as a money object; anything else counts as unknown."""
    if isinstance(value, dict):
        value = value.get("amount", value.get("value"))
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
