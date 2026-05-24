"""
Web API server for the blockchain file-sharing node.
Usage: python app.py <node_id> [web_port]
"""
import sys
import os

# Ensure the project root is in sys.path (needed for embedded/portable Python)
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import threading
import time
import json
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
        _node = Node(node_id)
        # Start all background threads — skip CLI user_interface()
        threading.Thread(target=NetworkConfig._discovery.start_discovery_server, args=(node_id,), daemon=True).start()
        threading.Thread(target=_node.start_server,                daemon=True).start()
        threading.Thread(target=_node.multicast_listen,            daemon=True).start()
        threading.Thread(target=_node.periodic_multicast_announce, daemon=True).start()
        _node.start_periodic_sync()
        _node.start_periodic_ping()
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
    pub_key = None
    key_path = f"public_key_{_node.node_id}.pem"
    if os.path.exists(key_path):
        with open(key_path, 'r') as f:
            pub_key = f.read()

    return jsonify({
        "status":       "running",
        "node_id":      _node.node_id,
        "host":         _node.host,
        "port":         _node.port,
        "peers_count":  len(_node.peers),
        "chain_length": len(_node.chain.blockchain),
        "running":      _node.running,
        "public_key":   pub_key
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
    result = []
    for h, p in _node.peers:
        node_id = NetworkConfig.get_node_id_by_transfer_addr(h, p)
        display_id = node_id if node_id else "Unknown Node"
        result.append({"host": h, "port": p, "node_id": display_id})
    return jsonify(result)


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
    
    targets = None
    if "targets" in request.form:
        try:
            targets = json.loads(request.form["targets"])
            print(f"DEBUG: Received targets from UI: {targets}")
        except Exception as e:
            print(f"DEBUG: Failed to parse targets: {e}")
            pass
    else:
        print("DEBUG: No targets specified in request.form, defaulting to broadcast")

    def _send():
        _node.file_handler.send_file(tmp_path, targets=targets)
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True).start()
    return jsonify({"success": True, "filename": filename})


@app.route("/api/download/<filename>")
def api_download_file(filename):
    secure_name = secure_filename(filename)
    storage_dir = os.path.abspath("node_files")
    return send_from_directory(storage_dir, secure_name, as_attachment=True)


# ── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import socket

    if len(sys.argv) < 2:
        # Auto-detect free port and name
        web_port = 8080
        instance = 1
        while web_port < 8200:  # Matches our HTTP port scan limit
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("0.0.0.0", web_port))
                    break
                except OSError:
                    web_port += 1
                    instance += 1
        
        hostname = socket.gethostname().lower()
        # Clean hostname to alphanumeric only
        hostname = "".join(c for c in hostname if c.isalnum())
        node_id = f"{hostname}_node{instance}"
        print(f"\n[AUTO] No arguments provided. Auto-starting node...")
        print(f"[AUTO] Detected free port: {web_port}")
        print(f"[AUTO] Generated unique node name: '{node_id}'\n")
    else:
        node_id  = sys.argv[1]
        web_port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080

    print(f"Starting node '{node_id}' -> http://localhost:{web_port}")
    
    # Auto-open browser in a separate thread once server starts
    def _open_browser():
        time.sleep(1.5)
        import webbrowser
        try:
            webbrowser.open(f"http://localhost:{web_port}")
        except Exception:
            pass
            
    threading.Thread(target=_open_browser, daemon=True).start()
    threading.Thread(target=_start_node, args=(node_id,), daemon=True).start()
    app.run(host="0.0.0.0", port=web_port, debug=False, use_reloader=False)
