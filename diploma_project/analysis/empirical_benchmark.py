"""
Емпіричний бенчмарк v2: вимірює час самостійно (без /api/metrics).
Запускає N вузлів, відправляє файл, вимірює час відповіді та збирає
метрики з CSV-файлів, що автоматично записуються кожним вузлом.
"""
import subprocess, time, requests, os, json, csv, sys, signal
import statistics, glob
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import stats as sp_stats

CLUSTER_SIZES = [3, 5, 7, 10, 15]
REPETITIONS = 3
WAIT_DISCOVERY = 15
WAIT_AFTER_SEND = 8
BASE_PORT = 8080
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(PROJECT_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

TEST_FILE = os.path.join(PROJECT_DIR, "test_benchmark_file.bin")
if not os.path.exists(TEST_FILE):
    with open(TEST_FILE, "wb") as f:
        f.write(os.urandom(1024 * 1024))

def launch_cluster(n_nodes):
    procs = []
    for i in range(n_nodes):
        port = BASE_PORT + i
        node_id = f"bench_node{i+1}"
        proc = subprocess.Popen(
            [sys.executable, "app.py", node_id, str(port)],
            cwd=PROJECT_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0,
        )
        procs.append((proc, port, node_id))
    return procs

def kill_cluster(procs):
    for proc, _, _ in procs:
        try:
            if os.name == 'nt':
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                proc.terminate()
        except Exception:
            pass
    time.sleep(1)
    for proc, _, _ in procs:
        try: proc.kill()
        except: pass
    time.sleep(1)

def wait_for_cluster(procs, timeout=30):
    deadline = time.time() + timeout
    for proc, port, _ in procs:
        while time.time() < deadline:
            try:
                r = requests.get(f"http://localhost:{port}/api/status", timeout=2)
                if r.status_code == 200: break
            except: pass
            time.sleep(0.5)

def get_peers_count(port):
    try:
        r = requests.get(f"http://localhost:{port}/api/peers", timeout=3)
        return len(r.json())
    except: return 0

def send_and_measure(port):
    """Відправляє файл та вимірює повний час round-trip."""
    t0 = time.perf_counter()
    try:
        with open(TEST_FILE, "rb") as f:
            r = requests.post(
                f"http://localhost:{port}/api/send-file",
                files={"file": ("test_benchmark_file.bin", f)},
                timeout=60,
            )
        elapsed = (time.perf_counter() - t0) * 1000  # мс
        return r.status_code == 200, elapsed
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"  [!] Error: {e}")
        return False, elapsed

