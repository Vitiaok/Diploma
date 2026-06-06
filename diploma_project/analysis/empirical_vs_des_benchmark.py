"""
Емпіричний бенчмарк v3: збирає ТІ Ж метрики, що й DES-симуляція.

Метрики DES:
  - Crypto_CPU_ms        (час шифрування AES + RSA)
  - Consensus_Majority_ms (час досягнення більшості)
  - Full_Propagation_ms   (час повної розсилки / broadcast)
  - Sender_Bandwidth_MB   (пропускна здатність відправника)
  - Global_Storage_GB     (загальний обсяг зберігання)
  - Throughput_TPS        (транзакцій на секунду)

Запускає N вузлів локально (як app.py процеси), відправляє файли,
збирає метрики з CSV-файлів кожного вузла, і зводить результати
в таблицю, що порівнюється з DES.
"""
import subprocess, time, requests, os, json, csv, sys, signal
import statistics, glob
import socket

CLUSTER_SIZES = [3, 5, 7, 10]
WAIT_DISCOVERY = 5
REPETITIONS = 3
WAIT_AFTER_SEND = 10  # Legacy constant
BASE_PORT = 8080
FILE_SIZE_MB = 1.0  # 1 MB test file (same order as DES uses 5 MB)
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(PROJECT_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

TEST_FILE = os.path.join(PROJECT_DIR, "test_benchmark_file.bin")
if not os.path.exists(TEST_FILE):
    with open(TEST_FILE, "wb") as f:
        f.write(os.urandom(int(FILE_SIZE_MB * 1024 * 1024)))


def find_free_port(start_port):
    """Find a free port starting from start_port."""
    port = start_port
    while port < start_port + 200:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                port += 1
    return port


def launch_cluster(n_nodes):
    procs = []
    used_ports = []
    port = BASE_PORT
    for i in range(n_nodes):
        # Find an actually free port
        port = find_free_port(port)
        node_id = f"bench_node{i+1}"
        proc = subprocess.Popen(
            [sys.executable, "app.py", node_id, str(port)],
            cwd=PROJECT_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0,
        )
        procs.append((proc, port, node_id))
        used_ports.append(port)
        port += 1  # next search starts after this port
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
        try:
            proc.kill()
        except Exception:
            pass
    time.sleep(2)


def wait_for_cluster(procs, timeout=45):
    deadline = time.time() + timeout
    for proc, port, nid in procs:
        while time.time() < deadline:
            try:
                r = requests.get(f"http://localhost:{port}/api/status", timeout=2)
                if r.status_code == 200:
                    break
            except Exception:
                pass
            time.sleep(0.5)


def get_peers_count(port):
    try:
        r = requests.get(f"http://localhost:{port}/api/peers", timeout=3)
        return len(r.json())
    except Exception:
        return 0


def collect_api_metrics(port):
    """Collect metrics via the /api/metrics endpoint (Node's MetricsCollector).
    This gives us pow_time and consensus_time that the FileHandler doesn't track."""
    try:
        r = requests.get(f"http://localhost:{port}/api/metrics", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


def send_and_measure(port):
    """Send a file and measure full round-trip time."""
    t0 = time.perf_counter()
    try:
        with open(TEST_FILE, "rb") as f:
            r = requests.post(
                f"http://localhost:{port}/api/send-file",
                files={"file": ("test_benchmark_file.bin", f)},
                timeout=120,
            )
        elapsed = (time.perf_counter() - t0) * 1000  # ms
        return r.status_code == 200, elapsed
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"  [!] Error: {e}")
        return False, elapsed


def collect_csv_metrics(node_id):
    """Collect metrics from the node's CSV file."""
    metrics = {}
    pattern = os.path.join(RESULTS_DIR, f"metrics_{node_id}.csv")
    files = glob.glob(pattern)
    if not files:
        return metrics
    try:
        with open(files[0], 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                metric = row['metric']
                if metric not in metrics:
                    metrics[metric] = []
                metrics[metric].append(float(row['value']))
    except Exception:
        pass
    return metrics


def safe_mean(vals):
    """Return mean if list is non-empty, else 0."""
    return statistics.mean(vals) if vals else 0.0


# ── Clean old bench metrics ─────────────────────────────────────────────────
for f in glob.glob(os.path.join(RESULTS_DIR, "metrics_bench_node*.csv")):
    os.remove(f)

# ── Benchmark ────────────────────────────────────────────────────────────────
print("=" * 90)
print(" EMPIRICAL SCALABILITY BENCHMARK v3 (DES-compatible metrics)")
print("=" * 90)

all_results = []

for n in CLUSTER_SIZES:
    print(f"\n{'='*70}")
    print(f" N = {n} nodes")
    print(f"{'='*70}")

    # Delete old bench metrics before test
    for f in glob.glob(os.path.join(RESULTS_DIR, "metrics_bench_node*.csv")):
        os.remove(f)

    procs = launch_cluster(n)
    wait_for_cluster(procs, timeout=45)
    print(f"  Waiting {WAIT_DISCOVERY}s for peer discovery...")
    time.sleep(WAIT_DISCOVERY)

    # Print discovered peers
    for _, port, nid in procs:
        pc = get_peers_count(port)
        print(f"    {nid}: {pc} peers")

    sender_port = procs[0][1]
    round_trips = []
    successful_count = 0

    import concurrent.futures

    overall_t0 = time.perf_counter()

    print(f"  Sending {REPETITIONS} files concurrently (як у DES)...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=REPETITIONS) as executor:
        futures = [executor.submit(send_and_measure, sender_port) for _ in range(REPETITIONS)]
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            ok, elapsed = future.result()
            if ok:
                round_trips.append(elapsed)
                successful_count += 1
                print(f"    Task #{i+1} [OK] API accepted in {elapsed:.1f}ms")
            else:
                print(f"    Task #{i+1} [FAIL]")

    print(f"  Waiting for {successful_count} blocks to be mined (PoW/Consensus)...")
    mined_blocks = 0
    wait_start = time.time()
    while mined_blocks < successful_count and (time.time() - wait_start) < 30:
        api_m = collect_api_metrics(sender_port)
        mined_blocks = api_m.get('pow_time', {}).get('count', 0)
        time.sleep(1)

    overall_elapsed_s = time.perf_counter() - overall_t0
    print(f"  All blocks mined! True elapsed time: {overall_elapsed_s:.1f}s")
    
    time.sleep(2) # brief flush delay

    # ── Collect metrics from ALL nodes ────────────────────────────────────────
    all_enc_vals = []
    all_bcast_vals = []
    all_transfer_vals = []
    all_pow_vals = []
    all_consensus_vals = []
    all_decryption_vals = []

    # 1) Collect from CSV files (FileHandler's MetricsCollector)
    for _, _, nid in procs:
        m = collect_csv_metrics(nid)
        all_enc_vals.extend(m.get('encryption_time', []))
        all_bcast_vals.extend(m.get('broadcast_time', []))
        all_transfer_vals.extend(m.get('transfer_time', []))
        # CSV may also contain these if Node saved after FileHandler
        all_pow_vals.extend(m.get('pow_time', []))
        all_consensus_vals.extend(m.get('consensus_time', []))
        all_decryption_vals.extend(m.get('decryption_time', []))

    # 2) Collect from /api/metrics (Node's MetricsCollector — has pow_time, consensus_time)
    for _, port, nid in procs:
        api_m = collect_api_metrics(port)
        # The API returns {"node_id": ..., "pow_time": {"count": N, "mean": X, ...}, ...}
        if 'pow_time' in api_m and not all_pow_vals:
            # Use mean * count to reconstruct individual-like values
            count = api_m['pow_time'].get('count', 0)
            mean_val = api_m['pow_time'].get('mean', 0)
            if count > 0:
                all_pow_vals.extend([mean_val] * count)
        if 'consensus_time' in api_m and not all_consensus_vals:
            count = api_m['consensus_time'].get('count', 0)
            mean_val = api_m['consensus_time'].get('mean', 0)
            if count > 0:
                all_consensus_vals.extend([mean_val] * count)
        # Also try to get decryption_time if missing from CSV
        if 'decryption_time' in api_m and not all_decryption_vals:
            count = api_m['decryption_time'].get('count', 0)
            mean_val = api_m['decryption_time'].get('mean', 0)
            if count > 0:
                all_decryption_vals.extend([mean_val] * count)

    # Debug: print what we collected
    print(f"  Collected: enc={len(all_enc_vals)} bcast={len(all_bcast_vals)} "
          f"pow={len(all_pow_vals)} consensus={len(all_consensus_vals)} "
          f"decrypt={len(all_decryption_vals)}")

    # Convert seconds → milliseconds
    avg_enc_ms = safe_mean(all_enc_vals) * 1000
    avg_bcast_ms = safe_mean(all_bcast_vals) * 1000
    avg_transfer_ms = safe_mean(all_transfer_vals) * 1000
    avg_pow_ms = safe_mean(all_pow_vals) * 1000
    avg_consensus_ms = safe_mean(all_consensus_vals) * 1000
    avg_decryption_ms = safe_mean(all_decryption_vals) * 1000
    avg_roundtrip_ms = safe_mean(round_trips)

    # ── Compute DES-compatible metrics ────────────────────────────────────────

    # Crypto_CPU_ms: encryption (AES) + decryption
    crypto_cpu_ms = avg_enc_ms + avg_decryption_ms

    # Consensus_Majority_ms: from pow_time + consensus_time
    consensus_majority_ms = avg_pow_ms + avg_consensus_ms

    # Full_Propagation_ms: broadcast time (time to send to all peers)
    full_propagation_ms = avg_bcast_ms

    # Sender_Bandwidth_MB: total data sent = N_peers * file_size
    sender_bandwidth_mb = (n - 1) * FILE_SIZE_MB  # sender sends to N-1 peers

    # Global_Storage_GB: every node stores the file = N * file_size
    global_storage_gb = (n * FILE_SIZE_MB) / 1024.0

    # Throughput_TPS: successful file transfers per second
    throughput_tps = successful_count / overall_elapsed_s if overall_elapsed_s > 0 else 0

    result = {
        'Nodes_N': n,
        'Crypto_CPU_ms': round(crypto_cpu_ms, 2),
        'Consensus_Majority_ms': round(consensus_majority_ms, 2),
        'Full_Propagation_ms': round(full_propagation_ms, 2),
        'Sender_Bandwidth_MB': round(sender_bandwidth_mb, 2),
        'Global_Storage_GB': round(global_storage_gb, 4),
        'Throughput_TPS': round(throughput_tps, 4),
        # Extra detail (not in DES, but useful)
        'Avg_Encryption_ms': round(avg_enc_ms, 2),
        'Avg_PoW_ms': round(avg_pow_ms, 2),
        'Avg_Consensus_ms': round(avg_consensus_ms, 2),
        'Avg_Broadcast_ms': round(avg_bcast_ms, 2),
        'Avg_Roundtrip_ms': round(avg_roundtrip_ms, 2),
    }
    all_results.append(result)

    print(f"  => Crypto={crypto_cpu_ms:.1f}ms  Consensus={consensus_majority_ms:.1f}ms  "
          f"Propagation={full_propagation_ms:.1f}ms  TPS={throughput_tps:.4f}")

    kill_cluster(procs)
    time.sleep(3)

# ── Save CSV (DES-compatible columns) ────────────────────────────────────────
csv_path = os.path.join(RESULTS_DIR, "empirical_des_compatible.csv")
fieldnames = [
    'Nodes_N', 'Crypto_CPU_ms', 'Consensus_Majority_ms', 'Full_Propagation_ms',
    'Sender_Bandwidth_MB', 'Global_Storage_GB', 'Throughput_TPS',
    'Avg_Encryption_ms', 'Avg_PoW_ms', 'Avg_Consensus_ms',
    'Avg_Broadcast_ms', 'Avg_Roundtrip_ms',
]
with open(csv_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    for r in all_results:
        w.writerow(r)

print(f"\nCSV saved: {csv_path}")

# ── Print comparison table ───────────────────────────────────────────────────
print("\n" + "=" * 110)
print(" EMPIRICAL RESULTS (DES-compatible format)")
print("=" * 110)

header = (f"{'Nodes(N)':<10} | {'Crypto(ms)':<12} | {'Consensus(ms)':<14} | "
          f"{'Propagate(ms)':<14} | {'BW(MB)':<10} | {'Storage(GB)':<12} | {'TPS':<10}")
print(header)
print("-" * 110)

for r in all_results:
    print(f"{r['Nodes_N']:<10} | {r['Crypto_CPU_ms']:<12} | {r['Consensus_Majority_ms']:<14} | "
          f"{r['Full_Propagation_ms']:<14} | {r['Sender_Bandwidth_MB']:<10} | "
          f"{r['Global_Storage_GB']:<12} | {r['Throughput_TPS']:<10}")

# ── Load DES results if available ────────────────────────────────────────────
des_csv = os.path.join(RESULTS_DIR, "advanced_scalability.csv")
des_results = {}
if os.path.exists(des_csv):
    with open(des_csv, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            n_val = int(row['Nodes_N'])
            des_results[n_val] = row

if des_results:
    print("\n" + "=" * 130)
    print(" COMPARISON: EMPIRICAL vs DES SIMULATION")
    print("=" * 130)
    header = (f"{'Nodes':<8} | {'Crypto EMP':<12} | {'Crypto DES':<12} | "
              f"{'Consensus EMP':<14} | {'Consensus DES':<14} | "
              f"{'Propagate EMP':<14} | {'Propagate DES':<14} | "
              f"{'TPS EMP':<10} | {'TPS DES':<10}")
    print(header)
    print("-" * 130)

    for r in all_results:
        n = r['Nodes_N']
        if n in des_results:
            d = des_results[n]
            print(f"{n:<8} | {r['Crypto_CPU_ms']:<12} | {float(d['Crypto_CPU_ms']):<12.2f} | "
                  f"{r['Consensus_Majority_ms']:<14} | {float(d['Consensus_Majority_ms']):<14.2f} | "
                  f"{r['Full_Propagation_ms']:<14} | {float(d['Full_Propagation_ms']):<14.2f} | "
                  f"{r['Throughput_TPS']:<10} | {float(d['Throughput_TPS']):<10.4f}")
        else:
            print(f"{n:<8} | {r['Crypto_CPU_ms']:<12} | {'N/A':<12} | "
                  f"{r['Consensus_Majority_ms']:<14} | {'N/A':<14} | "
                  f"{r['Full_Propagation_ms']:<14} | {'N/A':<14} | "
                  f"{r['Throughput_TPS']:<10} | {'N/A':<10}")

print(f"\n{'='*70}")
print(f" DONE! Results: {csv_path}")
print(f"{'='*70}")
