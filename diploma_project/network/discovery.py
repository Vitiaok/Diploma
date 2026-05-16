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


    def discover_nodes(self) -> Dict[str, Tuple[str, int]]:
        """Scan the network for other blockchain nodes."""
        
        network_prefix = '.'.join(self.my_ip.split('.')[:-1]) + '.'
        
        discovered_nodes = {}
        
        def try_connect(ip: str, port: int):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5)  
                    s.connect((ip, port))
                    
                    
                    request = {
                        'type': 'discovery',
                        'sender_ip': self.my_ip
                    }
                    s.sendall(json.dumps(request).encode('utf-8'))
                    
                    
                    response = json.loads(s.recv(1024).decode('utf-8'))
                    if response.get('type') == 'discovery_response':
                        node_id = response.get('node_id')
                        discovered_nodes[node_id] = (ip, port)
                        
                        
            except (socket.timeout, ConnectionRefusedError):
                pass
            except Exception as e:
                print(f"Error scanning {ip}:{port}: {e}")

       
        threads = []
        for i in range(1, 255):  
            ip = network_prefix + str(i)
            if ip != self.my_ip:  
                for port_offset in range(self.MAX_NODES):
                    port = self.DISCOVERY_PORT + port_offset
                    thread = threading.Thread(target=try_connect, args=(ip, port))
                    thread.start()
                    threads.append(thread)
        
        
        for thread in threads:
            thread.join()
            
        return discovered_nodes

    def start_discovery_server(self, node_id: str):
       
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
      
        for port_offset in range(self.MAX_NODES):
            try:
                port = self.DISCOVERY_PORT + port_offset
                server_socket.bind((self.my_ip, port))
                self.nodes[node_id] = (self.my_ip, port)
                break
            except OSError:
                continue
        
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