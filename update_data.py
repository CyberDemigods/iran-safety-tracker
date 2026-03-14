#!/usr/bin/env python3
"""
Downloads all MahsaAlert GeoJSON layers and combines them into a single data.json
for the Iran Safety Tracker. Run periodically to keep data fresh.

Usage: python3 update_data.py
"""

import json
import urllib.request
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "data.json")
LAYERS_API = "https://api.mahsaalert.app/api/v1/layers"

# Known GeoJSON URLs as fallback
KNOWN_URLS = {
    1:  ("basij",    "https://mahsaalert.hel1.your-objectstorage.com/prod/sources/layers/1/basij.geojson"),
    3:  ("police",   "https://mahsaalert.hel1.your-objectstorage.com/prod/sources/layers/3/marakez-entezami.geojson"),
    5:  ("prison",   "https://mahsaalert.hel1.your-objectstorage.com/prod/sources/layers/5/prison.geojson"),
    6:  ("nuclear",  "https://mahsaalert.hel1.your-objectstorage.com/prod/sources/layers/6/nuclear-program.geojson"),
    7:  ("missile",  "https://mahsaalert.hel1.your-objectstorage.com/prod/sources/layers/7/missile-program.geojson"),
    9:  ("radar",    "https://mahsaalert.hel1.your-objectstorage.com/prod/sources/layers/9/radar.geojson"),
    10: ("airfield", "https://mahsaalert.hel1.your-objectstorage.com/prod/sources/layers/10/areoway.geojson"),
    11: ("military", "https://mahsaalert.hel1.your-objectstorage.com/prod/sources/layers/11/military-base.geojson"),
    12: ("military_unconfirmed", "https://mahsaalert.hel1.your-objectstorage.com/prod/sources/layers/12/unknown-military.geojson"),
    32: ("strike",   "https://mahsaalert.hel1.your-objectstorage.com/prod/sources/layers/32/targets-26-02.geojson"),
}

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "IranSafetyTracker/1.0"})
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read().decode("utf-8"))


def main():
    print(f"[{datetime.now().isoformat()}] Updating data.json...")

    # Use direct storage URLs (API often returns stale/empty versions)
    layer_urls = {}
    for lid, (_, url) in KNOWN_URLS.items():
        layer_urls[lid] = url
    print(f"  Using {len(layer_urls)} known layer URLs")

    strikes = []
    targets = []

    for lid, url in sorted(layer_urls.items()):
        type_name = KNOWN_URLS.get(lid, ("unknown",))[0]
        try:
            geojson = fetch_json(url)
            features = geojson.get("features", [])
            count = 0

            for feat in features:
                geom = feat.get("geometry", {})
                geom_type = geom.get("type", "")
                coords = geom.get("coordinates", [])

                if geom_type == "Point" and len(coords) >= 2:
                    lon, lat = coords[0], coords[1]
                elif geom_type == "Polygon" and coords:
                    # Centroid of first ring
                    ring = coords[0]
                    if not ring:
                        continue
                    lon = sum(c[0] for c in ring) / len(ring)
                    lat = sum(c[1] for c in ring) / len(ring)
                elif geom_type == "MultiPolygon" and coords:
                    ring = coords[0][0] if coords[0] else []
                    if not ring:
                        continue
                    lon = sum(c[0] for c in ring) / len(ring)
                    lat = sum(c[1] for c in ring) / len(ring)
                else:
                    continue
                props = feat.get("properties", {})

                item = {
                    "lat": round(lat, 5),
                    "lon": round(lon, 5),
                    "name": props.get("name:fa") or props.get("name") or "Unknown",
                    "type": type_name,
                    "status": props.get("status", ""),
                    "accurate": props.get("accurate", "no"),
                    "sources": props.get("sources", ""),
                    "mahsaId": props.get("id", ""),
                }

                if lid == 32:
                    ts = props.get("date")
                    if ts:
                        try:
                            unix = int(str(ts).split("-")[0]) if "-" in str(ts) else int(ts)
                            d = datetime.fromtimestamp(unix)
                            item["date"] = d.strftime("%Y-%m-%d")
                            item["time"] = d.strftime("%H:%M")
                        except (ValueError, OSError):
                            item["date"] = ""
                            item["time"] = ""
                    else:
                        item["date"] = ""
                        item["time"] = ""
                    strikes.append(item)
                else:
                    targets.append(item)
                count += 1

            print(f"  Layer {lid:>2} ({type_name:>20}): {count} points")
        except Exception as e:
            print(f"  Layer {lid:>2} ({type_name:>20}): FAILED - {e}")

    output = {
        "updated": datetime.now().isoformat(),
        "strikes": strikes,
        "targets": targets,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    size_kb = os.path.getsize(OUTPUT_FILE) / 1024
    print(f"\nDone: {len(strikes)} strikes, {len(targets)} targets -> data.json ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
