"""
Аналіз масштабованості децентралізованої системи захищеного файлообміну.

Запускає серію симуляцій та будує графіки:
  1. Пропускна здатність vs кількість вузлів
  2. Час консенсусу vs кількість вузлів
  3. Вплив затримки мережі
  4. Вплив розміру файлу
"""
import time
import csv
import json
import os
import statistics
from typing import List

from analysis.simulation import NetworkSimulator

RESULTS_DIR = "results"
PLOTS_DIR = os.path.join(RESULTS_DIR, "plots")

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    print("[WARNING] matplotlib не встановлено. pip install matplotlib")


# ──────────────────────────────────────────────────────────────────────────────
#  Допоміжні функції
# ──────────────────────────────────────────────────────────────────────────────

def _ensure_dirs():
    os.makedirs(PLOTS_DIR, exist_ok=True)


def _save_csv(rows: List[dict], filename: str):
    path = os.path.join(RESULTS_DIR, filename)
    if not rows:
        return path
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"  [CSV] збережено: {path}")
    return path


def _agg(transfers: List[dict], key: str) -> float:
    vals = [t[key] for t in transfers if t.get("success")]
    return statistics.mean(vals) if vals else 0.0


# ──────────────────────────────────────────────────────────────────────────────
#  Тести
# ──────────────────────────────────────────────────────────────────────────────

def test_throughput_vs_nodes(
    node_counts: List[int] = None,
    num_transfers: int = 5,
    file_size: int = 10 * 1024,
    latency_ms: float = 0.0,
) -> List[dict]:
    if node_counts is None:
        node_counts = [2, 3, 5, 7, 10]
    print("\n[TEST] Throughput vs кількість вузлів")
    rows = []
    for n in node_counts:
        print(f"  → {n} вузлів ...", end=" ", flush=True)
        sim = NetworkSimulator(num_nodes=n, latency_ms=latency_ms)
        t0 = time.perf_counter()
        transfers = sim.run_benchmark(num_transfers, file_size)
        elapsed = time.perf_counter() - t0
        ok = [t for t in transfers if t["success"]]
        tps = len(ok) / elapsed if elapsed > 0 else 0
        row = {
            "num_nodes":           n,
            "num_transfers":       num_transfers,
            "successful":          len(ok),
            "throughput_tps":      round(tps, 4),
            "avg_total_time_s":    round(_agg(ok, "total_time"), 4),
            "avg_pow_time_s":      round(_agg(ok, "pow_time"), 4),
            "avg_consensus_time_s":round(_agg(ok, "consensus_time"), 4),
            "avg_encrypt_time_s":  round(_agg(ok, "encryption_time"), 6),
            "file_size_bytes":     file_size,
            "latency_ms":          latency_ms,
        }
        rows.append(row)
        print(f"TPS={tps:.4f}  avg_time={row['avg_total_time_s']:.3f}s")
    _save_csv(rows, "scalability_throughput.csv")
    return rows


def test_latency_impact(
    latencies_ms: List[float] = None,
    num_nodes: int = 5,
    num_transfers: int = 5,
    file_size: int = 10 * 1024,
) -> List[dict]:
    if latencies_ms is None:
        latencies_ms = [0, 10, 50, 100, 200, 500]
    print("\n[TEST] Вплив затримки мережі")
    rows = []
    for lat in latencies_ms:
        print(f"  → latency={lat}ms ...", end=" ", flush=True)
        sim = NetworkSimulator(num_nodes=num_nodes, latency_ms=lat)
        transfers = sim.run_benchmark(num_transfers, file_size)
        ok = [t for t in transfers if t["success"]]
        row = {
            "latency_ms":           lat,
            "num_nodes":            num_nodes,
            "successful":           len(ok),
            "avg_consensus_time_s": round(_agg(ok, "consensus_time"), 4),
            "avg_transfer_time_s":  round(_agg(ok, "transfer_time"), 4),
            "avg_total_time_s":     round(_agg(ok, "total_time"), 4),
        }
        rows.append(row)
        print(f"consensus={row['avg_consensus_time_s']:.3f}s  total={row['avg_total_time_s']:.3f}s")
    _save_csv(rows, "scalability_latency.csv")
    return rows


