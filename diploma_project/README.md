# 🔐 Decentralized Secure File Sharing on Private Blockchain

> **Bachelor's Thesis** — *Modelling and Scalability Analysis of a Decentralized Secure File Exchange System on a Private Blockchain*
> 
> Specialty: **F3 Computer Science** | Lviv National University named after Ivan Franko

---

## 📋 Overview

A fully decentralized P2P file-sharing system where every node discovers peers automatically, encrypts files end-to-end, and records every transfer immutably on a private blockchain — no central server, no single point of failure.

### Key Features

| Feature | Implementation |
|---|---|
| 🔍 Auto peer discovery | UDP Multicast + LAN HTTP scan |
| 🔒 File encryption | AES-256-GCM + RSA-2048 (hybrid) |
| ✍️ Digital signatures | RSA-PKCS1v15-SHA256 per block |
| ⛏️ Consensus | Proof-of-Work (5-zero hash target) |
| 🔄 Self-healing network | Heartbeat ping every 3 seconds |
| 📊 Scalability analysis | DES simulation up to 100,000 nodes |
| 🌐 Web UI | Real-time dashboard (Vanilla JS) |

---

## 🏗️ Architecture

```
diploma_project/
├── app.py                  # Flask REST API + Node startup
├── network/
│   ├── node.py             # Core P2P node (server + client)
│   ├── discovery.py        # UDP Multicast + TCP peer discovery
│   └── config.py           # Port assignment & peer registry
├── blockchain/
│   ├── block.py            # Block structure + SHA-256 hashing
│   ├── chain.py            # Chain management, PoW, consensus
│   └── keys.py             # RSA key generation & signing
├── security/
│   └── encryption.py       # AES-256-GCM + RSA-2048 hybrid
├── files/
│   └── handler.py          # Encrypted file transfer logic
├── analysis/
│   ├── des_simulation.py   # Discrete-Event Simulator (DES)
│   ├── traffic_simulator.py# Concurrent load testing tool
│   ├── logger.py           # Structured JSON event logger
│   └── metrics.py          # Performance metrics collector
├── frontend/
│   └── index.html          # Single-page dashboard UI
├── tests/
│   └── test_critical_path.py  # 9 mock unit tests
├── start_cluster.ps1       # Launch N nodes automatically
└── run_full_simulation.ps1 # Full cluster + traffic simulation
```

### How it works

```
[Node A]  →  generates AES key  →  encrypts file (AES-256-GCM)
          →  wraps AES key with RSA pubkey of each peer
          →  mines PoW hash (SHA-256, 5 zeros prefix)
          →  broadcasts block to all peers via TCP
          
[Node B]  →  verifies PoW hash
          →  verifies RSA digital signature
          →  unwraps AES key with own private key
          →  decrypts file  →  adds block to chain
```

---

## 🚀 Quick Start

### Prerequisites

```bash
pip install flask cryptography requests
```

### Run a Single Node

```bash
python app.py node1
# Opens web UI at http://localhost:5001
```

### Run a Local Cluster (PowerShell)

```powershell
# Start 5 nodes automatically
.\start_cluster.ps1 -count 5

# Or run full simulation: 5 nodes + traffic test
.\run_full_simulation.ps1 -nodes 5 -transfers 10 -filesizeKB 100
```

### Run with Docker

```bash
docker-compose up --scale node=5
```

### Manual multi-node setup

```bash
# Terminal 1
python app.py node1

# Terminal 2
python app.py node2

# Terminal 3
python app.py node3
```

Nodes discover each other automatically via UDP Multicast within seconds.

---

## 🌐 REST API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/status` | Node status, peers count, chain length |
| GET | `/api/peers` | List of active peers |
| GET | `/api/chain` | Full blockchain in JSON |
| POST | `/api/send_file` | Send encrypted file to peers |
| POST | `/api/validate_block` | Receive & validate block from peer |
| GET | `/api/metrics` | Performance metrics (CSV export) |

**Example — Send a file:**
```bash
curl -X POST http://localhost:5001/api/send_file \
  -F "file=@/path/to/secret.pdf"
```

**Example — Check status:**
```bash
curl http://localhost:5001/api/status
```

---

## 🔐 Security Model

