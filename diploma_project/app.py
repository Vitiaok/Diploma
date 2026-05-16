"""
Web API server for the blockchain file-sharing node.
Usage: python app.py <node_id> [web_port]
"""
import sys
import os
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from network.config import NetworkConfig
from network.node import Node

UPLOAD_TMP = "tmp_uploads"
os.makedirs(UPLOAD_TMP, exist_ok=True)
os.makedirs("node_files", exist_ok=True)

app = Flask(__name__, static_folder="frontend", static_url_path="")
_node: Node = None


# ── Node startup ────────────────────────────────────────────────────────────

def _start_node(node_id: str):
    global _node
    try:
        NetworkConfig.initialize(node_id)
        time.sleep(1)
        _node = Node(node_id)
        # Start all background threads — skip CLI user_interface()
        threading.Thread(target=_node.start_server,                daemon=True).start()
        threading.Thread(target=_node.multicast_listen,            daemon=True).start()
        threading.Thread(target=_node.periodic_multicast_announce, daemon=True).start()
        _node.start_periodic_sync()
        print(f"[NODE] '{node_id}' ready on {_node.host}:{_node.port}")
    except Exception as e:
        print(f"[NODE ERROR] {e}")


# ── Static frontend ─────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")


# ── REST API ────────────────────────────────────────────────────────────────

@app.route("/api/status")
def api_status():
    if _node is None:
        return jsonify({"status": "starting"})
    return jsonify({
        "status":       "running",
        "node_id":      _node.node_id,
        "host":         _node.host,
        "port":         _node.port,
        "peers_count":  len(_node.peers),
        "chain_length": len(_node.chain.blockchain),
        "running":      _node.running,
    })


@app.route("/api/chain")
def api_chain():
    if _node is None:
        return jsonify([])
    return jsonify([b.dict for b in _node.chain.get_chain()])


@app.route("/api/peers")
def api_peers():
    if _node is None:
        return jsonify([])
    return jsonify([{"host": h, "port": p} for h, p in _node.peers])


@app.route("/api/metrics")
def api_metrics():
    if _node is None:
        return jsonify({})
    return jsonify(_node.metrics.get_summary())


@app.route("/api/files")
def api_files():
    storage = Path("node_files")
    files = []
    if storage.exists():
        for f in storage.iterdir():
            if f.is_file() and not f.name.endswith(".tmp"):
                files.append({
                    "name":     f.name,
                    "size":     f.stat().st_size,
                    "modified": f.stat().st_mtime,
                })
    return jsonify(sorted(files, key=lambda x: x["modified"], reverse=True))


@app.route("/api/send-file", methods=["POST"])
def api_send_file():
    if _node is None:
        return jsonify({"success": False, "error": "Node not ready"}), 503
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400

    f = request.files["file"]
    filename = secure_filename(f.filename)
    tmp_path = os.path.join(UPLOAD_TMP, filename)
    f.save(tmp_path)

    def _send():
        _node.file_handler.send_file(tmp_path)
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True).start()
    return jsonify({"success": True, "filename": filename})


# ── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python app.py <node_id> [web_port]")
        sys.exit(1)

    node_id  = sys.argv[1]
    web_port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080

    print(f"Starting node '{node_id}' -> http://localhost:{web_port}")
    threading.Thread(target=_start_node, args=(node_id,), daemon=True).start()
    app.run(host="0.0.0.0", port=web_port, debug=False, use_reloader=False)
