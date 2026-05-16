"""
Збір та збереження метрик продуктивності вузла.
Відстежує: PoW-час, час консенсусу, час передачі файлів, розмір ланцюга.
"""
import time
import csv
import json
import os
from collections import defaultdict
from contextlib import contextmanager
from typing import Optional
import statistics


RESULTS_DIR = "results"


class MetricsCollector:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self._data: dict[str, list] = defaultdict(list)
        os.makedirs(RESULTS_DIR, exist_ok=True)

    def record(self, metric: str, value: float, meta: dict = None):
        """Записати числове значення метрики."""
        entry = {"value": value, "ts": time.time()}
        if meta:
            entry.update(meta)
        self._data[metric].append(entry)

    @contextmanager
    def measure(self, metric: str, meta: dict = None):
        """Контекстний менеджер для автоматичного вимірювання часу."""
        t0 = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - t0
            self.record(metric, elapsed, meta)

    def get_summary(self) -> dict:
        """Повернути агрегований підсумок усіх метрик."""
        summary = {"node_id": self.node_id}
        for metric, entries in self._data.items():
            vals = [e["value"] for e in entries]
            if not vals:
                continue
            summary[metric] = {
                "count": len(vals),
                "mean": round(statistics.mean(vals), 6),
                "min": round(min(vals), 6),
                "max": round(max(vals), 6),
                "stdev": round(statistics.stdev(vals), 6) if len(vals) > 1 else 0.0,
            }
        return summary

    def save_csv(self, filename: Optional[str] = None):
        """Зберегти всі метрики у CSV-файл."""
        if filename is None:
            filename = f"metrics_{self.node_id}.csv"
        filepath = os.path.join(RESULTS_DIR, filename)
        rows = []
        for metric, entries in self._data.items():
            for e in entries:
                row = {"node_id": self.node_id, "metric": metric}
                row.update(e)
                rows.append(row)

        if not rows:
            return filepath

        fieldnames = list(rows[0].keys())
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

        return filepath

    def save_json(self, filename: Optional[str] = None):
        """Зберегти підсумок метрик у JSON-файл."""
        if filename is None:
            filename = f"metrics_{self.node_id}.json"
        filepath = os.path.join(RESULTS_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.get_summary(), f, indent=2, ensure_ascii=False)
        return filepath

    def reset(self):
        """Очистити всі зібрані метрики."""
        self._data.clear()