def collect_csv_metrics(node_id):
    """Збирає метрики з CSV-файлу вузла."""
    metrics = {}
    pattern = os.path.join(RESULTS_DIR, f"metrics_{node_id}.csv")
    files = glob.glob(pattern)
    if not files:
        return metrics
    with open(files[0], 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            metric = row['metric']
            if metric not in metrics:
                metrics[metric] = []
            metrics[metric].append(float(row['value']))
    return metrics

# Видаляємо старі bench_ метрики
for f in glob.glob(os.path.join(RESULTS_DIR, "metrics_bench_node*.csv")):
    os.remove(f)

# ── Бенчмарк ────────────────────────────────────────────────────────────────
print("=" * 80)
print(" EMPIRICAL SCALABILITY BENCHMARK v2")
print("=" * 80)

all_results = []

for n in CLUSTER_SIZES:
    print(f"\n{'='*60}")
    print(f" N = {n} nodes")
    print(f"{'='*60}")

    # Видалити старі bench-метрики перед тестом
    for f in glob.glob(os.path.join(RESULTS_DIR, "metrics_bench_node*.csv")):
        os.remove(f)

    procs = launch_cluster(n)
    wait_for_cluster(procs, timeout=30)
    print(f"  Waiting {WAIT_DISCOVERY}s for discovery...")
    time.sleep(WAIT_DISCOVERY)

    for _, port, nid in procs:
        pc = get_peers_count(port)
        print(f"    {nid}: {pc} peers")

    sender_port = procs[0][1]
    round_trips = []

    for rep in range(REPETITIONS):
        print(f"  Send #{rep+1}...", end=" ")
        ok, elapsed = send_and_measure(sender_port)
        if ok:
            round_trips.append(elapsed)
            print(f"[OK] {elapsed:.1f}ms")
        else:
            print(f"[FAIL] {elapsed:.1f}ms")
        time.sleep(WAIT_AFTER_SEND)

    # Зачекати щоб метрики записалися
    time.sleep(3)

    # Збираємо метрики з CSV
    sender_metrics = collect_csv_metrics("bench_node1")
    enc_vals = sender_metrics.get('encryption_time', [])
    bcast_vals = sender_metrics.get('broadcast_time', [])
    transfer_vals = sender_metrics.get('transfer_time', [])

    avg_enc = statistics.mean(enc_vals) * 1000 if enc_vals else 0
    avg_bcast = statistics.mean(bcast_vals) * 1000 if bcast_vals else 0
    avg_transfer = statistics.mean(transfer_vals) * 1000 if transfer_vals else 0
    avg_roundtrip = statistics.mean(round_trips) if round_trips else 0

    all_results.append({
        'n': n,
        'encryption_ms': avg_enc,
        'broadcast_ms': avg_bcast,
        'transfer_ms': avg_transfer,
        'roundtrip_ms': avg_roundtrip,
    })

    print(f"  => enc={avg_enc:.1f}ms  broadcast={avg_bcast:.1f}ms  roundtrip={avg_roundtrip:.1f}ms")

    kill_cluster(procs)
    time.sleep(3)

# ── CSV ──────────────────────────────────────────────────────────────────────
csv_path = os.path.join(RESULTS_DIR, "empirical_scalability.csv")
with open(csv_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=['n', 'encryption_ms', 'broadcast_ms', 'transfer_ms', 'roundtrip_ms'])
    w.writeheader()
    for r in all_results:
        w.writerow(r)
print(f"\nCSV saved: {csv_path}")

# ── Графіки ──────────────────────────────────────────────────────────────────
plt.rcParams.update({
    'font.family': 'DejaVu Sans',
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.grid': True, 'grid.alpha': 0.3, 'grid.linestyle': '--',
    'figure.dpi': 150,
})
BLUE='#2563eb'; GREEN='#16a34a'; ORANGE='#ea580c'; RED='#dc2626'; PURPLE='#7c3aed'

nodes_arr = np.array([r['n'] for r in all_results])
enc_arr   = np.array([r['encryption_ms'] for r in all_results])
bcast_arr = np.array([r['broadcast_ms'] for r in all_results])
rt_arr    = np.array([r['roundtrip_ms'] for r in all_results])
tx_arr    = np.array([r['transfer_ms'] for r in all_results])

# --- 1. Round-trip + Broadcast vs N ---
fig, ax = plt.subplots(figsize=(10, 5.5))
ax.plot(nodes_arr, rt_arr,    'o-', color=BLUE,   lw=2, ms=8, label='Round-trip (API -> peers -> done)')
ax.plot(nodes_arr, bcast_arr, 's-', color=GREEN,  lw=2, ms=8, label='Broadcast (P2P)')
ax.plot(nodes_arr, enc_arr,   '^-', color=ORANGE, lw=2, ms=8, label='Encryption (AES-GCM+RSA)')

if len(nodes_arr) >= 3 and np.any(rt_arr > 0):
    slope, intercept, r_val, *_ = sp_stats.linregress(nodes_arr, rt_arr)
    x_fit = np.linspace(nodes_arr[0], nodes_arr[-1], 100)
    ax.plot(x_fit, slope*x_fit + intercept, '--', color=RED, lw=1.5,
            label=f'Regression: T = {slope:.1f}*N + {intercept:.0f} (R2={r_val**2:.3f})')

ax.set_xlabel('Number of nodes N', fontsize=12)
ax.set_ylabel('Time, ms', fontsize=12)
ax.set_title('Empirical Testing: Operation Time vs Cluster Size', fontsize=13, fontweight='bold')
ax.legend(fontsize=9)
plt.tight_layout()
fig.savefig(os.path.join(RESULTS_DIR, 'empirical_scalability_time.png'), bbox_inches='tight')
plt.close()
print("Saved: empirical_scalability_time.png")

# --- 2. DES vs Empirical ---
fig, ax = plt.subplots(figsize=(10, 5.5))
des_consensus = 280 + 22.4 * nodes_arr
x = np.arange(len(nodes_arr)); width = 0.35

empirical_total = np.where(bcast_arr > 0, bcast_arr, rt_arr)
ax.bar(x - width/2, empirical_total, width, label='Empirical', color=GREEN, alpha=0.85)
ax.bar(x + width/2, des_consensus,    width, label='DES Model',  color=GREEN, alpha=0.3, edgecolor=GREEN, lw=2)

if np.any(empirical_total > 0) and np.any(des_consensus > 0):
    ratios = des_consensus / np.where(empirical_total > 0, empirical_total, 1)
    avg_ratio = np.mean(ratios[empirical_total > 0]) if np.any(empirical_total > 0) else 0
    ax.text(0.02, 0.95, f'DES/Empirical ratio: {avg_ratio:.1f}x',
            transform=ax.transAxes, fontsize=11, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

ax.set_xlabel('Number of nodes N', fontsize=12)
ax.set_ylabel('Time, ms', fontsize=12)
ax.set_title('DES Model vs Empirical Testing Comparison', fontsize=13, fontweight='bold')
ax.set_xticks(x); ax.set_xticklabels(nodes_arr)
ax.legend(fontsize=10)
plt.tight_layout()
fig.savefig(os.path.join(RESULTS_DIR, 'empirical_vs_des_comparison.png'), bbox_inches='tight')
plt.close()
print("Saved: empirical_vs_des_comparison.png")

# --- 3. Breakdown bar chart ---
fig, ax = plt.subplots(figsize=(10, 5.5))
x = np.arange(len(nodes_arr)); w = 0.25
ax.bar(x - w, enc_arr,  w, label='Encryption',  color=BLUE,   alpha=0.85)
ax.bar(x,     bcast_arr,w, label='Broadcast',    color=GREEN,  alpha=0.85)
ax.bar(x + w, tx_arr,   w, label='File Transfer',color=ORANGE, alpha=0.85)
ax.set_xlabel('Number of nodes N', fontsize=12)
ax.set_ylabel('Time, ms', fontsize=12)
ax.set_title('Empirical Testing: Time Breakdown by Operation Type', fontsize=13, fontweight='bold')
ax.set_xticks(x); ax.set_xticklabels(nodes_arr)
ax.legend(fontsize=10)
plt.tight_layout()
fig.savefig(os.path.join(RESULTS_DIR, 'empirical_breakdown.png'), bbox_inches='tight')
plt.close()
print("Saved: empirical_breakdown.png")

print(f"\n{'='*60}")
print(f" DONE! Graphs: {RESULTS_DIR}")
print(f"{'='*60}")
