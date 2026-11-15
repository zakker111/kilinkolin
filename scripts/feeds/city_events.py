"""Tampereen tapahtumakalenteri — real stage, culture, library and community events.

The city's own event calendar publishes each event with its location, and every location
carries an exact latitude/longitude plus a street address. Rows keep that published point, so a
library reading, a theatre premiere or a craft workshop lands on the real building — nothing is
geocoded or guessed here.

Source: https://tapahtumat.tampere.fi/api/search/internal-content-fetch?lang=fi&country=FI&q=
The endpoint is bound to the calendar's own host and needs both `lang=fi` and `country=FI`; it
returns the whole public calendar in one response (~3 MB, no key, no pagination).

Scope kept deliberately narrow:

* only events with a real, single-day start and end (an exhibition running for months is not a
  crowd arriving at an hour, so it is left out rather than spread over every day of its run);
* music-only rows are skipped — `tampere-keikat` already supplies gigs with their own feed;
* rows already published by another source (same day, same title) are skipped by `build.py`.
"""
import datetime as dt
import json
import urllib.request
from zoneinfo import ZoneInfo

URL = "https://tapahtumat.tampere.fi/api/search/internal-content-fetch?lang=fi&country=FI&q="
UA = "kilinkolin/0.12 (+https://github.com/zakker111/kilinkolin)"
TZ = ZoneInfo("Europe/Helsinki")
MAX_EVENTS = 220          # one build stays bounded; the daily refresh picks up the rest

STAGE_CATS = {"theatre", "dance", "comedy", "circus", "opera", "performances", "musical"}
CULTURE_CATS = {"museums", "museums and galleries", "exhibitions", "literature", "film",
                "library", "libraries", "arts", "culture"}
COMMUNITY_CATS = {"handicraft", "food and beverage", "kids and family", "festivals", "markets",
                  "fairs", "courses", "workshops", "guidance", "nature and well-being",
                  "well-being", "participation"}
MUSIC_CATS = {"music", "consert", "concerts", "gig", "clubs", "club"}


def fetch():
    """Return (events, status). Each event is a plain dict; never raises."""
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=90) as resp:
            pages = (json.loads(resp.read().decode("utf-8")) or {}).get("pages") or []
    except Exception as exc:  # noqa: BLE001 - a broken source must not blank the site
        return [], f"FAILED: {exc}"

    today = dt.date.today()
    out = []
    for page in pages:
        if page.get("pageType") != "event":
            continue
        try:
            item = _event(page, today)
        except (ValueError, TypeError, KeyError, AttributeError):
            continue  # one malformed page must not lose the whole source
        if item:
            out.extend(item)
    out.sort(key=lambda e: (e["date"], e["time"]))
    del out[MAX_EVENTS:]
    return out, ("OK" if out else "EMPTY")


def _event(page, today):
    """One calendar page -> zero or more single-day event rows."""
    ev = page.get("event") or {}
    loc = (page.get("locations") or [{}])[0] or {}
    lat, lon = loc.get("lat"), loc.get("lng")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return []
    address = (loc.get("address") or "").strip()
    if not address:
        return []
    title = (page.get("name") or "").strip()
    if not title:
        return []

    cats = {str(c).lower() for c in (page.get("globalContentCategories") or [])}
    kind, sub = _classify(cats)
    if kind is None:
        return []

    price = page.get("price") or {}
    try:
        free = float(price.get("min", 1)) == 0
    except (TypeError, ValueError):
        free = False
    url = ""
    for link in page.get("links") or []:
        if link.get("url"):
            url = link["url"]
            break
    participants = page.get("maxParticipants") or ev.get("maxParticipants") or 0
    try:
        participants = int(participants)
    except (TypeError, ValueError):
        participants = 0

    spans = ev.get("dates") or []
    if not spans and ev.get("start"):
        spans = [{"start": ev.get("start"), "end": ev.get("end")}]

    rows = []
    for span in spans:
        raw_start = span.get("start")
        if not raw_start:
            continue
        start = dt.datetime.fromisoformat(raw_start.replace("Z", "+00:00")).astimezone(TZ)
        if start.date() < today:
            continue
        raw_end = span.get("end") or ev.get("end")
        end = dt.datetime.fromisoformat(raw_end.replace("Z", "+00:00")).astimezone(TZ) if raw_end else None
        if not end or end.date() != start.date():
            continue  # ongoing or multi-day: no single arrival hour to model
        minutes = round((end - start).total_seconds() / 60)
        if minutes < 20:
            minutes = 0  # untrustworthy end: let the model fall back to its typical duration
        rows.append({
            "date": start.date().isoformat(),
            "time": start.strftime("%H:%M"),
            "title": title,
            "place": address,
            "lat": round(float(lat), 6),
            "lon": round(float(lon), 6),
            "minutes": minutes,
            "free": free,
            "url": url,
            "kind": kind,
            "sub": sub,
            "max_participants": participants,
            "organizer": (page.get("ownerName") or "").strip(),
        })
    return rows


def _classify(cats):
    """City content categories -> (kind, subcategory) from the build's taxonomy."""
    if cats & MUSIC_CATS and not cats & (STAGE_CATS | CULTURE_CATS | COMMUNITY_CATS):
        return None, None          # gigs and concerts belong to the music feed
    if cats & STAGE_CATS:
        if "dance" in cats:
            return "stage", "dance"
        if "comedy" in cats:
            return "stage", "comedy"
        return "stage", "theatre"
    if cats & CULTURE_CATS:
        if cats & {"museums", "museums and galleries", "exhibitions"}:
            return "culture", "exhibition"
        if "literature" in cats:
            return "culture", "literature"
        if "film" in cats:
            return "culture", "film"
        # a library or arts-centre listing without a literature/film/exhibition tag is
        # guidance, a talk or a club — that is a community event
        return "community", "lecture"
    if cats & COMMUNITY_CATS:
        if cats & {"kids and family"}:
            return "community", "family"
        if cats & {"food and beverage"}:
            return "community", "food"
        if cats & {"festivals", "markets", "fairs"}:
            return "community", "fair"
        if cats & {"handicraft", "workshops"}:
            return "community", "workshop"
        return "community", "lecture"      # courses, guidance, well-being, tt_* theme tags
    return "community", "participation"
