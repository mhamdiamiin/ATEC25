# app/app.py
from flask import Flask, render_template, jsonify, request
import json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

# --- Paths ---
BASE = Path(__file__).resolve().parents[1]   # project root (.../tars9-sentinel)
OUT  = BASE / "out"

MODULES = ["AI_NAV", "AI_LIFE", "COMMS_U1", "COMMS_U2", "PROP_CTRL"]

app = Flask(__name__)

# ---------- Helpers ----------
def _to_dt(s: str):
    if not s:
        return None
    try:
        s = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return None

# ---------- Loaders ----------
def load_anomalies():
    with open(OUT / "anomalies.json", "r", encoding="utf-8") as f:
        return json.load(f)

def load_log():
    with open(OUT / "immutable_log.jsonl", "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]

# ---------- Pages ----------
@app.route("/")
def index():
    return render_template("index.html")

# ---------- Data APIs ----------
@app.route("/data/anomalies")
def data_anomalies():
    return jsonify(load_anomalies())

@app.route("/data/log")
def data_log():
    return jsonify(load_log())

@app.route("/data/metrics")
def data_metrics():
    anomalies = load_anomalies()
    total = len(anomalies)

    # True latest timestamp (max), not "last item in array"
    last_ts = None
    if anomalies:
        parsed = [_to_dt(a.get("timestamp", "")) for a in anomalies]
        parsed = [p for p in parsed if p is not None]
        if parsed:
            last_ts = max(parsed).astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    checksum_count = sum(1 for a in anomalies if a.get("checksum_err", 0))
    integrity = 100.0 if total == 0 else max(0.0, 100.0 * (1.0 - (checksum_count / total)))

    # recent window for severity
    per_recent = {m: 0 for m in MODULES}
    for a in anomalies[-20:]:
        m = a.get("module")
        if m in per_recent:
            per_recent[m] += 1
    critical = any(c >= 3 for c in per_recent.values())

    return jsonify({
        "total_anomalies": total,
        "last_anomaly": last_ts,
        "integrity": round(integrity, 1),
        "per_module_recent": per_recent,
        "critical": critical,
    })

# ---------- Admin: regenerate anomalies ----------
@app.route("/admin/regen", methods=["POST"])
def admin_regen():
    # Optional tiny shared-secret (uncomment to require ?key=YOURSECRET)
    # if request.args.get("key") != "YOURSECRET": return jsonify({"ok": False}), 403
    subprocess.run([sys.executable, str(BASE / "src" / "run.py")], check=True)
    return jsonify({"ok": True})

# ---------- Entrypoint ----------
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
