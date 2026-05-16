import hashlib
import base64
import json
from typing import Dict, Any

class Block:
    def __init__(self, index, timestamp, data, previous_hash, nonce=0, hash=None, signature=None):
        self.index = index
        self.timestamp = timestamp
        self.data = data
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = hash if hash else self.calculate_hash()
        self.signature = self._process_signature(signature)

    def _process_signature(self, signature):
       
        if signature is None:
            return None
        try:
            if isinstance(signature, bytes):
                return base64.b64encode(signature).decode('utf-8')
            elif isinstance(signature, str):
               
                base64.b64decode(signature)  
                return signature
            else:
                return None
        except Exception:
            return None

    def calculate_hash(self):
        
        data_string = (
            str(self.index) +
            self.timestamp +
            json.dumps(self.data, sort_keys=True) +  
            self.previous_hash +
            str(self.nonce)
        )
        return hashlib.sha256(data_string.encode('utf-8')).hexdigest()

    @property
    def dict(self) -> Dict[str, Any]:
        
        return {
            'index': self.index,
            'timestamp': self.timestamp,
            'data': self.data,
            'previous_hash': self.previous_hash,
            'nonce': self.nonce,
            'hash': self.hash,
            'signature': self.signature
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Block':
        
        return cls(
            index=data['index'],
            timestamp=data['timestamp'],
            data=data['data'],
            previous_hash=data['previous_hash'],
            nonce=data['nonce'],
            hash=data['hash'],
            signature=data.get('signature')
        )

    def to_json(self) -> str:
        
        return json.dumps(self.dict, ensure_ascii=False)