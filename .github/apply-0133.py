from pathlib import Path


def edit(path, pairs):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert old in s, f"missing in {path}: {old[:70]!r}"
        s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")


edit("scripts/feeds/kide.py", [
    (
        'Kide is the ticketing platform most Tampere student organisations use. Its public\n'
        'product list carries the event name, the organiser, a free-text place and a real\n'
        'start **and** end time, which the music feed does not have. It carries no\n'
        'coordinates, so build.py resolves the place against the venue registry and drops\n'
        'anything it cannot put on a real address — nothing is guessed here.\n',
        'Kide is the ticketing platform most Tampere student organisations use. Its public\n'
        'product list carries the event name, the organiser, a free-text place and a real\n'
        'start **and** end time, which the music feed does not have. The list has no coordinates;\n'
        'when its place does not match the venue registry, build.py reads the public product\n'
        'detail, which carries the organiser\'s published street address and point. Entries with\n'
        'only a vague place or a postal box are dropped — nothing is guessed here.\n',
    ),
    (
        'URL = "https://api.kide.app/api/products?city=Tampere"\nTZ = ZoneInfo("Europe/Helsinki")',
        'URL = "https://api.kide.app/api/products?city=Tampere"\nDETAIL_URL = "https://api.kide.app/api/products/{id}"\nTZ = ZoneInfo("Europe/Helsinki")',
    ),
    (
        '                "date": starts.date().isoformat(),\n'
        '                "time": starts.strftime("%H:%M"),\n'
        '                "title": title,\n',
        '                "date": starts.date().isoformat(),\n'
        '                "time": starts.strftime("%H:%M"),\n'
        '                "title": title,\n'
        '                "product_id": p.get("id"),\n',
    ),
    (
        'def _price(value):\n',
        '_DETAIL_CACHE = {}\n\n\n'
        'def fetch_detail(product_id):\n'
        '    """Return Kide\'s published location for a product, or None.\n\n'
        '    The list endpoint carries only a free-text place. The product detail carries the\n'
        '    street address and point that the organiser published; use that instead of guessing.\n'
        '    Never raise: one unavailable detail must not lose the whole student feed.\n'
        '    """\n'
        '    if not product_id:\n'
        '        return None\n'
        '    if product_id in _DETAIL_CACHE:\n'
        '        return _DETAIL_CACHE[product_id]\n'
        '    try:\n'
        '        req = urllib.request.Request(\n'
        '            DETAIL_URL.format(id=product_id),\n'
        '            headers={"User-Agent": "kilinkolin/0.11 (+https://github.com/zakker111/kilinkolin)"})\n'
        '        with urllib.request.urlopen(req, timeout=20) as resp:\n'
        '            model = (json.loads(resp.read().decode("utf-8")) or {}).get("model") or {}\n'
        '        detail = model.get("product") if isinstance(model, dict) else None\n'
        '        _DETAIL_CACHE[product_id] = detail if isinstance(detail, dict) else None\n'
        '    except Exception:  # noqa: BLE001 - detail lookup is optional\n'
        '        _DETAIL_CACHE[product_id] = None\n'
        '    return _DETAIL_CACHE[product_id]\n\n\n'
        'def _price(value):\n',
    ),
])


