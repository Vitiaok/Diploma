import json
import threading
import datetime as date
from blockchain.block import Block
from blockchain.keys import sign_data
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
import base64


HASH_TARGET = "00000"
BLOCKCHAIN_FILE = "blockchain.json"
REQUIRED_VALIDATIONS = 1

class Chain:
    def __init__(self):
        self.blockchain = []
        self.pending_blocks = {}
        self.validations = {}
        self.lock = threading.RLock()
        self.load_chain()

    def create_block(self, data, private_key):
        
        
        if len(self.blockchain) == 0:
            previous_hash = "0" * 64 
        else:
            previous_block = self.blockchain[-1]
            previous_hash = previous_block.hash

       
        new_block = Block(
            len(self.blockchain),
            date.datetime.now().isoformat(),
            data,
            previous_hash  
        )
    
        
        new_block.hash = self.proof_of_work(new_block)

        
        signature = sign_data(private_key, new_block.hash)

        new_block.signature = signature

        block_id = new_block.hash
        with self.lock:
            self.pending_blocks[block_id] = new_block
            self.validations[block_id] = set()

        return new_block

    def proof_of_work(self, block):
        
        while block.hash[:len(HASH_TARGET)] != HASH_TARGET:
            block.nonce += 1
            block.hash = block.calculate_hash()
        return block.hash

    def validate_block_signature(self, block, validator_id):
        
        try:
        
            public_key_path = f"public_key_{validator_id}.pem"
            with open(public_key_path, "rb") as key_file:
                public_key = serialization.load_pem_public_key(
                    key_file.read()
                )

            
            signature_bytes = base64.b64decode(block.signature)

            
            try:
                public_key.verify(
                    signature_bytes,
                    block.hash.encode('utf-8'),
                    padding.PKCS1v15(),
                    hashes.SHA256()
                )
                return True, "valid_signature"
            except InvalidSignature:
                print(f"Invalid signature for block from validator {validator_id}")
                return False, "invalid_signature"

        except Exception as e:
            print(f"Error validating signature: {e}")
            return False, f"signature_error: {str(e)}"

    def validate_block(self, block, validator_id):
        
        block_id = block.hash

        
        is_valid, reason = self.is_valid_block(block)
        if not is_valid:
            print(f"Block failed basic validation: {reason}")
            return False, reason

        is_sig_valid, sig_reason = self.validate_block_signature(block, validator_id)
        if not is_sig_valid:
            print(f"Block signature validation failed: {sig_reason}")
            return False, sig_reason

        with self.lock:
            if block_id not in self.pending_blocks:
                self.pending_blocks[block_id] = block
                self.validations[block_id] = set()

            self.validations[block_id].add(validator_id)
            print(f"Current validations for block {block_id}: {self.validations[block_id]}")
            
            if len(self.validations[block_id]) >= REQUIRED_VALIDATIONS:
                self.add_validated_block(block)
                print(f"Block {block_id} has been validated and added to the chain")
                del self.pending_blocks[block_id]
                del self.validations[block_id]
                return True, "validated"

        return False, "insufficient_validations"

    def is_valid_block(self, block):
        
        if len(self.blockchain) > 0:
            if block.previous_hash != self.blockchain[-1].hash:
                print(f"Previous hash does not match: expected {self.blockchain[-1].hash}, got {block.previous_hash}")
                return False, f"previous_hash_mismatch (expected {self.blockchain[-1].hash}, got {block.previous_hash})"

        
        if block.hash != block.calculate_hash():
            print("Hash calculation mismatch")
            return False, "hash_calculation_mismatch"

        
        if block.hash[:len(HASH_TARGET)] != HASH_TARGET:
            print("Hash does not meet target difficulty")
            return False, "insufficient_difficulty"

       
        if block.signature is None:
            print("Block has no signature")
            return False, "missing_signature"

        return True, "valid"

    def add_validated_block(self, block):
        
        with self.lock:
            self.blockchain.append(block)
        self.save_chain()


    def save_chain(self):
        
        with open(BLOCKCHAIN_FILE, 'w') as f:
            json.dump([block.dict for block in self.blockchain], f, indent=4, sort_keys=True)
        print(f"Blockchain saved to {BLOCKCHAIN_FILE}")

    def load_chain(self):
        
        try:
            with open(BLOCKCHAIN_FILE, 'r') as f:
                chain_data = json.load(f)
                self.blockchain = [Block(**block) for block in chain_data]

                
                for i in range(1, len(self.blockchain)):
                    if self.blockchain[i].previous_hash != self.blockchain[i - 1].hash:
                        print(f"Error: Block {i} has incorrect previous hash.")
                        break

            
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print("No blockchain found or corrupted blockchain file, starting fresh.")

    def get_chain(self):
        
        return self.blockchain

    def remove_block_by_index(self, index=None):
        """
        Якщо передано індекс, видаляє блок за цим індексом.
        Якщо індекс не передано (None), очищає весь блокчейн.
        """
        if index is None:
            with self.lock:
                self.blockchain = []  # Очищаємо весь ланцюг
                self.save_chain()  # Зберігаємо порожній ланцюг у файл
            print("Весь блокчейн було видалено.")
        elif 0 <= index < len(self.blockchain):
            with self.lock:
                del self.blockchain[index]  # Видаляємо блок за індексом
                self.save_chain()  # Зберігаємо зміни
            print(f"Блок #{index} було видалено.")
        else:
            print(f"Блок з індексом {index} не існує.")


    def get_block_by_hash(self, block_hash):
        
        for block in self.blockchain:
            if block.hash == block_hash:
                return block
        return None
    
    def verify_chain_integrity(self):
        
        invalid_blocks = []
        
        if len(self.blockchain) == 0:
            return True, invalid_blocks
            
        for i in range(len(self.blockchain)):
            current_block = self.blockchain[i]
            validation_errors = []
            
            
            if i > 0:
                previous_block = self.blockchain[i-1]
                if current_block.previous_hash != previous_block.hash:
                    validation_errors.append('previous_hash_mismatch')
                
            
            if current_block.hash != current_block.calculate_hash():
                validation_errors.append('hash_mismatch')
                
            
            if current_block.hash[:len(HASH_TARGET)] != HASH_TARGET:
                validation_errors.append('invalid_proof_of_work')
                
            if validation_errors:
                invalid_blocks.append({
                    'index': i,
                    'block_hash': current_block.hash,
                    'errors': validation_errors
                })
        
        return len(invalid_blocks) == 0, invalid_blocks

    def repair_block(self, block_index, correct_block_data):
        
        if 0 <= block_index < len(self.blockchain):
            correct_block = Block(**correct_block_data)
            
            
            if (correct_block.hash[:len(HASH_TARGET)] == HASH_TARGET and 
                correct_block.hash == correct_block.calculate_hash()):
                
                
                self.blockchain[block_index] = correct_block
                for i in range(block_index + 1, len(self.blockchain)):
                    self.blockchain[i].previous_hash = self.blockchain[i-1].hash
                    self.blockchain[i].hash = self.blockchain[i].calculate_hash()
                
                self.save_chain()
                return True
        return False

    def get_chain_snapshot(self):
        
        return {
            'length': len(self.blockchain),
            'latest_hash': self.blockchain[-1].hash if self.blockchain else None,
            'blocks': [block.dict for block in self.blockchain],
            'block_hashes': [block.hash for block in self.blockchain]
        }

    def resolve_conflicts(self, peer_chain_data):
        
        peer_blocks = [Block(**block_data) for block_data in peer_chain_data['blocks']]
        peer_hashes = peer_chain_data['block_hashes']
        
        
        temp_chain = Chain()
        temp_chain.blockchain = peer_blocks
        is_valid, _ = temp_chain.verify_chain_integrity()
        
        if not is_valid:
            print("Received chain is invalid")
            return False

        
        local_hashes = [block.hash for block in self.blockchain]
        
        
        divergence_point = -1
        for i in range(min(len(local_hashes), len(peer_hashes))):
            if local_hashes[i] != peer_hashes[i]:
                divergence_point = i
                break
        
        if divergence_point != -1:
            print(f"Found chain divergence at block {divergence_point}")
            
            if len(peer_blocks) >= len(self.blockchain):
                
                self.blockchain = self.blockchain[:divergence_point]
                
                self.blockchain.extend(peer_blocks[divergence_point:])
                self.save_chain()
                print(f"Chain has been fixed from block {divergence_point}")
                return True
        
        return False

    def force_chain_sync(self, peer_chain_data):
        
        peer_blocks = [Block(**block_data) for block_data in peer_chain_data['blocks']]
        
        
        temp_chain = Chain()
        temp_chain.blockchain = peer_blocks
        is_valid, _ = temp_chain.verify_chain_integrity()
        
        if is_valid:
            self.blockchain = peer_blocks
            self.save_chain()
            print("Chain has been force synchronized with peer data")
            return True
        return False
    
    