```
Sender                          Receiver
  │                                 │
  │── generate k_session (AES-256) ─│
  │── encrypt file: C = AES-GCM(F, k_session)
  │── wrap key: w = RSA_ENCRYPT(pk_receiver, k_session)
  │────────── send (C, w, nonce, tag) ──────────▶│
  │                                 │
  │                                 │── k = RSA_DECRYPT(sk_self, w)
  │                                 │── F = AES_GCM_DECRYPT(C, k, nonce, tag)
```

- **Confidentiality**: AES-256-GCM ensures file content is unreadable without the session key
- **Key Security**: RSA-2048 ensures only the intended recipient can unwrap the AES key
- **Integrity**: GCM authentication tag detects any tampering with the ciphertext
- **Non-repudiation**: RSA-PKCS1v15-SHA256 signature on each block hash

---

## 📊 Scalability Analysis

The system includes a **Discrete-Event Simulator (DES)** for theoretical scalability analysis:

```bash
python analysis/des_simulation.py
```

**Results (5 MB file, averaged over 3 Monte Carlo runs):**

| Nodes (N) | Crypto (ms) | Consensus (ms) | Bandwidth (MB) | TPS |
|---|---|---|---|---|
| 5 | 30 | 292 | 25 | 9.69 |
| 100 | 220 | 2,429 | 500 | 1.22 |
| 1,000 | 2,020 | 22,542 | 5,000 | 0.13 |
| 10,000 | 20,020 | 224,144 | 50,000 | 0.01 |
| 100,000 | 200,020 | 2,241,525 | 500,000 | 0.001 |

> **Finding**: Broadcast architecture is O(N) — optimal for private networks up to ~500 nodes. For global scale, a Gossip protocol (O(log N)) would be needed.

---

## 🧪 Testing

Run the full test suite (9 critical path tests):

```bash
python -m unittest tests.test_critical_path
```

| Test | What it verifies |
|---|---|
| `test_blockchain_rejects_tampered_blocks` | Immutability — tampered file_hash is rejected |
| `test_proof_of_work_difficulty` | PoW produces correct hash prefix |
| `test_consensus_fork_resolution` | Longest chain rule resolves forks |
| `test_concurrency_race_condition` | RLock prevents data corruption under 10 parallel threads |
| `test_missing_block_sync_trigger` | Chain rejects blocks with missing predecessor |
| `test_aes_encryption_decryption_flow` | AES-256-GCM encrypts and decrypts without data loss |
| `test_rsa_signature_forgery` | Forged RSA signature is rejected |
| `test_node_handles_connection_refused` | Dead peers are auto-removed (Self-Healing) |
| `test_discovery_handles_malformed_udp_packets` | Malformed JSON packets don't crash discovery |

**Expected output:**
```
Ran 9 tests in ~9s
OK
```

---

## 🔬 Load Testing

```bash
# Run traffic simulator: 10 concurrent file transfers, 100KB each
python analysis/traffic_simulator.py 10 100

# Full automated simulation (PowerShell)
.\run_full_simulation.ps1 -nodes 7 -transfers 15 -filesizeKB 250
```

Results are saved to `results/advanced_scalability.csv`.

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Web Framework | Flask 3.x |
| Cryptography | cryptography (PyCA) — AES-256-GCM, RSA-2048 |
| Networking | socket (TCP/UDP), UDP Multicast |
| Frontend | HTML5, Vanilla JavaScript |
| Containerization | Docker, docker-compose |
| Testing | unittest, unittest.mock |
| Simulation | Custom DES (heapq-based event queue) |

---

## 📁 Key Files

| File | Purpose |
|---|---|
| `app.py` | Entry point — starts Flask + all background threads |
| `network/node.py` | Core P2P logic, heartbeat, peer management |
| `blockchain/chain.py` | PoW, block validation, fork resolution |
| `security/encryption.py` | AES-256-GCM + RSA-2048 hybrid encryption |
| `analysis/des_simulation.py` | DES scalability simulator (up to 100K nodes) |
| `tests/test_critical_path.py` | 9 critical-path mock tests |
| `start_cluster.ps1` | PowerShell cluster launcher |
| `run_full_simulation.ps1` | One-click simulation script |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 👤 Author

**Bachelor's Thesis** — Faculty of Electronics and Computer Technologies  
Lviv National University named after Ivan Franko, 2026