edit("scripts/build.py", [
    ('import math\nimport os\nimport sys', 'import math\nimport os\nimport re\nimport sys'),
    (
        'def kide_rows(alias_idx):\n'
        '    """Kide products placed on a real registry venue; anything unplaceable is dropped."""\n'
        '    events, status = kide_feed.fetch()\n'
        '    rows, skipped = [], Counter()\n'
        '    for ev in events:\n'
        '        venue = resolve_venue(ev["place"], alias_idx, VENUES)\n'
        '        if not venue or venue["id"] == "tampere_muu":\n'
        '            skipped[ev["place"] or "(no place)"] += 1\n'
        '            continue\n',
        'def kide_rows(alias_idx):\n'
        '    """Kide products placed on a real registry venue; anything unplaceable is dropped."""\n'
        '    events, status = kide_feed.fetch()\n'
        '    rows, skipped = [], Counter()\n'
        '    for ev in events:\n'
        '        venue = resolve_venue(ev["place"], alias_idx, VENUES)\n'
        '        if not venue or venue["id"] == "tampere_muu":\n'
        '            detail = kide_feed.fetch_detail(ev.get("product_id"))\n'
        '            venue = kide_detail_venue(ev, detail)\n'
        '        if not venue or venue["id"] == "tampere_muu":\n'
        '            skipped[ev["place"] or "(no place)"] += 1\n'
        '            continue\n',
    ),
    (
        '    student_rows, student_status = kide_rows(alias_idx)\n'
        '    city_items, city_status = city_feed.fetch()\n',
        '    student_rows, student_status = kide_rows(alias_idx)\n'
        '    # kide_rows can add a venue whose location came from the product detail endpoint;\n'
        '    # include those names before the student rows are resolved a second time.\n'
        '    alias_idx = build_alias_index(VENUES)\n'
        '    city_items, city_status = city_feed.fetch()\n',
    ),
    (
        'def venue_record(v):\n',
        'def kide_detail_venue(ev, detail):\n'
        '    """Use the address and point published in a Kide product detail.\n\n'
        '    The list endpoint only has a free-text place; the detail is the organiser\'s own\n'
        '    published location. A vague place name or a postal box is not an address, so it is\n'
        '    still dropped rather than guessed.\n'
        '    """\n'
        '    if not isinstance(detail, dict):\n'
        '        return None\n'
        '    try:\n'
        '        lat = float(detail.get("latitude"))\n'
        '        lon = float(detail.get("longitude"))\n'
        '    except (TypeError, ValueError):\n'
        '        return None\n'
        '    street = " ".join((detail.get("streetAddress") or "").split())\n'
        '    low = street.lower()\n'
        '    if (not street or not re.search(r"\\d", street) or low in {"tampereen seutu", "tampere"}\n'
        '            or low.startswith("pl ") or not (61.0 < lat < 62.0 and 22.5 < lon < 25.0)):\n'
        '        return None\n'
        '    postal = " ".join((detail.get("postalCode") or "").split())\n'
        '    city = " ".join((detail.get("city") or "").split())\n'
        '    address = street + (", " + " ".join(p for p in (postal, city) if p) if postal or city else "")\n'
        '    existing = resolve_by_address(address, VENUES)\n'
        '    if existing and existing["id"] != "tampere_muu":\n'
        '        return existing\n'
        '    vid = "kide-" + hashlib.sha1(\n'
        '        f"{address.lower()}|{round(lat, 5)},{round(lon, 5)}".encode()).hexdigest()[:8]\n'
        '    for v in VENUES:\n'
        '        if v["id"] == vid:\n'
        '            return v\n'
        '    venue = {\n'
        '        "id": vid, "name": (ev.get("place") or place_name(street)).strip(),\n'
        '        "lat": lat, "lon": lon, "area": nearest_zone(lat, lon),\n'
        '        "kind": "student", "capacity": {"gig": 0},\n'
        '        "hubs": nearest_hubs(lat, lon), "approx": False, "address": address,\n'
        '        "source": "kide product location",\n'
        '    }\n'
        '    VENUES.append(venue)\n'
        '    return venue\n\n\n'
        'def venue_record(v):\n',
    ),
])


