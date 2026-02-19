"""
En este archivo se encuentra toda la lógica criptográfica del sistema. 
Proporciona los métodos necesarios para calcular el par de claves privadas 
y públicas, firmar y verificar los mensajes tanto con un algoritmo 
clásico (Ed25519) como con un algoritmo post-cuántico (Dilithium)
"""


from __future__ import annotations

from typing import Optional, Tuple, Any

try:
    import oqs  # type: ignore
    OQS_AVAILABLE: bool = True
except ImportError:
    oqs: Optional[Any] = None
    OQS_AVAILABLE = False

from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError


# CAPA EdDSA (Ed25519)

def generate_eddsa_keypair() -> Tuple[bytes, bytes]:
    """
    Genera un par de claves Ed25519 usando PyNaCl.
    Devuelve (private_key, public_key) en bytes (para mejor transporte y almacenaje)
    """
    sk = SigningKey.generate()
    vk = sk.verify_key

    return sk.encode(), vk.encode()


def eddsa_sign(message: bytes, private_key: bytes) -> bytes:
    """
    Firma un mensaje con EdDSA (Ed25519).
    message: bytes
    private_key: bytes
    """
    sk = SigningKey(private_key)
    signature = sk.sign(message).signature
    return signature


def eddsa_verify(message: bytes, signature: bytes, public_key: bytes) -> bool:
    """
    Verifica firma Ed25519 sobre un mensaje usando solo la clave pública.
    """
    try:
        vk = VerifyKey(public_key)
        vk.verify(message, signature)
        return True
    except BadSignatureError:
        return False


# 2) CAPA Dilithium 

def generate_dilithium_keypair_old() -> Tuple[bytes, bytes]: 
    """
    Genera par de claves Dilithium3 usando OQS.
    Devuelve (private_key, public_key) en bytes.
    """
    if not OQS_AVAILABLE:
        raise RuntimeError("oqs-python no está instalado. No se puede usar Dilithium.")
    with oqs.Signature("Dilithium3") as signer:  # type: ignore[union-attr]
        public_key: bytes = signer.generate_keypair()
        private_key: bytes = signer.export_secret_key()
    return private_key, public_key

def generate_dilithium_keypair() -> Tuple[Any, bytes]:
    """
    Genera par de claves Dilithium3 usando OQS.
    Devuelve (signer, public_key), donde signer es el objeto de OQS que contiene la clave
    secreta internamente y permite firmar directamente
    """
    if not OQS_AVAILABLE:
        raise RuntimeError("oqs-python no está instalado. No se puede usar Dilithium.")

    signer = oqs.Signature("Dilithium3")
    public_key: bytes = signer.generate_keypair()
    return signer, public_key



def dilithium_sign_old_old(message: bytes, private_key: bytes) -> bytes: #Esto usa una version de la API (una version experimental) que no queremos
    """
    Firma post-cuántica con Dilithium3.
    """
    if not OQS_AVAILABLE:
        raise RuntimeError("oqs-python no está instalado. No se puede usar Dilithium.")
    with oqs.Signature("Dilithium3") as signer:  # type: ignore[union-attr]
        signer.import_secret_key(private_key)
        signature: bytes = signer.sign(message)
        return signature
    
def dilithium_sign_old(message: bytes, private_key: bytes) -> bytes:
    if not OQS_AVAILABLE:
        raise RuntimeError("oqs-python no está instalado. No se puede usar Dilithium.")

    with oqs.Signature("Dilithium3") as signer:
        # 🔑 Esta es la clave: el nombre correcto del atributo
        signer.secret_key = private_key
        signature = signer.sign(message)
        return signature

def dilithium_sign(message: bytes, signer: Any) -> bytes:
    """  
    Firma un mensaje (bytes) con Dilithium3 usando el objeto signer de OQS.
    Se usa a través de sign_message() cuando el esquema seleccionado es "dilithium3".
    Permite que Transaction y Block firmen sin conocer detalles internos del algoritmo.
    """
    if not OQS_AVAILABLE:
        raise RuntimeError("oqs-python no está instalado. No se puede usar Dilithium.")

    return signer.sign(message)



def dilithium_verify(message: bytes, signature: bytes, public_key: bytes) -> bool:
    """
    Verifica firma Dilithium3 usando la clave pública.
    """
    if not OQS_AVAILABLE:
        raise RuntimeError("oqs-python no está instalado. No se puede usar Dilithium.")
    with oqs.Signature("Dilithium3") as verifier:  # type: ignore[union-attr]
        try:
            return bool(verifier.verify(message, signature, public_key))
        except Exception:
            return False



def generate_keypair_old(scheme: str) -> Tuple[bytes, bytes]:
   
    if scheme == "ed25519":
        return generate_eddsa_keypair()
    elif scheme == "dilithium3":
        return generate_dilithium_keypair()
    else:
        raise ValueError("Esquema de firma no soportado.")
    
def generate_keypair(scheme: str) -> Tuple[Any, bytes]:
    """
    Crea par de claves según el algoritmo:
    - "ed25519"
    - "dilithium3"
    De esta manera el sistema soporta tanto ed25519 como dilithium 
    """
    if scheme == "ed25519":
        return generate_eddsa_keypair()
    elif scheme == "dilithium3":
        return generate_dilithium_keypair()
    else:
        raise ValueError("Esquema de firma no soportado.")



def sign_message_old(message: bytes, private_key: bytes, scheme: str) -> bytes:
    """
    Firma un mensaje usando el esquema seleccionado.
    """
    if scheme == "ed25519":
        return eddsa_sign(message, private_key)
    elif scheme == "dilithium3":
        return dilithium_sign(message, private_key)
    else:
        raise ValueError("Esquema de firma no soportado.")


def sign_message(message: bytes, private_key: Any, scheme: str) -> bytes:
    """ 
    Interfaz comun para firmar un mensaje con el esquema que haya sido seleccionado. 
    """
    if scheme == "ed25519":
        return eddsa_sign(message, private_key)
    elif scheme == "dilithium3":
        return dilithium_sign(message, private_key)
    else:
        raise ValueError("Esquema de firma no soportado.")



def verify_signature(message: bytes, signature: bytes, public_key: bytes, scheme: str) -> bool:
    """
    Verifica la firma según el algoritmo elegido.
    """
    if scheme == "ed25519":
        return eddsa_verify(message, signature, public_key)
    elif scheme == "dilithium3":
        return dilithium_verify(message, signature, public_key)
    else:
        raise ValueError("Esquema de firma no soportado.")
