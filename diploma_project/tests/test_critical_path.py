import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import json

# Ensure the root directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from blockchain.chain import Chain
from blockchain.block import Block
from security.encryption import generate_aes_key, encrypt_file, decrypt_data
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from blockchain.keys import sign_data

class TestCriticalPath(unittest.TestCase):

    # =========================================================================
    # БЛОК 1: ТЕСТИ БЛОКЧЕЙНУ ТА КОНСЕНСУСУ (Blockchain & Consensus)
    # =========================================================================

    def test_blockchain_rejects_tampered_blocks(self):
        """Тест надійності: Блокчейн повинен відхиляти змінені заднім числом блоки (Immutability)."""
        test_chain = Chain()
        
        valid_block = Block(
            index=1,
            timestamp="2026-05-24T12:00:00Z",
            data={"filename": "secret.txt", "file_hash": "abc123hash"},
            previous_hash="0" * 64
        )
        valid_block.hash = "00000_valid_hash_here" 
        
        # Хакер змінює вміст блоку (file_hash)
        tampered_block = Block(
            index=1,
            timestamp="2026-05-24T12:00:00Z",
            data={"filename": "secret.txt", "file_hash": "HACKED_HASH"},
            previous_hash="0" * 64
        )
        tampered_block.hash = valid_block.hash # Хакер залишає оригінальний хеш, щоб обманути систему
        
        is_valid, reason = test_chain.validate_block(tampered_block, "validator_node")
        self.assertFalse(is_valid)
        self.assertIn("hash", reason.lower())

    def test_proof_of_work_difficulty(self):
        """Тест PoW: Алгоритм повинен генерувати хеш, що починається з потрібної кількості нулів (Spam Protection)."""
        test_chain = Chain()
        block = Block(1, "2026-05-24T12:00:00Z", "Test Data", "0" * 64)
        
        # Виконуємо майнінг
        final_hash = test_chain.proof_of_work(block)
        
        from blockchain.chain import HASH_TARGET
        # Перевіряємо, що згенерований хеш задовольняє поточну складність мережі
        self.assertTrue(final_hash.startswith(HASH_TARGET))
        self.assertEqual(block.hash, final_hash)
        self.assertGreater(block.nonce, 0, "Nonce повинен збільшитися під час майнінгу")

    @patch('blockchain.chain.Chain.verify_chain_integrity')
    def test_consensus_fork_resolution(self, mock_is_valid):
        """Тест Консенсусу: Вирішення конфліктів ланцюгів (Найдовший ланцюг перемагає)."""
        mock_is_valid.return_value = (True, [])
        test_chain = Chain()
        
        # Створюємо фейковий "чужий" довший ланцюг
        longer_chain = {
            'length': 3,
            'latest_hash': 'hash1',
            'blocks': [
                Block(0, "Time", "Genesis", "0").dict,
                Block(1, "Time", "Data1", "hash0").dict,
                Block(2, "Time", "Data2", "hash1").dict
            ],
            'block_hashes': ['0', 'hash0', 'hash1']
        }
        
        # Наш локальний ланцюг коротший
        test_chain.blockchain = [
            Block(0, "Time", "Genesis", "0")
        ]
        
        # Викликаємо функцію вирішення конфліктів
        resolved = test_chain.resolve_conflicts(longer_chain)
        
        self.assertTrue(resolved, "Блокчейн повинен прийняти довший валідний ланцюг від пірів")
        self.assertEqual(len(test_chain.blockchain), 3, "Локальний ланцюг повинен оновитися до довжини 3")

    def test_concurrency_race_condition(self):
        """Тест Багатопотоковості: Запобігання Race Condition при одночасному створенні блоків."""
        import threading
        test_chain = Chain()
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        
        # Імітуємо 10 клієнтів, які одночасно намагаються створити блок
        def worker(thread_id):
            # Функція create_block використовує threading.RLock() всередині
            test_chain.create_block({"data": f"Thread {thread_id}"}, private_key)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        # Перевіряємо, що жоден блок не загубився і база даних не пошкоджена
        self.assertEqual(len(test_chain.pending_blocks), 10, "Усі 10 блоків мають бути в черзі без втрат!")

    def test_missing_block_sync_trigger(self):
        """Тест Синхронізації: Виявлення 'дірок' у ланцюзі (Missing Blocks)."""
        test_chain = Chain()
        # Поточний ланцюг має лише Genesis блок (Block 0)
        
        # Ми отримуємо Блок №2 від сусіда (пропустивши Блок №1)
        future_block = Block(
            index=2,
            timestamp="2026-05-24T12:00:00Z",
            data={"file": "test.txt"},
            previous_hash="hash_of_missing_block_1"
        )
        
        # Блокчейн повинен помітити, що previous_hash цього блоку не збігається з нашим останнім блоком
        is_valid, reason = test_chain.is_valid_block(future_block)
        
        self.assertFalse(is_valid, "Блокчейн не повинен приймати блок, якщо пропущено попередні")
        self.assertIn("previous_hash_mismatch", reason.lower(), "Система повинна чітко вказати на розрив ланцюга")

    # =========================================================================
    # БЛОК 2: ТЕСТИ КРИПТОГРАФІЇ ТА АВТОРИЗАЦІЇ (Cryptography & Security)
    # =========================================================================

    def test_aes_encryption_decryption_flow(self):
        """Тест Захисту Даних: Перевірка надійності симетричного AES-256-GCM шифрування файлів."""
        aes_key = generate_aes_key()
        self.assertEqual(len(aes_key), 32)
        
        secret_data = b"This is a top secret diploma file content!"
        test_file = "test_secret.txt"
        with open(test_file, "wb") as f: f.write(secret_data)
            
        encrypted_data = encrypt_file(test_file, aes_key)
        self.assertNotIn(secret_data, encrypted_data) # Доводить, що файл перетворився на кашу
        
        decrypted_data = decrypt_data(encrypted_data, aes_key)
        self.assertEqual(decrypted_data, secret_data) # Доводить, що дані не пошкоджено
        
        if os.path.exists(test_file): os.remove(test_file)

    def test_rsa_signature_forgery(self):
        """Тест Цифрового Підпису: Захист від атаки підміни автора (Identity Spoofing)."""
        # 1. Генеруємо ключ реального користувача
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        
        # 2. Генеруємо ключ хакера
        hacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        
        block_hash = "fake_block_hash_123"
        
        # Хакер підписує чужий блок СВОЇМ ключем
        forged_signature = sign_data(hacker_key, block_hash)
        
        # Створюємо мок для перевірки
        test_chain = Chain()
        block = Block(1, "Time", "Data", "PrevHash")
        block.hash = block_hash
        block.signature = forged_signature
        
        # Ми імітуємо, що система бере публічний ключ СПРАВЖНЬОГО користувача для перевірки
        public_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        with patch("builtins.open", unittest.mock.mock_open(read_data=public_bytes)):
            is_valid, reason = test_chain.validate_block_signature(block, "real_user_id")
            
        self.assertFalse(is_valid, "Система повинна відхилити блок, підписаний чужим ключем!")
        self.assertIn("invalid", reason.lower())

    # =========================================================================
    # БЛОК 3: ТЕСТИ МЕРЕЖЕВОЇ ВІДМОВОСТІЙКОСТІ (Network Fault Tolerance)
    # =========================================================================

    @patch('socket.socket')
    @patch('network.config.NetworkConfig')
    def test_node_handles_connection_refused(self, mock_config, mock_socket):
        """Тест P2P Мережі: Самовідновлення мережі при відключенні ноди (Self-Healing)."""
        mock_socket_instance = MagicMock()
        mock_socket_instance.connect.side_effect = ConnectionRefusedError("[WinError 10061]")
        mock_socket.return_value.__enter__.return_value = mock_socket_instance
        
        mock_config.get_node_info.return_value = ("127.0.0.1", 5000)
        mock_config._discovery.get_file_transfer_port.return_value = 6000
        mock_config.get_peers.return_value = []
        
        from network.node import Node
        test_node = Node("node1")
        
        dead_peer = ("192.168.0.100", 6001)
        test_node.peers.append(dead_peer)
        test_node.sync_with_peers()
        
        self.assertNotIn(dead_peer, test_node.peers, "Мертва нода повинна бути автоматично видалена!")

    @patch('network.discovery.socket.socket')
    def test_discovery_handles_malformed_udp_packets(self, mock_socket):
        """Тест Виявлення: Захист від збійних або хакерських пакетів у локальній мережі."""
        from network.discovery import NetworkDiscovery
        discovery = NetworkDiscovery()
        
        # Імітуємо отримання пошкодженого JSON пакету з мережі
        mock_socket_instance = MagicMock()
        mock_socket_instance.recv.return_value = b"{broken_json: ]"
        mock_socket.return_value.__enter__.return_value = mock_socket_instance
        
        try:
            # Функція не повинна "впасти" (crash), а просто проігнорувати пакет
            discovery._handle_discovery_request(mock_socket_instance, "test_node")
            crashed = False
        except Exception:
            crashed = True
            
        self.assertFalse(crashed, "Модуль автовиявлення не повинен падати при отриманні битих пакетів!")

if __name__ == '__main__':
    unittest.main()