def test_file_size_impact(
    file_sizes: List[int] = None,
    num_nodes: int = 3,
    num_transfers: int = 3,
) -> List[dict]:
    if file_sizes is None:
        file_sizes = [1024, 10*1024, 50*1024, 100*1024, 512*1024]
    print("\n[TEST] Вплив розміру файлу")
    rows = []
    for size in file_sizes:
        label = f"{size//1024}KB" if size >= 1024 else f"{size}B"
        print(f"  → {label} ...", end=" ", flush=True)
        sim = NetworkSimulator(num_nodes=num_nodes, latency_ms=0)
        transfers = sim.run_benchmark(num_transfers, size)
        ok = [t for t in transfers if t["success"]]
        row = {
            "file_size_bytes":      size,
            "file_size_kb":         round(size / 1024, 2),
            "successful":           len(ok),
            "avg_encrypt_time_s":   round(_agg(ok, "encryption_time"), 6),
            "avg_pow_time_s":       round(_agg(ok, "pow_time"), 4),
            "avg_consensus_time_s": round(_agg(ok, "consensus_time"), 4),
            "avg_total_time_s":     round(_agg(ok, "total_time"), 4),
        }
        rows.append(row)
        print(f"encrypt={row['avg_encrypt_time_s']:.5f}s  total={row['avg_total_time_s']:.3f}s")
    _save_csv(rows, "scalability_filesize.csv")
    return rows


# ──────────────────────────────────────────────────────────────────────────────
#  Побудова графіків
# ──────────────────────────────────────────────────────────────────────────────

COLORS = {
    "blue":   "#4A90D9",
    "red":    "#E74C3C",
    "green":  "#2ECC71",
    "purple": "#9B59B6",
    "orange": "#E67E22",
}


def _fig_style():
    plt.style.use("seaborn-v0_8-whitegrid")


def plot_throughput_vs_nodes(rows: List[dict]):
    if not HAS_MPL or not rows:
        return
    _fig_style()
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle("Масштабованість: кількість вузлів", fontsize=14, fontweight="bold")

    ns     = [r["num_nodes"] for r in rows]
    tps    = [r["throughput_tps"] for r in rows]
    pow_t  = [r["avg_pow_time_s"] for r in rows]
    con_t  = [r["avg_consensus_time_s"] for r in rows]

    for ax, y, title, ylabel, color in [
        (axes[0], tps,   "Пропускна здатність (TPS)",    "TPS",            COLORS["blue"]),
        (axes[1], pow_t, "Середній час PoW",              "Час, с",         COLORS["red"]),
        (axes[2], con_t, "Середній час консенсусу",       "Час, с",         COLORS["green"]),
    ]:
        ax.plot(ns, y, "o-", color=color, linewidth=2, markersize=8)
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("Кількість вузлів")
        ax.set_ylabel(ylabel)
        ax.set_xticks(ns)

    plt.tight_layout()
    path = os.path.join(PLOTS_DIR, "throughput_vs_nodes.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [PLOT] {path}")


def plot_latency_impact(rows: List[dict]):
    if not HAS_MPL or not rows:
        return
    _fig_style()
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Вплив затримки мережі", fontsize=14, fontweight="bold")

    lats = [r["latency_ms"] for r in rows]
    con  = [r["avg_consensus_time_s"] for r in rows]
    tot  = [r["avg_total_time_s"] for r in rows]

    axes[0].plot(lats, con, "s-", color=COLORS["purple"], linewidth=2, markersize=8)
    axes[0].set_title("Час консенсусу vs Затримка мережі")
    axes[0].set_xlabel("Затримка, мс"); axes[0].set_ylabel("Час, с")

    axes[1].plot(lats, tot, "s-", color=COLORS["orange"], linewidth=2, markersize=8)
    axes[1].set_title("Загальний час vs Затримка мережі")
    axes[1].set_xlabel("Затримка, мс"); axes[1].set_ylabel("Час, с")

    plt.tight_layout()
    path = os.path.join(PLOTS_DIR, "latency_impact.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [PLOT] {path}")


def plot_file_size_impact(rows: List[dict]):
    if not HAS_MPL or not rows:
        return
    _fig_style()
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle("Вплив розміру файлу", fontsize=14, fontweight="bold")

    sizes  = [r["file_size_kb"] for r in rows]
    enc    = [r["avg_encrypt_time_s"] * 1000 for r in rows]  # → мс
    pow_t  = [r["avg_pow_time_s"] for r in rows]
    tot    = [r["avg_total_time_s"] for r in rows]

    for ax, y, title, ylabel, color in [
        (axes[0], enc,   "Час шифрування AES-256",  "Час, мс",  COLORS["blue"]),
        (axes[1], pow_t, "Час PoW",                 "Час, с",   COLORS["red"]),
        (axes[2], tot,   "Загальний час передачі",  "Час, с",   COLORS["green"]),
    ]:
        ax.plot(sizes, y, "D-", color=color, linewidth=2, markersize=8)
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("Розмір файлу, КБ")
        ax.set_ylabel(ylabel)

    plt.tight_layout()
    path = os.path.join(PLOTS_DIR, "file_size_impact.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [PLOT] {path}")


