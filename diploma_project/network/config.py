from network.discovery import NetworkDiscovery
import json

class NetworkConfig:
    _discovery = None  
    
    @classmethod
    def initialize(cls, node_id: str):
        print(f"[*] Initializing NetworkConfig for {node_id}...", flush=True)
        if cls._discovery is None:
            cls._discovery = NetworkDiscovery()  
        
        cls._discovery.initialize_node(node_id)
        # Отримуємо призначений порт
        addr = cls._discovery.nodes.get(node_id)
        if addr:
            print(f"[*] NetworkConfig ready. Node {node_id} is on port {addr[1]}", flush=True)
        else:
            print(f"[!] Warning: Node {node_id} not found in discovery after initialization!", flush=True)

    @classmethod
    def get_node_info(cls, node_id: str):
        if not cls._discovery:
            raise RuntimeError("NetworkConfig not initialized. Call initialize() first.")
        
        # Повертаємо саме той порт, який був призначений в initialize_node
        if node_id in cls._discovery.nodes:
            return cls._discovery.nodes[node_id]
        
        # Якщо вузла немає (що дивно), генеруємо помилку або повертаємо хоч щось
        return cls._discovery.my_ip, cls._discovery.DISCOVERY_PORT

    @classmethod
    def get_node_id_by_transfer_addr(cls, host, transfer_port):
        if not cls._discovery:
            return None
        discovery_port = transfer_port - cls._discovery.FILE_TRANSFER_PORT_OFFSET
        for nid, addr in cls._discovery.nodes.items():
            if addr[1] == discovery_port and (addr[0] == host or addr[0] == "127.0.0.1" or host == "127.0.0.1"):
                return nid
        return None
    
    @classmethod
    def get_peers(cls, node_id):
        try:
            if not cls._discovery:
                raise RuntimeError("NetworkConfig not initialized. Call initialize() first.")
                
            return cls._discovery.get_peers(node_id)
        except Exception as e:
            print(f"Error getting peers for {node_id}: {e}")
            raise
    
   
    
    @classmethod
    def validate_peer(cls, host, port):
        
        try:
            if not isinstance(host, str) or not host:
                return False
                
            if not isinstance(port, int) or port < 1 or port > 65535:
                return False
                
            
            parts = host.split('.')
            if len(parts) != 4:
                return False
                
            for part in parts:
                if not part.isdigit() or not 0 <= int(part) <= 255:
                    return False
                    
            return True
            
        except Exception:
            return False