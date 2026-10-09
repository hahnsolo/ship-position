"""
Checks where a ship is, once, and saves it to position.json.

Connects to the aisstream.io live AIS feed, waits for the ship's next
position report (ships underway report every few seconds, moored ships
every few minutes), then disconnects. If nothing arrives in time, the last
known position is kept and marked as not fresh.

Settings come from environment variables:
  AISSTREAM_API_KEY   your aisstream.io key (required)
  SHIP_MMSI           the ship's 9-digit MMSI (default: CSL Laurentien)
  WAIT_SECONDS        how long to wait for a report (default: 240)
"""
import asyncio, json, os, sys
from datetime import datetime, timezone

import websockets

FEED = os.environ.get("AISSTREAM_URL", "wss://stream.aisstream.io/v0/stream")
API_KEY = os.environ.get("AISSTREAM_API_KEY", "")
MMSI = os.environ.get("SHIP_MMSI", "316001637")
WAIT = int(os.environ.get("WAIT_SECONDS", "240"))
OUT = os.environ.get("OUTPUT_FILE", "position.json")

NAV_STATUS = {
    0: "Underway", 1: "At anchor", 2: "Not under command", 3: "Restricted manoeuvrability",
    4: "Constrained by draught", 5: "Moored", 6: "Aground", 7: "Fishing", 8: "Sailing",
}


def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_previous():
    try:
        with open(OUT) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def clean_time(t):
    # aisstream gives "2026-10-09 13:30:12.345678 +0000 UTC"
    if not t:
        return now_utc()
    try:
        return datetime.strptime(t[:19], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return now_utc()


async def listen():
    """Returns (position dict or None, static dict or None)."""
    sub = {
        "APIKey": API_KEY,
        "BoundingBoxes": [[[-90, -180], [90, 180]]],
        "FiltersShipMMSI": [MMSI],
        "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
    }
    position, static = None, None
    received = 0
    loop = asyncio.get_running_loop()
    deadline = loop.time() + WAIT
    async with websockets.connect(FEED, open_timeout=30) as ws:
        await ws.send(json.dumps(sub))
        while loop.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=max(1, deadline - loop.time()))
            except asyncio.TimeoutError:
                break
            except websockets.ConnectionClosed:
                if received == 0:
                    raise RuntimeError("aisstream: connection closed before any data (check the API key)")
                break
            received += 1
            msg = json.loads(raw)
            if "error" in msg:
                raise RuntimeError("aisstream: " + str(msg["error"]))
            kind = msg.get("MessageType")
            meta = msg.get("MetaData", {})
            body = msg.get("Message", {}).get(kind, {})
            if kind == "PositionReport":
                lat, lon = body.get("Latitude"), body.get("Longitude")
                if lat is None or lon is None or abs(lat) > 90 or abs(lon) > 180:
                    continue  # 91/181 mean "not available"
                heading = body.get("TrueHeading")
                position = {
                    "name": (meta.get("ShipName") or "").strip(),
                    "lat": round(lat, 5),
                    "lon": round(lon, 5),
                    "sog": round(body.get("Sog") or 0, 1),
                    "cog": round(body.get("Cog") or 0, 1),
                    "heading": None if heading in (None, 511) else heading,
                    "status": NAV_STATUS.get(body.get("NavigationalStatus"), "Underway"),
                    "reportedUtc": clean_time(meta.get("time_utc")),
                }
            elif kind == "ShipStaticData":
                dest = (body.get("Destination") or "").strip().strip("@").strip()
                static = {"destination": dest.title() if dest else ""}
            if position and static:
                break
    return position, static


def main():
    if not API_KEY:
        sys.exit("Set AISSTREAM_API_KEY")
    prev = load_previous()
    problem = None
    try:
        position, static = asyncio.run(listen())
    except Exception as e:  # keep the last known position on any failure
        problem = str(e)
        print("Feed problem:", problem, file=sys.stderr)
        position, static = None, None

    out = dict(prev)
    out["mmsi"] = MMSI
    out["checkedUtc"] = now_utc()
    if position:
        out.update(position)
        out["fresh"] = True
    else:
        out["fresh"] = False
    if static and static["destination"]:
        out["destination"] = static["destination"]
    out.setdefault("name", "CSL LAURENTIEN")

    with open(OUT, "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))
    if problem and problem.startswith("aisstream:"):
        sys.exit(1)  # e.g. a bad API key: fail the run so it shows up red in Actions


if __name__ == "__main__":
    main()
