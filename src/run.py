# src/run.py
import csv
import json
import hashlib
import random
import statistics as stats
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------- Paths ----------
BASE = Path(__file__).resolve().parents[1]   # project root (.../tars9-sentinel)
DATA = BASE / "data"
OUT  = BASE / "out"
DATA.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

# ---------- Telemetry synthesis ----------
random.seed()  # different each run
start = datetime.now(timezone.utc) - timedelta(minutes=5)  # fresh, recent timestamps
modules = ["AI_NAV", "AI_LIFE", "COMMS_U1", "COMMS_U2", "PROP_CTRL"]
cmd_types = ["MAINT", "NAV_ADJ", "HEALTH", "SYNC", "IDLE"]

def iso_z(dt: datetime) -> str:
    # RFC3339-ish ISO with trailing 'Z'
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def gen_row(t: datetime, module: str, anomaly: bool = False):
    latency = max(5, random.gauss(120, 25))
    packet_loss = max(0.0, random.gauss(0.01, 0.006))
    checksum_err = 0
    expected = 1.0
    observed = expected + random.gauss(0, 0.03)
    life_support_ok = 1

    if anomaly and module in ("COMMS_U1", "COMMS_U2", "AI_LIFE"):
        if module.startswith("COMMS"):
            latency *= random.uniform(2.0, 3.2)
            packet_loss += random.uniform(0.05, 0.12)
            checksum_err = 1
        if module == "AI_LIFE":
            observed = expected + random.uniform(0.3, 0.55)
            life_support_ok = 0 if random.random() < 0.25 else 1

    return {
        "timestamp": iso_z(t),
        "module": module,
        "cmd_type": random.choice(cmd_types),
        "expected": round(expected, 3),
        "observed": round(observed, 3),
        "latency_ms": round(latency, 1),
        "packet_loss": round(packet_loss, 3),
        "checksum_err": checksum_err,
        "life_support_ok": life_support_ok,
    }

# Create ~6 minutes of per-second telemetry across modules
rows = []
t = start
for i in range(360):
    m = random.choice(modules)
    anomaly = (i > 120) and (random.random() < 0.22)  # more anomalies later
    rows.append(gen_row(t, m, anomaly))
    t += timedelta(seconds=1)

# Optional CSV (handy for debugging / later use)
csv_path = DATA / "telemetry_sample.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

# ---------- Detection ----------
def z(val, mean, sd): 
    return 0.0 if sd == 0 else (val - mean) / sd

def detect(rows):
    by_mod = {}
    for r in rows:
        by_mod.setdefault(r["module"], []).append(r["latency_ms"])
    baselines = {m: (stats.mean(v), stats.pstdev(v)) for m, v in by_mod.items()}

    alerts = []
    for r in rows:
        mu, sd = baselines[r["module"]]
        flags = []
        if r["checksum_err"] > 0: flags.append("CHECKSUM_ERR")
        if r["packet_loss"] > 0.05: flags.append("HIGH_PACKET_LOSS")
        if abs(r["observed"] - r["expected"]) > 0.25: flags.append("AI_BEHAVIOR_DRIFT")
        if r["life_support_ok"] == 0: flags.append("LIFE_SUPPORT_RISK")
        if z(r["latency_ms"], mu, sd) > 3: flags.append("LATENCY_OUTLIER")
        if flags:
            alerts.append({
                "timestamp": r["timestamp"],
                "module": r["module"],
                "flags": flags,
                "latency_ms": r["latency_ms"],
                "packet_loss": r["packet_loss"],
                "checksum_err": r["checksum_err"],
                "observed_minus_expected": round(r["observed"] - r["expected"], 3),
            })
    return alerts, baselines

alerts, baselines = detect(rows)

with open(OUT / "anomalies.json", "w", encoding="utf-8") as f:
    json.dump(alerts, f, indent=2)

# ---------- Immutable log (hash chain) ----------
def hash_record(prev_hash: str, payload: dict) -> str:
    body = json.dumps(payload, sort_keys=True)
    return hashlib.sha256((prev_hash + body).encode()).hexdigest()

def write_log(entries, path: Path):
    prev = "GENESIS"
    with open(path, "w", encoding="utf-8") as f:
        for e in entries:
            h = hash_record(prev, e)
            f.write(json.dumps({"prev": prev, "hash": h, "payload": e}) + "\n")
            prev = h

nowz = iso_z(datetime.now(timezone.utc))
entries = [
    {"event": "BOOT", "time": nowz},
    {"event": "BASELINE_COMPUTED", "baselines": baselines, "time": nowz},
]

for a in alerts[-25:]:
    resp = []
    if "CHECKSUM_ERR" in a["flags"] or "HIGH_PACKET_LOSS" in a["flags"]:
        resp += ["ISOLATE_COMMS_CHANNEL", "SWITCH_TO_REDUNDANT_LINK"]
    if "AI_BEHAVIOR_DRIFT" in a["flags"]:
        resp += ["QUARANTINE_AI_SUBMODULE"]
    if "LIFE_SUPPORT_RISK" in a["flags"]:
        resp += ["ENGAGE_CREW_SAFETY_LOCK"]
    entries.append({
        "event": "ALERT",
        "time": a["timestamp"],
        "module": a["module"],
        "flags": a["flags"],
        "response": resp,
    })

entries.append({"event": "END", "time": iso_z(datetime.now(timezone.utc))})
write_log(entries, OUT / "immutable_log.jsonl")
