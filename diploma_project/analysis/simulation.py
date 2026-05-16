"""
Модуль симуляції P2P мережі блокчейну.

Дозволяє запускати N вузлів в одному процесі (без реальних сокетів),
імітуючи затримки мережі, консенсус PoW і захищений файлообмін.
"""
import threading
import time
import random
import os
import json
import hashlib
from typing import List, Optional

from cryptography.hazmat.primitives.asymmetric import rsa

from blockchain.block import Block
from blockchain.chain import Chain
from blockchain.keys import sign_data
from analysis.metrics import MetricsCollector
from security.encryption import generate_aes_key, encrypt_data


# ──────────────────────────────────────────────────────────────────────────────
#  In-memory Chain (без запису у файл)
# ──────────────────────────────────────────────────────────────────────────────

class SimulatedChain(Chain):
    """Chain без файлового I/O — для симуляції."""

    def save_chain(self):
        pass

    def load_chain(self):
        self.blockchain = []


# ──────────────────────────────────────────────────────────────────────────────
#  Один симульований вузол
# ──────────────────────────────────────────────────────────────────────────────

class SimulatedNode:
    """
    Симульований P2P-вузол блокчейну.
    Комунікація між вузлами — прямі виклики методів (без TCP).
    """

    def __init__(self, node_id: str, latency_ms: float = 0.0):
        self.node_id = node_id
        self.latency_ms = latency_ms
        self.chain = SimulatedChain()
        self.peers: List["SimulatedNode"] = []
        self.metrics = MetricsCollector(node_id)
        self._lock = threading.Lock()

        # RSA-ключі у пам'яті
        self._private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )
        self.public_key = self._private_key.public_key()

    # ── Утиліти ───────────────────────────────────────────────────────────────

    def _delay(self):
        if self.latency_ms > 0:
            jitter = random.uniform(0, self.latency_ms * 0.1)
            time.sleep((self.latency_ms + jitter) / 1000.0)

    # ── Валідація (викликається іншими вузлами) ────────────────────────────────

    def receive_validation_request(self, block_dict: dict, sender_id: str) -> dict:
        self._delay()
        block = Block(**block_dict)
        with self._lock:
            # Вже є в ланцюзі?
            if any(b.hash == block.hash for b in self.chain.blockchain):
                return {"type": "validation_failed", "reason": "duplicate"}
        # Базова перевірка хешу і PoW
        if (block.hash == block.calculate_hash() and
                block.hash[:5] == "00000"):
            with self._lock:
                self.chain.blockchain.append(block)
            return {"type": "validation_success", "block_hash": block.hash}
        return {"type": "validation_failed", "reason": "invalid_hash"}

    # ── Консенсус ─────────────────────────────────────────────────────────────

    def _broadcast_consensus(self, block: Block) -> bool:
        if not self.peers:
            self.chain.add_validated_block(block)
            return True

        results = []
        lock = threading.Lock()

        def ask(peer):
            r = peer.receive_validation_request(block.dict, self.node_id)
            with lock:
                results.append(r)

        threads = [threading.Thread(target=ask, args=(p,), daemon=True)
                   for p in self.peers]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        successes = sum(1 for r in results if r.get("type") == "validation_success")
        if successes > len(self.peers) // 2:
            self.chain.add_validated_block(block)
            return True
        return False

    # ── Симуляція передачі файлу ───────────────────────────────────────────────

    def simulate_file_transfer(self, file_size_bytes: int) -> dict:
        """
        Повний цикл: шифрування → блок PoW → консенсус.
        Повертає словник з часовими метриками.
        """
        t_total_start = time.perf_counter()

        # 1. Генерація псевдофайлу
        dummy_data = os.urandom(file_size_bytes)
        file_hash = hashlib.sha256(dummy_data).hexdigest()

        # 2. Шифрування AES-256-GCM
        with self.metrics.measure("encryption_time", {"file_size": file_size_bytes}):
            aes_key = generate_aes_key()
            encrypted = encrypt_data(dummy_data, aes_key)

        # 3. Симуляція передачі (затримка)
        with self.metrics.measure("transfer_time", {"file_size": file_size_bytes}):
            self._delay()

        # 4. PoW + підпис
        with self.metrics.measure("pow_time"):
            metadata = json.dumps({
                "filename": f"sim_{file_size_bytes}.bin",
                "file_hash": file_hash,
                "file_size": file_size_bytes,
                "encrypted_size": len(encrypted),
                "sender": self.node_id,
            })
            block = self.chain.create_block(metadata, self._private_key)

        # 5. Консенсус
        with self.metrics.measure("consensus_time", {"peers": len(self.peers)}):
            success = self._broadcast_consensus(block)

        total_time = time.perf_counter() - t_total_start
        self.metrics.record("total_time", total_time, {"file_size": file_size_bytes})

        return {
            "success": success,
            "file_size": file_size_bytes,
            "encrypted_size": len(encrypted),
            "encryption_time": self.metrics._data["encryption_time"][-1]["value"],
            "transfer_time":   self.metrics._data["transfer_time"][-1]["value"],
            "pow_time":        self.metrics._data["pow_time"][-1]["value"],
            "consensus_time":  self.metrics._data["consensus_time"][-1]["value"],
            "total_time":      total_time,
            "num_peers":       len(self.peers),
            "block_hash":      block.hash,
        }


# ──────────────────────────────────────────────────────────────────────────────
#  Мережевий симулятор
# ──────────────────────────────────────────────────────────────────────────────

class NetworkSimulator:
    """
    Симулює P2P-мережу з num_nodes вузлів у повній топології (full-mesh).
    """

    def __init__(self, num_nodes: int, latency_ms: float = 0.0):
        self.num_nodes = num_nodes
        self.latency_ms = latency_ms
        self.nodes: List[SimulatedNode] = []
        self._build()

    def _build(self):
        self.nodes = [
            SimulatedNode(f"node_{i}", self.latency_ms)
            for i in range(self.num_nodes)
        ]
        # Full-mesh: кожен вузол знає всіх інших
        for i, node in enumerate(self.nodes):
            node.peers = [n for j, n in enumerate(self.nodes) if j != i]

    def run_benchmark(
        self,
        num_transfers: int = 10,
        file_size_bytes: int = 10 * 1024,
    ) -> List[dict]:
        """
        Запустити серію симульованих передач файлів.
        Повертає список результатів з метриками.
        """
        results = []
        for i in range(num_transfers):
            sender = random.choice(self.nodes)
            result = sender.simulate_file_transfer(file_size_bytes)
            result["transfer_id"] = i
            result["sender_id"] = sender.node_id
            results.append(result)
        return results

    def network_stats(self) -> dict:
        lengths = [len(n.chain.blockchain) for n in self.nodes]
        return {
            "num_nodes": self.num_nodes,
            "latency_ms": self.latency_ms,
            "chain_lengths": lengths,
            "avg_chain_length": sum(lengths) / max(len(lengths), 1),
            "chains_consistent": len(set(lengths)) == 1,
        }
