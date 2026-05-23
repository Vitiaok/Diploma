import socket
import threading
import json
from blockchain.chain import Chain
from blockchain.block import Block
from network.config import NetworkConfig
import time
from blockchain.keys import generate_and_save_keys, sign_data
import os
from cryptography.hazmat.primitives import serialization
from files.handler import FileHandler
import struct
from analysis.logger import NodeLogger
from analysis.metrics import MetricsCollector

HASH_TARGET = "00000"
MULTICAST_GROUP = '224.0.0.1'  
MULTICAST_PORT = 5007          
BUFFER_SIZE = 1024

class Node:
    def __init__(self, node_id):
        self.node_id = node_id
        generate_and_save_keys(self.node_id)
        self.discovery_host, self.discovery_port = NetworkConfig.get_node_info(node_id)
        self.file_transfer_port = NetworkConfig._discovery.get_file_transfer_port(self.discovery_port)
        self.host = self.discovery_host
        self.port = self.file_transfer_port
        self.chain = Chain()
        self.peers = self._get_file_transfer_peers()
        self.running = True
        self.file_handler = FileHandler(self)
        self.force_sync_required = False
        self.peer_connections = {}
        self.connection_lock = threading.Lock()
        self.logger = NodeLogger(node_id)
        self.metrics = MetricsCollector(node_id)
        self.logger.info("node_started", {"host": self.host, "port": self.port})

    def load_private_key(self):
        private_key_path = f"private_key_{self.node_id}.pem"
        
        if not os.path.exists(private_key_path):
            raise FileNotFoundError(f"Private key file {private_key_path} not found.")

        with open(private_key_path, "rb") as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=None,  
            )
        
        return private_key
    
    def load_all_public_keys(self):
       
        public_keys = {}
    
        for node_id in self.peers:
            public_key_path = f"public_key_{node_id}.pem"
        
            if not os.path.exists(public_key_path):
                print(f"Public key file {public_key_path} not found for node {node_id}.")
                continue
        
            with open(public_key_path, "rb") as key_file:
                public_key = key_file.read()
                public_keys[node_id] = public_key
    
        return public_keys

    def handle_client(self, client_socket, addr):
        try:
            data = client_socket.recv(4096).decode('utf-8')
            message = json.loads(data)
            
            if message['type'] == 'validate_block':
                block = Block(**message['block'])
                validator_id = message['validator']
                
                
                if any(existing.hash == block.hash for existing in self.chain.blockchain):
                    print(f"Block {block.hash} already exists in chain, skipping validation")
                    response = {
                        'type': 'validation_failed',
                        'block_hash': block.hash,
                        'validator': self.node_id,
                        'reason': 'duplicate_block'
                    }
                else:
                    is_valid, reason = self.chain.validate_block(block, validator_id)
                    if is_valid:
                        response = {
                            'type': 'validation_success',
                            'block_hash': block.hash,
                            'validator': self.node_id
                        }
                    else:
                        response = {
                            'type': 'validation_failed',
                            'block_hash': block.hash,
                            'validator': self.node_id,
                            'reason': reason
                        }
                        if 'missing_previous_blocks' in reason or 'previous_hash_mismatch' in reason:
                            print(f"Validation failed due to desync ({reason}). Triggering background sync...")
                            threading.Thread(target=self.sync_with_peers, daemon=True).start()
                
                client_socket.sendall(json.dumps(response).encode('utf-8'))
                
            elif message['type'] == 'file_transfer':
                self.file_handler.receive_file(client_socket, message['metadata'])
                
            elif message['type'] == 'get_chain':
                response = {
                    'type': 'chain_data',
                    'chain': self.chain.get_chain_snapshot()
                }
                client_socket.sendall(json.dumps(response).encode('utf-8'))
                
            elif message['type'] == 'get_block':
                block_index = message['block_index']
                if 0 <= block_index < len(self.chain.blockchain):
                    response = {
                        'type': 'block_data',
                        'block': self.chain.blockchain[block_index].dict
                    }
                else:
                    response = {
                        'type': 'block_data',
                        'block': None
                    }
                client_socket.sendall(json.dumps(response).encode('utf-8'))
                
        except Exception as e:
            print(f"Error handling client {addr}: {e}")
        finally:
            client_socket.close()

    

    def broadcast_block_for_validation(self, block):
        if not self.peers:
            print("Block validation failed: Network is empty, consensus impossible. Block discarded.")
            return False, False

        block_data = json.dumps({
            'type': 'validate_block',
            'block': block.dict,
            'validator': self.node_id 
        })

        validation_responses = []
        validated = False  
        needs_sync = False
        
        for peer_host, peer_port in self.peers:
            connected = False
            retries = 3  
            
            while not connected and retries > 0:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.connect((peer_host, peer_port))
                        s.sendall(block_data.encode('utf-8'))
                        
                        response = json.loads(s.recv(4096).decode('utf-8'))
                        print(f"Validation response from {peer_host}:{peer_port}: {response}")
                        validation_responses.append(response)
                        
                        if response.get('type') == 'validation_failed' and 'previous_hash_mismatch' in str(response.get('reason', '')):
                            needs_sync = True

                        successful_validations = sum(1 for res in validation_responses 
                                                if res.get('type') == 'validation_success')
                        
                        if not validated and successful_validations > len(self.peers) // 2:
                            print("Block received majority validation, adding to local chain.")
                            self.chain.add_validated_block(block)
                            validated = True  
                        
                        connected = True
                    
                except Exception as e:
                    print(f"Failed to send block to {peer_host}:{peer_port}: {e}")
                    print(f"Retries left: {retries}")
                    retries -= 1
                    if retries > 0:
                        time.sleep(5)

        if not validated:
            print("Block validation failed: Could not get majority validation from peers.")
            return False, needs_sync
            
        return True, needs_sync

    def start_server(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Прибираємо REUSEADDR, щоб порти не дублювалися на Windows
        # Слухаємо на всіх інтерфейсах (0.0.0.0)
        self.server_socket.bind(('0.0.0.0', self.port))
        self.server_socket.listen(5)
        print(f"Server started and listening on 0.0.0.0:{self.port} (announced as {self.host})")

        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                
                threading.Thread(target=self.handle_client, args=(client_socket, addr)).start()
            except Exception as e:
                if self.running:  
                    print(f"Server error: {e}")

    def create_and_broadcast_block(self, data):
        max_retries = 3
        for attempt in range(max_retries):
            private_key = self.load_private_key()
            with self.metrics.measure("pow_time"):
                new_block = self.chain.create_block(data, private_key)
            signature = sign_data(private_key, new_block.hash)
            new_block.signature = signature
            self.logger.info("block_created", {"hash": new_block.hash[:16], "attempt": attempt + 1})
            
            with self.metrics.measure("consensus_time", {"peers": len(self.peers)}):
                success, needs_sync = self.broadcast_block_for_validation(new_block)
                
            if success:
                self.metrics.save_csv()
                return True
                
            if needs_sync:
                print("Chain out of sync detected during broadcast. Forcing sync and retrying...")
                self.sync_with_peers()
            else:
                break
                
        self.metrics.save_csv()
        return False


    def user_interface(self):
        while self.running:
            command = input("\nEnter command (f: send file, c: show chain, s: stats, q: quit): ").strip().lower()

            if command == 'f':
                file_path = input("Enter path to the file to send: ")
                self.file_handler.send_file(file_path)
            elif command == 'c':
                
                for block in self.chain.get_chain():
                    print(json.dumps(block.dict, indent=2))
            elif command == 's':
                summary = self.metrics.get_summary()
                print(json.dumps(summary, indent=2, ensure_ascii=False))
                self.metrics.save_json()
            elif command == 'q':
                print("Shutting down node...")
                self.running = False

                
                if hasattr(self, 'server_socket') and self.server_socket:
                    try:
                        self.server_socket.close()
                        print("Server socket closed successfully.")
                    except Exception as e:
                        print(f"Error closing server socket: {e}")

                print("Node shutdown complete.")
            else:
                print("Invalid command. Try again.")



    def start(self):
        
        server_thread = threading.Thread(target=self.start_server)
        server_thread.daemon = True
        server_thread.start()

        multicast_listen_thread = threading.Thread(target=self.multicast_listen)
        multicast_listen_thread.daemon = True
        multicast_listen_thread.start()
        
        threading.Thread(target=self.periodic_multicast_announce, daemon=True).start()
        
        self.start_periodic_sync()

        try:
            self.user_interface()
        except KeyboardInterrupt:
            print("\nShutting down gracefully...")
        finally:
            self.running = False

            
    def sync_with_peers(self):
        
        is_valid, invalid_blocks = self.chain.verify_chain_integrity()
        
        if not is_valid:
            print(f"Found invalid blocks: {invalid_blocks}")
            
            for invalid_block in invalid_blocks:
                block_index = invalid_block['index']
                print(f"Attempting to repair block at index {block_index}")
                
                correct_block = self.request_block_from_peers(block_index)
                if correct_block:
                    try:
                        
                        json.dumps(correct_block)  
                        if self.chain.repair_block(block_index, correct_block):
                            print(f"Successfully repaired block at index {block_index}")
                        else:
                            print(f"Failed to repair block at index {block_index}")
                    except json.JSONDecodeError as e:
                        print(f"Invalid JSON data in block: {e}")
                else:
                    print(f"Could not obtain valid block from peers for index {block_index}")
        
        
        for peer_host, peer_port in self.peers:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((peer_host, peer_port))
                    
                    request = {
                        'type': 'get_chain',
                        'node_id': self.node_id
                    }
                    s.sendall(json.dumps(request).encode('utf-8'))
                    
                    
                    data = self.receive_all(s)
                    
                    if data:
                        response = json.loads(data.decode('utf-8'))
                        
                        if response['type'] == 'chain_data':
                            self.chain.resolve_conflicts(response['chain'])
                        
            except Exception as e:
                print(f"Failed to sync with peer {peer_host}:{peer_port}: {e}")

    def start_periodic_sync(self):
        
        def sync_task():
            while self.running:
                try:
                    self.sync_with_peers()
                except Exception as e:
                    print(f"Error during sync: {e}")
                time.sleep(30) 
                
        sync_thread = threading.Thread(target=sync_task)
        sync_thread.daemon = True
        sync_thread.start()

    def request_block_from_peers(self, block_index):
        
        for peer_host, peer_port in self.peers:
            try:
                
                    
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    try:
                        s.connect((peer_host, peer_port))
                        print("Connected to peer:", peer_host, peer_port)
                        
                        request = {
                            'type': 'get_block',
                            'block_index': block_index,
                            'node_id': self.node_id
                        }
                        s.sendall(json.dumps(request).encode('utf-8'))

                        raw_response = s.recv(4096).decode('utf-8')
                        try:
                            response = json.loads(raw_response)
                        except json.JSONDecodeError:
                            print(f"Failed to decode JSON response from peer {peer_host}:{peer_port}")
                            return None

                        if response['type'] == 'block_data' and response.get('block'):
                            print("Received block data:", response['block'])
                            temp_block = Block(**response['block'])
                            if (temp_block.hash[:len(HASH_TARGET)] == HASH_TARGET and 
                                temp_block.hash == temp_block.calculate_hash()):
                                return response['block']
                            else:
                                print("Block validation failed for block at index", block_index)
                        else:
                            print(f"No valid block data received from {peer_host}:{peer_port}")
                    
                    except socket.error as e:
                        print(f"Socket error with peer {peer_host}:{peer_port}: {e}")
                    except Exception as e:
                        print(f"Unexpected error with peer {peer_host}:{peer_port}: {e}")

                return None

            except Exception as e:
                print(f"Failed to get block from peer {peer_host}:{peer_port}: {e}")
        
        return None
    
    def multicast_listen(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('', MULTICAST_PORT))
            group = socket.inet_aton(MULTICAST_GROUP)
            mreq = struct.pack('4sL', group, socket.INADDR_ANY)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except OSError as e:
            print(f"[Multicast] Not available on this interface ({e}). Auto-discovery disabled.")
            return  # Node still works — peers can be added via API

        while self.running:
            try:
                data, address = sock.recvfrom(4096)  # збільшили buffer_size для ключів
                message = json.loads(data.decode('utf-8'))

                if message.get('node_id') == self.node_id:
                    continue

                peer_id   = message.get('node_id')
                peer_host = address[0]
                peer_port = message.get('port')
                peer_info = (peer_host, peer_port)

                if peer_info not in self.peers:
                    self.peers.append(peer_info)
                    print(f"[P2P] New peer discovered: {peer_id} at {peer_host}:{peer_port}")
                    threading.Thread(target=self.sync_with_peers, daemon=True).start()

                # Зберігаємо публічний ключ піра, якщо він присутній в оголошенні
                pub_key_pem = message.get('public_key')
                if peer_id and pub_key_pem:
                    key_path = f"public_key_{peer_id}.pem"
                    if not os.path.exists(key_path):
                        with open(key_path, 'w') as f:
                            f.write(pub_key_pem)
                        print(f"[P2P] Saved public key for {peer_id}")

            except Exception as e:
                if self.running:
                    print(f"Multicast listen error: {e}")
        sock.close()

    def multicast_announce(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

        # Додаємо публічний ключ до оголошення (реальний P2P обмін ключами)
        pub_key_pem = None
        key_path = f"public_key_{self.node_id}.pem"
        if os.path.exists(key_path):
            with open(key_path, 'r') as f:
                pub_key_pem = f.read()

        message = {
            'type':       'node_announcement',
            'node_id':    self.node_id,
            'host':       self.host,
            'port':       self.port,
            'public_key': pub_key_pem,  # <-- ключ передається автоматично
        }

        try:
            payload = json.dumps(message).encode('utf-8')
            sock.sendto(payload, (MULTICAST_GROUP, MULTICAST_PORT))
        except OSError:
            pass  # Multicast not available on this network — silently ignore
        except Exception as e:
            print(f"Multicast announce error: {e}")
        finally:
            sock.close()

    def periodic_multicast_announce(self):
        while self.running:
            self.multicast_announce()
            
            new_peer_added = False
            for peer in self._get_file_transfer_peers():
                if peer not in self.peers:
                    self.peers.append(peer)
                    print(f"[P2P] Discovered peer via HTTP: {peer[0]}:{peer[1]}")
                    new_peer_added = True
            
            if new_peer_added:
                threading.Thread(target=self.sync_with_peers, daemon=True).start()
            time.sleep(10)  

    def _get_file_transfer_peers(self):
        discovery_peers = NetworkConfig.get_peers(self.node_id)
        
        filtered_peers = []
        for host, port in discovery_peers:
            file_transfer_port = NetworkConfig._discovery.get_file_transfer_port(port)
            # Filter ourselves out ONLY if both host (IP) and port match
            is_own_host = (host == self.host or host == "127.0.0.1" or host == "localhost")
            if is_own_host and file_transfer_port == self.port:
                print(f"Skipping own port: {host}:{file_transfer_port}")
                continue
            filtered_peers.append((host, file_transfer_port))
        
        return filtered_peers
    
    def receive_all(self, sock, chunk_size=4096):
        
        data = []
        while True:
            chunk = sock.recv(chunk_size)
            if not chunk:
                break
            data.append(chunk)
        return b''.join(data)