def plot_summary_dashboard(t_rows, l_rows, f_rows):
    """Зведена панель: всі ключові метрики на одному рисунку."""
    if not HAS_MPL:
        return
    _fig_style()
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle(
        "Аналіз масштабованості: децентралізована система захищеного файлообміну\nна приватному блокчейні",
        fontsize=13, fontweight="bold"
    )

    # Row 0 — throughput data
    if t_rows:
        ns = [r["num_nodes"] for r in t_rows]
        axes[0][0].plot(ns, [r["throughput_tps"] for r in t_rows], "o-", color=COLORS["blue"], lw=2, ms=8)
        axes[0][0].set_title("TPS vs Кількість вузлів"); axes[0][0].set_xlabel("Вузли"); axes[0][0].set_ylabel("TPS")

        axes[0][1].plot(ns, [r["avg_pow_time_s"] for r in t_rows], "o-", color=COLORS["red"], lw=2, ms=8)
        axes[0][1].set_title("Час PoW vs Вузли"); axes[0][1].set_xlabel("Вузли"); axes[0][1].set_ylabel("Час, с")

        axes[0][2].plot(ns, [r["avg_consensus_time_s"] for r in t_rows], "o-", color=COLORS["green"], lw=2, ms=8)
        axes[0][2].set_title("Час консенсусу vs Вузли"); axes[0][2].set_xlabel("Вузли"); axes[0][2].set_ylabel("Час, с")

    # Row 1 — latency + filesize
    if l_rows:
        lats = [r["latency_ms"] for r in l_rows]
        axes[1][0].plot(lats, [r["avg_consensus_time_s"] for r in l_rows], "s-", color=COLORS["purple"], lw=2, ms=8)
        axes[1][0].set_title("Консенсус vs Затримка"); axes[1][0].set_xlabel("Затримка, мс"); axes[1][0].set_ylabel("Час, с")

        axes[1][1].plot(lats, [r["avg_total_time_s"] for r in l_rows], "s-", color=COLORS["orange"], lw=2, ms=8)
        axes[1][1].set_title("Загальний час vs Затримка"); axes[1][1].set_xlabel("Затримка, мс"); axes[1][1].set_ylabel("Час, с")

    if f_rows:
        sizes = [r["file_size_kb"] for r in f_rows]
        axes[1][2].plot(sizes, [r["avg_total_time_s"] for r in f_rows], "D-", color=COLORS["blue"], lw=2, ms=8)
        axes[1][2].set_title("Загальний час vs Розмір файлу"); axes[1][2].set_xlabel("КБ"); axes[1][2].set_ylabel("Час, с")

    plt.tight_layout()
    path = os.path.join(PLOTS_DIR, "summary_dashboard.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [PLOT] {path}")


# ──────────────────────────────────────────────────────────────────────────────
#  Точка входу
# ──────────────────────────────────────────────────────────────────────────────

def run_full_analysis(
    node_counts: List[int] = None,
    latencies_ms: List[float] = None,
    file_sizes: List[int] = None,
    num_transfers: int = 5,
):
    """Запустити повний аналіз масштабованості."""
    _ensure_dirs()

    t_rows = test_throughput_vs_nodes(node_counts, num_transfers)
    l_rows = test_latency_impact(latencies_ms, num_transfers=num_transfers)
    f_rows = test_file_size_impact(file_sizes, num_transfers=min(num_transfers, 3))

    print("\n[PLOTS] Побудова графіків...")
    plot_throughput_vs_nodes(t_rows)
    plot_latency_impact(l_rows)
    plot_file_size_impact(f_rows)
    plot_summary_dashboard(t_rows, l_rows, f_rows)

    # Зберегти зведений JSON
    summary = {
        "throughput_vs_nodes": t_rows,
        "latency_impact":      l_rows,
        "file_size_impact":    f_rows,
    }
    json_path = os.path.join(RESULTS_DIR, "scalability_summary.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\n[DONE] Результати збережено у: {RESULTS_DIR}/")
    return summary


if __name__ == "__main__":
    run_full_analysis(
        node_counts=[2, 3, 5, 7, 10],
        latencies_ms=[0, 10, 50, 100, 200],
        file_sizes=[1024, 10*1024, 50*1024, 100*1024, 512*1024],
        num_transfers=5,
    )
