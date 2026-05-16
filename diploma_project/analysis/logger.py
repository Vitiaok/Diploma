"""
Централізований логер для вузлів блокчейн-мережі.
Записує події у JSON-форматі з часовими мітками.
"""
import logging
import json
import os
from datetime import datetime


LOG_DIR = "logs"


class NodeLogger:
    def __init__(self, node_id: str, log_dir: str = LOG_DIR):
        self.node_id = node_id
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

        log_path = os.path.join(log_dir, f"node_{node_id}.log")

        self._logger = logging.getLogger(f"node.{node_id}")
        self._logger.setLevel(logging.DEBUG)

        if not self._logger.handlers:
            fh = logging.FileHandler(log_path, encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(fh)

            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            ch.setFormatter(logging.Formatter("[%(asctime)s][%(name)s] %(message)s", "%H:%M:%S"))
            self._logger.addHandler(ch)

    def _format(self, level: str, event: str, data: dict = None) -> str:
        record = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "node": self.node_id,
            "level": level,
            "event": event,
        }
        if data:
            record["data"] = data
        return json.dumps(record, ensure_ascii=False)

    def info(self, event: str, data: dict = None):
        self._logger.info(self._format("INFO", event, data))

    def warning(self, event: str, data: dict = None):
        self._logger.warning(self._format("WARNING", event, data))

    def error(self, event: str, data: dict = None):
        self._logger.error(self._format("ERROR", event, data))

    def debug(self, event: str, data: dict = None):
        self._logger.debug(self._format("DEBUG", event, data))
