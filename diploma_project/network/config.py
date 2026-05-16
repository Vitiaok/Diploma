from network.discovery import NetworkDiscovery
import json

class NetworkConfig:
    _discovery = None  
    
    @classmethod
    def initialize(cls, node_id):
        
        if cls._discovery is None:
            cls._discovery = NetworkDiscovery()  
            try:
                cls._discovery.start(node_id)
            except Exception as e:
                print(f"Error initializing network discovery: {e}")
                raise
    
    @classmethod
    def get_node_info(cls, node_id):
        
        try:
            if not cls._discovery:
                raise RuntimeError("NetworkConfig not initialized. Call initialize() first.")
                
            if node_id in cls._discovery.nodes:
                return cls._discovery.nodes[node_id]
            
            
            return cls._discovery._get_my_ip(), cls._discovery.DISCOVERY_PORT
            
        except Exception as e:
            print(f"Error getting node info for {node_id}: {e}")
            raise
    
    @classmethod
    def get_peers(cls, node_id):
        
        try:
            if not cls._discovery:
                raise RuntimeError("NetworkConfig not initialized. Call initialize() first.")
                
            all_peers = cls._discovery.get_peers(node_id)
            
            own_ip = cls._discovery._get_my_ip()
            
            
            filtered_peers = [
                (host, port) for host, port in all_peers 
                if host != own_ip and 
                host != 'localhost' and 
                host != '127.0.0.1'
            ]
            
            return filtered_peers
            
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