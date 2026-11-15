import json
from pathlib import Path

IDS = {
    "tuomiokirkko", "rosendahl", "tammelan_stadion", "astor", "puisto_ravintola",
    "salhojankatu", "huurre", "myllarit", "terassi_ylakerta", "vastavirta",
    "hiedanranta", "city-c3fb3e5f", "kangasala_kirkko", "ylinen_kartano",
}
p = Path("registry/routes.json")
doc = json.loads(p.read_text(encoding="utf-8"))
before = len(doc["routes"])
doc["routes"] = {k: v for k, v in doc["routes"].items() if k.split("|", 1)[0] not in IDS}
p.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"dropped {before - len(doc['routes'])} older cached legs")

p = Path("VERSIONS.md"); s = p.read_text(encoding="utf-8")
needle = "- No model or schema change: model 2026.11.5, schema 2, 380 events.\n"
assert needle in s
s = s.replace(needle, "- Fixed: 14 venues corrected in earlier releases still had route-cache entries ending at\n  their old points; 257 event-used legs are refreshed as well.\n" + needle, 1)
p.write_text(s, encoding="utf-8")

p = Path("TODO.md"); s = p.read_text(encoding="utf-8")
old = "refetched, and the panel's venue-address line restored"
assert old in s
p.write_text(s.replace(old, old + "; 257 older stale legs refreshed", 1), encoding="utf-8")
print("older route refresh prepared")
