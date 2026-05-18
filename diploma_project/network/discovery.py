import socket
import netifaces
import threading
import json
from typing import Dict, List, Tuple
import time

class NetworkDiscovery:
    DISCOVERY_PORT = 5000  
    MAX_NODES = 10        
    FILE_TRANSFER_PORT_OFFSET = 1000

    def __init__(self):
        self.nodes: Dict[str, Tuple[str, int]] = {}
        self._lock_socket = None
        self.my_ip = self._get_my_ip()
        self.discovery_thread = None
        self.running = True
        

    def _get_my_ip(self) -> str:
        """Отримати IP адресу, пріоритет локальній мережі."""
        try:
            # Спроба отримати адресу через підключення до зовнішнього хоста (не створюючи трафіку)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"


    WEB_PORT = 8080  # Flask port — always open, firewall already allowed it

    def discover_nodes(self) -> Dict[str, Tuple[str, int]]:
        """Scan the LAN for nodes by probing /api/status on port 8080.
        This works even when multicast is blocked, because Flask's port is
        already allowed through Windows Firewall."""
        import urllib.request

        network_prefix = '.'.join(self.my_ip.split('.')[:-1]) + '.'
        discovered_nodes = {}
        lock = threading.Lock()

        def try_http(ip: str):
            if ip == self.my_ip:
                return
            for port in [8080, 8081, 8082]:
                try:
                    url = f"http://{ip}:{port}/api/status"
                    with urllib.request.urlopen(url, timeout=0.8) as resp:
                        data = json.loads(resp.read().decode())
                        node_id   = data.get("node_id")
                        node_host = data.get("host", ip)
                        node_port = data.get("port")   # file-transfer port (e.g. 6000)
                        pub_key   = data.get("public_key")
                        if node_id and node_port:
                            discovery_port = node_port - self.FILE_TRANSFER_PORT_OFFSET
                            with lock:
                                discovered_nodes[node_id] = (node_host, discovery_port)
                            print(f"[Discovery] Found node '{node_id}' at {node_host}:{node_port}")
                            
                            # Save public key for signature validation
                            if pub_key:
                                key_path = f"public_key_{node_id}.pem"
                                if not __import__("os").path.exists(key_path):
                                    with open(key_path, "w") as f:
                                        f.write(pub_key)
                                    print(f"[Discovery] Saved public key for '{node_id}'")
                except Exception:
                    pass  # Host not running a node on this port — expected

        threads = [threading.Thread(target=try_http, args=(network_prefix + str(i),))
                   for i in range(1, 255)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=1.5)

        return discovered_nodes

    def initialize_node(self, node_id: str):
        """Детерміноване призначення портів на основі імені вузла."""
        import re
        name = str(node_id).lower().strip()
        
        # Витягуємо числовий суфікс (node1->0, node2->1, node10->9, etc.)
        digits = re.findall(r'\d+', name)
        if digits:
            offset = (int(digits[-1]) - 1) % self.MAX_NODES
        else:
            # Для довільних імен (alice, laptop, etc.) — хеш від імені
            offset = sum(ord(c) for c in name) % self.MAX_NODES

        discovery_port = self.DISCOVERY_PORT + offset
        transfer_port  = discovery_port + self.FILE_TRANSFER_PORT_OFFSET

        self.nodes[node_id] = (self.my_ip, discovery_port)

        print(f"\n[INIT] Node: '{node_id}' | Offset: {offset}", flush=True)
        print(f"[INIT] Discovery Port: {discovery_port} | Transfer Port: {transfer_port}\n", flush=True)

        # Блокуємо порт виявлення
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('0.0.0.0', discovery_port))
            s.listen(5)
            self._lock_socket = s
        except Exception:
            print(f"[!] Discovery port {discovery_port} already in use.", flush=True)

        discovered = self.discover_nodes()
        self.nodes.update(discovered)

        # Start periodic HTTP scan since app.py calls initialize_node directly
        def periodic_discovery():
            while self.running:
                time.sleep(30)
                new_nodes = self.discover_nodes()
                self.nodes.update(new_nodes)

        discovery_thread = threading.Thread(target=periodic_discovery)
        discovery_thread.daemon = True
        discovery_thread.start()
    def _is_port_available(self, port: int) -> bool:
        """Перевірка чи вільний порт (більше не потрібна в такій формі, але залишимо для сумісності)."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                return s.connect_ex(('127.0.0.1', port)) != 0
        except:
            return True

    def start_discovery_server(self, node_id: str):
        # Використовуємо сокет, створений в initialize_node, якщо він є
        if getattr(self, '_lock_socket', None):
            server_socket = self._lock_socket
        else:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Якщо вузол вже відомий, беремо його порт, інакше дефолтний
            host, port = self.nodes.get(node_id, (self.my_ip, self.DISCOVERY_PORT))
            server_socket.bind((self.my_ip, port))
            server_socket.listen(5)
        

        while self.running:
            try:
                client_socket, addr = server_socket.accept()
                threading.Thread(target=self._handle_discovery_request,
                              args=(client_socket, node_id)).start()
            except Exception as e:
                if self.running:
                    print(f"Discovery server error: {e}")

    def _handle_discovery_request(self, client_socket: socket.socket, node_id: str):
        
        try:
            data = client_socket.recv(1024).decode('utf-8')
            message = json.loads(data)
            
            if message.get('type') == 'discovery':
                response = {
                    'type': 'discovery_response',
                    'node_id': node_id,
                    'port': self.nodes[node_id][1]
                }
                client_socket.sendall(json.dumps(response).encode('utf-8'))
        except Exception as e:
            print(f"Error handling discovery request: {e}")
        finally:
            client_socket.close()

    def start(self, node_id: str):
        """Start the discovery service."""
        
        self.discovery_thread = threading.Thread(target=self.start_discovery_server,
                                              args=(node_id,))
        self.discovery_thread.daemon = True
        self.discovery_thread.start()
        
        
        discovered = self.discover_nodes()
        self.nodes.update(discovered)
        
        
        def periodic_discovery():
            while self.running:
                time.sleep(30)  
                new_nodes = self.discover_nodes()
                self.nodes.update(new_nodes)
        
        discovery_thread = threading.Thread(target=periodic_discovery)
        discovery_thread.daemon = True
        discovery_thread.start()

    def stop(self):
        
        self.running = False

    def get_peers(self, node_id: str) -> List[Tuple[str, int]]:
        
        return [(host, port) for nid, (host, port) in self.nodes.items() 
                if nid != node_id]
    
    @classmethod
    def get_file_transfer_port(cls, discovery_port):
        
        return discovery_port + cls.FILE_TRANSFER_PORT_OFFSET