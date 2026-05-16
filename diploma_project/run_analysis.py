"""
Точка входу для запуску аналізу масштабованості.
Запуск: python run_analysis.py
"""
from analysis.scalability import run_full_analysis

if __name__ == "__main__":
    run_full_analysis(
        node_counts=[2, 3, 5, 7, 10],
        latencies_ms=[0, 10, 50, 100, 200],
        file_sizes=[1024, 10*1024, 50*1024, 100*1024, 512*1024],
        num_transfers=5,
    )
