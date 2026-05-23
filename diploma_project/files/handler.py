"""
Модуль захищеного файлообміну з AES-256-GCM шифруванням.
"""
import os
import hashlib
import base64
import json
import socket
import time
from typing import Dict, Optional

from security.encryption import generate_aes_key, encrypt_file, decrypt_data, wrap_aes_key, unwrap_aes_key
from analysis.logger import NodeLogger
from analysis.metrics import MetricsCollector


class FileTransfer:
    CHUNK_SIZE = 8192
    FILE_STORAGE = "node_files"
    TRANSFER_TIMEOUT = 60

    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def prepare_storage():
        os.makedirs(FileTransfer.FILE_STORAGE, exist_ok=True)

    @staticmethod
    def create_file_metadata(file_path: str, encrypted_aes_key_b64: Optional[str] = None) -> dict:
        file_hash = FileTransfer.calculate_file_hash(file_path)
        meta = {
            "filename":   os.path.basename(file_path),
            "file_hash":  file_hash,
            "file_size":  os.path.getsize(file_path),
            "timestamp":  time.time(),
            "encrypted":  encrypted_aes_key_b64 is not None,
        }
        if encrypted_aes_key_b64:
            meta["aes_key_encrypted"] = encrypted_aes_key_b64
        return meta


class FileHandler:
    def __init__(self, node):
        self.node = node
        FileTransfer.prepare_storage()
        self.transfer_status: Dict[str, bool] = {}
        self.logger = NodeLogger(node.node_id)
        self.metrics = MetricsCollector(node.node_id)

    # ── Отримати публічний ключ peers (якщо є) ─────────────────────────────

    def _get_peer_public_key(self, peer_host: str):
        """Завантажити публічний ключ peer з файлу (якщо є)."""
        from cryptography.hazmat.primitives import serialization
        for node_id, (host, _) in self.node.__class__.__dict__.items():
            pass  # placeholder — у реальній мережі публічний ключ обмінюється при виявленні
        # Пошук за збереженими public_key_*.pem
        for fname in os.listdir("."):
            if fname.startswith("public_key_") and fname.endswith(".pem"):
                try:
                    with open(fname, "rb") as f:
                        return serialization.load_pem_public_key(f.read())
                except Exception:
                    continue
        return None

    # ── Відправка ──────────────────────────────────────────────────────────

    def send_file(self, file_path: str, targets: list = None) -> bool:
        try:
            if not os.path.exists(file_path):
                self.logger.error("file_not_found", {"path": file_path})
                return False

            # Шифрування AES-256-GCM
            with self.metrics.measure("encryption_time"):
                aes_key = generate_aes_key()
                encrypted_data = encrypt_file(file_path, aes_key)

            # Wrapped AES key (RSA-OAEP) — для кожного peer своє, якщо є ключ
            # Спрощено: передаємо AES-ключ у base64 (у продакшні — зашифрований RSA peer'а)
            aes_key_b64 = base64.b64encode(aes_key).decode("utf-8")
            metadata = FileTransfer.create_file_metadata(file_path, aes_key_b64)
            metadata["encrypted_size"] = len(encrypted_data)

            self.logger.info("send_start", {
                "file": metadata["filename"],
                "size": metadata["file_size"],
                "encrypted_size": len(encrypted_data),
            })

            peers_to_send = self.node.peers
            if targets:
                target_tuples = []
                for t in targets:
                    parts = t.split(":")
                    if len(parts) == 2:
                        target_tuples.append((parts[0], int(parts[1])))
                peers_to_send = [p for p in peers_to_send if p in target_tuples]

            if not peers_to_send:
                self.logger.warning("no_peers")
                return False

            with self.metrics.measure("broadcast_time"):
                success = self._broadcast_encrypted(encrypted_data, metadata, peers_to_send)

            if success:
                file_data = {
                    **metadata,
                    "sender_node": self.node.node_id,
                    "transfer_status": "completed",
                }
                self.node.create_and_broadcast_block(json.dumps(file_data))
                self.logger.info("send_complete", {"file": metadata["filename"]})
                self.metrics.save_csv()
                return True

            self.logger.error("send_failed", {"file": metadata["filename"]})
            return False

        except Exception as e:
            self.logger.error("send_exception", {"error": str(e)})
            return False

    def _broadcast_encrypted(self, encrypted_data: bytes, metadata: dict, peers_to_send: list) -> bool:
        successful = 0
        for peer_host, peer_port in peers_to_send:
            try:
                self.logger.debug("connect_peer", {"host": peer_host, "port": peer_port})
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(FileTransfer.TRANSFER_TIMEOUT)
                    s.connect((peer_host, peer_port))

                    # 1. Метадані
                    msg = {
                        "type": "file_transfer",
                        "metadata": metadata,
                        "sender_node": self.node.node_id,
                    }
                    s.sendall(json.dumps(msg).encode("utf-8"))

                    # 2. Сигнал готовності
                    s.settimeout(5)
                    try:
                        if s.recv(1024).decode("utf-8") != "ready":
                            continue
                    except socket.timeout:
                        continue

                    # 3. Передача зашифрованих даних
                    s.settimeout(FileTransfer.TRANSFER_TIMEOUT)
                    total = len(encrypted_data)
                    sent = 0
                    with self.metrics.measure("transfer_time", {"peer": peer_host}):
                        while sent < total:
                            chunk = encrypted_data[sent: sent + FileTransfer.CHUNK_SIZE]
                            s.sendall(chunk)
                            sent += len(chunk)

                    self.logger.info("peer_transfer_ok", {"peer": peer_host, "bytes": sent})
                    successful += 1

            except socket.timeout:
                self.logger.warning("peer_timeout", {"host": peer_host})
            except ConnectionRefusedError:
                self.logger.warning("peer_refused", {"host": peer_host})
            except Exception as e:
                self.logger.error("peer_error", {"host": peer_host, "error": str(e)})

        return successful > 0

    # ── Приймання ──────────────────────────────────────────────────────────

    def receive_file(self, client_socket: socket.socket, metadata: dict) -> bool:
        filename         = metadata["filename"]
        expected_hash    = metadata["file_hash"]
        expected_size    = metadata.get("encrypted_size", metadata["file_size"])
        is_encrypted     = metadata.get("encrypted", False)
        aes_key_b64      = metadata.get("aes_key_encrypted")

        self.logger.info("receive_start", {"file": filename, "encrypted": is_encrypted})
        tmp_path  = os.path.join(FileTransfer.FILE_STORAGE, filename + ".enc.tmp")
        out_path  = os.path.join(FileTransfer.FILE_STORAGE, filename)

        try:
            client_socket.sendall(b"ready")

            received = 0
            with open(tmp_path, "wb") as f:
                while received < expected_size:
                    chunk = client_socket.recv(
                        min(FileTransfer.CHUNK_SIZE, expected_size - received)
                    )
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)

            # Розшифрування
            if is_encrypted and aes_key_b64:
                with self.metrics.measure("decryption_time"):
                    aes_key = base64.b64decode(aes_key_b64)
                    with open(tmp_path, "rb") as f:
                        encrypted_data = f.read()
                    plaintext = decrypt_data(encrypted_data, aes_key)
                    with open(out_path, "wb") as f:
                        f.write(plaintext)
                os.remove(tmp_path)
            else:
                os.rename(tmp_path, out_path)

            # Перевірка цілісності
            actual_hash = FileTransfer.calculate_file_hash(out_path)
            if actual_hash != expected_hash:
                self.logger.error("hash_mismatch", {"file": filename})
                os.remove(out_path)
                return False

            self.logger.info("receive_ok", {"file": filename})
            self.metrics.save_csv()
            return True

        except Exception as e:
            self.logger.error("receive_exception", {"error": str(e)})
            for p in (tmp_path, out_path):
                if os.path.exists(p):
                    os.remove(p)
            return False