edit("web/config.js", [('  APP_VERSION: "0.13.2",', '  APP_VERSION: "0.13.3",')])
edit("README.md", [
    ('Live: https://zakker111.github.io/kilinkolin/ · **v0.13.2** · model **2026.11.5** · schema **2**',
     'Live: https://zakker111.github.io/kilinkolin/ · **v0.13.3** · model **2026.11.5** · schema **2**'),
    ('- Student: Kide\'s public Tampere product list. Kide publishes no coordinates, so a product is\n'
     '  placed only when its venue already exists in the registry; the rest are dropped and logged.',
     '- Student: Kide\'s public Tampere product list. Its list endpoint has no coordinates; when a place\n'
     '  does not match the registry, the product detail\'s published street address and point are used.\n'
     '  Entries with only a vague place or a postal box are dropped and logged, never guessed.'),
])
edit("NOTICE.md", [
    ('- Student events come from Kide\'s public Tampere product list. Kide publishes no coordinates,\n'
     '  so a product is placed only on a venue already in the registry; unplaceable products are\n'
     '  dropped and logged, never guessed.',
     '- Student events come from Kide\'s public Tampere product list. Its list endpoint has no coordinates;\n'
     '  unresolved products use the street address and point published on the product detail. Entries\n'
     '  with only a vague place or a postal box are dropped and logged, never guessed.'),
])
edit("TODO.md", [
    ('- [x] 0.13.2 address corrections: 28 venues moved to published street addresses and address\n'
     '      points, plus the generic fallback; 765 stale route legs dropped, the event-used legs in use\n'
     '      refetched, and the panel\'s venue-address line restored',
     '- [x] 0.13.2 address corrections: 28 venues moved to published street addresses and address\n'
     '      points, plus the generic fallback; 765 stale route legs dropped, the event-used legs in use\n'
     '      refetched, and the panel\'s venue-address line restored\n'
     '- [x] 0.13.3 student events: Kide product details now supply the published address and point when\n'
     '      the list\'s free-text place does not match; 15 more student events (47 → 62), six new\n'
     '      locations and their walking legs'),
    ('- **Student events are matched, not geocoded.** Kide gives a place name but no coordinates, so a\n'
     '  product is only published when its place is already a registry venue; today that is 47 of 67. The\n'
     '  rest are dropped and logged, never placed on a guessed address.',
     '- **Student events are matched, not geocoded.** Kide\'s list gives a place name but no coordinates;\n'
     '  unresolved products use the address and point published on the product detail. Today 62 of 64\n'
     '  future products are published. Two are still dropped and logged because they have no single\n'
     '  place: the VETO apartment tour (starts in Niemenranta, moves between homes) and Yrityspäivät\n'
     '  (a postal box, PL 54). Neither is placed on a guessed address.'),
])
edit("AGENTS.md", [
    ('`scripts/feeds/kide.py` is the student source and it publishes **no coordinates at all** — only a\n'
     'free-text place string. A product is placed only when that string matches a registry venue (name or\n'
     '`aliases`, whitespace-normalised, with the spellings Kide actually uses added as aliases); every\n'
     'other product is dropped and logged rather than pinned to a guessed point. The same event sold\n'
     'separately by four guilds is merged on (date, start, title).',
     '`scripts/feeds/kide.py` is the student source. Its product **list** carries a free-text place and\n'
     'no coordinates. A product is first matched to a registry venue (name or `aliases`, whitespace-\n'
     'normalised, with the spellings Kide actually uses added as aliases). If that fails, the public\n'
     'product detail can supply the organiser\'s published `streetAddress`, postal code and point; use it\n'
     'only when the street has a number and the point is in the Tampere region. Vague places\n'
     '(`Tampereen seutu`) and postal boxes (`PL 54`) are dropped and logged, never guessed. After\n'
     '`kide_rows` adds one of these generated venues, rebuild the alias index before resolving the\n'
     'student rows. The same event sold separately by four guilds is merged on (date, start, title).'),
])
edit("VERSIONS.md", [
    ('## App\n\n### 0.13.2 — 2026-11-15',
     '## App\n\n'
     '### 0.13.3 — 2026-11-15\n'
     'Student events completed from Kide\'s published product locations.\n\n'
     '- Fixed: 17 future Kide products were dropped because the list endpoint carries only a free-text\n'
     '  place and no coordinates. The public product detail publishes the organiser\'s street address and\n'
     '  point; 15 of them now have a real venue. Student events go from 47 to 62.\n'
     '- Added: Bommari (Korkeakoulunkatu 5), Vertex Oy (Vaajakatu 9), TTHP (Korkeakoulunkatu 3),\n'
     '  Staabi ry (Kalevantie 4), Tampereen Opiskelijapuolikas (Ratinan rantatie 1) and the Kide\n'
     '  location at Korkeakoulunkatu 7, each on its published address point; their walking legs are in\n'
     '  the route cache.\n'
     '- Still excluded, deliberately: the VETO apartment tour (starts in Niemenranta and moves between\n'
     '  homes, so no single address) and Yrityspäivät (a PL 54 postal box). Neither is guessed.\n'
     '- No model or schema change: model 2026.11.5, schema 2, 395 events.\n\n'
     '### 0.13.2 — 2026-11-15'),
])
print("0.13.3 source patch applied")
