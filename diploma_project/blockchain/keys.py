from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import base64
import os
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa

def generate_and_save_keys(node_id):
    
    private_key_filename = f'private_key_{node_id}.pem'
    public_key_filename = f'public_key_{node_id}.pem'
    if os.path.exists(private_key_filename) and os.path.exists(public_key_filename):
        print(f"Keys already exist for node {node_id}. Skipping key generation.")
        return

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    public_key = private_key.public_key()

    with open(private_key_filename, 'wb') as private_file:
        private_file.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
        )

    with open(public_key_filename, 'wb') as public_file:
        public_file.write(
            public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
        )

    print(f"Keys generated and saved for node {node_id}")

def sign_data(private_key, data):
   
    signature = private_key.sign(
        data.encode('utf-8'), 
        padding.PKCS1v15(),  
        hashes.SHA256()  
    )
    
    
    return base64.b64encode(signature).decode('utf-8')