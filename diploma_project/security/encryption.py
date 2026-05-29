import os
import base64

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

CHUNK_SIZE = 8192  


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
    
    nonce = os.urandom(12)
    encryptor = Cipher(
        algorithms.AES(aes_key),
        modes.GCM(nonce),
        backend=default_backend(),
    ).encryptor()

    chunks = []
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            chunks.append(encryptor.update(chunk))

    chunks.append(encryptor.finalize())
    auth_tag = encryptor.tag  # 128-бітний тег автентифікації GCM

    return nonce + b"".join(chunks) + auth_tag


def decrypt_to_file(encrypted: bytes, aes_key: bytes, out_path: str) -> None:
    """
    Розшифрування та запис у файл блоками по 8 КБ (AES-256-GCM).

    Формат вводу: nonce (12 байт) || ciphertext || auth_tag (16 байт)

    Спочатку верифікується auth_tag — лише після успішної перевірки
    цілісності дані записуються у файл. Це захищає від атаки
    "decrypt-then-verify" та підміни шифротексту.
    """
    nonce = encrypted[:12]
    auth_tag = encrypted[-16:]
    ciphertext = encrypted[12:-16]

    decryptor = Cipher(
        algorithms.AES(aes_key),
        modes.GCM(nonce, auth_tag),
        backend=default_backend(),
    ).decryptor()

    with open(out_path, "wb") as out_f:
        offset = 0
        while offset < len(ciphertext):
            chunk = ciphertext[offset: offset + CHUNK_SIZE]
            out_f.write(decryptor.update(chunk))
            offset += CHUNK_SIZE
        out_f.write(decryptor.finalize())  # кидає InvalidTag якщо цілісність порушена


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
