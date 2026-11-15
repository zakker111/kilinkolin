"""Kide.app — real student events in Tampere.

Kide is the ticketing platform most Tampere student organisations use. Its public
product list carries the event name, the organiser, a free-text place and a real
start **and** end time, which the music feed does not have. The list has no coordinates;
when its place does not match the venue registry, build.py reads the public product
detail, which carries the organiser's published street address and point. Entries with
only a vague place or a postal box are dropped — nothing is guessed here.

Source: https://api.kide.app/api/products?city=Tampere (public JSON, no key).
"""
import datetime as dt
import json
import urllib.request
from zoneinfo import ZoneInfo

URL = "https://api.kide.app/api/products?city=Tampere"
DETAIL_URL = "https://api.kide.app/api/products/{id}"
TZ = ZoneInfo("Europe/Helsinki")
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

    today = dt.datetime.now(TZ).date()
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
                "product_id": p.get("id"),
                "place": place,
                "organizer": (p.get("companyName") or "").strip(),
                "minutes": minutes,
                "free": _price(p.get("minPrice")) == 0,
            })
        except (ValueError, TypeError, KeyError, AttributeError):
            continue  # one malformed product must not lose the whole source
    return out, "OK"


_DETAIL_CACHE = {}


def fetch_detail(product_id):
    """Return Kide's published location for a product, or None.

    The list endpoint carries only a free-text place. The product detail carries the
    street address and point that the organiser published; use that instead of guessing.
    Never raise: one unavailable detail must not lose the whole student feed.
    """
    if not product_id:
        return None
    if product_id in _DETAIL_CACHE:
        return _DETAIL_CACHE[product_id]
    try:
        req = urllib.request.Request(
            DETAIL_URL.format(id=product_id),
            headers={"User-Agent": "kilinkolin/0.11 (+https://github.com/zakker111/kilinkolin)"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            model = (json.loads(resp.read().decode("utf-8")) or {}).get("model") or {}
        detail = model.get("product") if isinstance(model, dict) else None
        _DETAIL_CACHE[product_id] = detail if isinstance(detail, dict) else None
    except Exception:  # noqa: BLE001 - detail lookup is optional
        _DETAIL_CACHE[product_id] = None
    return _DETAIL_CACHE[product_id]


def _price(value):
    """minPrice arrives as a number or as a money object; anything else counts as unknown."""
    if isinstance(value, dict):
        value = value.get("amount", value.get("value"))
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
