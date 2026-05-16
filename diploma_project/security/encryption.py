"""
Шифрування файлів для захищеного файлообміну.

Схема:
  - AES-256-GCM  для шифрування вмісту файлу
  - RSA-OAEP/SHA-256 для захищеного обміну AES-ключем
"""
import os
import base64

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey


# ---------- AES-256-GCM -------------------------------------------------------

def generate_aes_key() -> bytes:
    """Згенерувати 256-бітний AES-ключ."""
    return os.urandom(32)


def encrypt_data(data: bytes, aes_key: bytes) -> bytes:
    """
    Зашифрувати bytes за допомогою AES-256-GCM.
    Повертає: nonce (12 байт) || ciphertext+tag
    """
    nonce = os.urandom(12)
    ciphertext = AESGCM(aes_key).encrypt(nonce, data, None)
    return nonce + ciphertext


def decrypt_data(encrypted: bytes, aes_key: bytes) -> bytes:
    """
    Розшифрувати bytes (формат: nonce || ciphertext+tag).
    Кидає виняток, якщо цілісність порушена.
    """
    nonce, ciphertext = encrypted[:12], encrypted[12:]
    return AESGCM(aes_key).decrypt(nonce, ciphertext, None)


def encrypt_file(file_path: str, aes_key: bytes) -> bytes:
    """Прочитати файл і повернути зашифровані дані."""
    with open(file_path, "rb") as f:
        return encrypt_data(f.read(), aes_key)


def decrypt_to_file(encrypted: bytes, aes_key: bytes, out_path: str) -> None:
    """Розшифрувати дані і записати у файл."""
    plaintext = decrypt_data(encrypted, aes_key)
    with open(out_path, "wb") as f:
        f.write(plaintext)


# ---------- RSA OAEP (обмін ключем) ------------------------------------------

_OAEP = asym_padding.OAEP(
    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
    algorithm=hashes.SHA256(),
    label=None,
)


def wrap_aes_key(aes_key: bytes, rsa_public_key: RSAPublicKey) -> str:
    """
    Зашифрувати AES-ключ публічним RSA-ключем отримувача.
    Повертає base64-рядок для передачі у метаданих.
    """
    encrypted = rsa_public_key.encrypt(aes_key, _OAEP)
    return base64.b64encode(encrypted).decode("utf-8")


def unwrap_aes_key(wrapped_b64: str, rsa_private_key: RSAPrivateKey) -> bytes:
    """
    Розшифрувати AES-ключ власним RSA-приватним ключем.
    """
    encrypted = base64.b64decode(wrapped_b64)
    return rsa_private_key.decrypt(encrypted, _OAEP)
