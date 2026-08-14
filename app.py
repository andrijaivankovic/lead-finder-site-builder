import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

import lead_search
import lead_store

app = Flask(__name__)


def _safe_file(name):
    if not name:
        return None
    candidate = (lead_store.data_dir(ROOT) / name).resolve()
    if candidate.parent != lead_store.data_dir(ROOT).resolve():
        return None
    if not candidate.name.startswith("leads_") or candidate.suffix != ".csv":
        return None
    if not candidate.exists():
        return None
    return candidate


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/usage")
def usage():
    summary = lead_search.usage_summary()
    summary["has_google_key"] = bool(lead_search.google_key())
    return jsonify(summary)


@app.get("/api/files")
def files():
    return jsonify({"files": lead_store.list_files(ROOT)})


@app.get("/api/leads")
def leads():
    path = _safe_file(request.args.get("file"))
    if not path:
        return jsonify({"error": "Unknown file."}), 404
    return jsonify({"file": path.name, "rows": lead_store.load_rows(path)})


@app.post("/api/search")
def search():
    payload = request.get_json(silent=True) or {}
    query = (payload.get("query") or "").strip()
    limit = payload.get("limit") or None

    if not query:
        return jsonify({"error": "Enter a search first."}), 400

    try:
        result = lead_search.run_search(query, limit=int(limit) if limit else None)
    except lead_search.SearchError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        return jsonify({"error": "Unexpected failure: {}".format(error)}), 500

    if not result["leads"]:
        return jsonify({"error": "No results. Try a different term or place."}), 404

    return jsonify(
        {
            "file": result["path"].name,
            "source": result["source"],
            "found": len(result["leads"]),
            "without_website": result["without_website"],
            "merged_with": result.get("previous"),
            "calls": result.get("calls", 0),
        }
    )


@app.post("/api/status")
def status():
    payload = request.get_json(silent=True) or {}
    path = _safe_file(payload.get("file"))
    place_id = payload.get("place_id")
    new_status = payload.get("status", "")

    if not path or not place_id:
        return jsonify({"error": "Unknown file or business."}), 404
    if new_status not in lead_store.STATUSES:
        return jsonify({"error": "Unknown status."}), 400

    if not lead_store.update_status(path, place_id, new_status):
        return jsonify({"error": "Business not found in this file."}), 404

    return jsonify({"saved": True})


@app.get("/api/export")
def export():
    path = _safe_file(request.args.get("file"))
    if not path:
        return jsonify({"error": "Unknown file."}), 404
    return send_file(path, as_attachment=True, download_name=path.name)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
