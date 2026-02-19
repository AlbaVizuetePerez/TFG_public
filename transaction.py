""" 
En este archivo se encuentra la definición de las transacciones, que son 
la unidad minada de transferencia de valor en la cadena. Cada una delegas 
representa una transacción de saldo entre una cuenta emisora y una receptora 
(blockchain basado en un modelo de cuentas). En ellas une criptografía 
(para la firma y su verificación), el uso de la API (para la serializacion), 
y un estado económico (gestionado a través de balances). 
La seguridad de estas transacciones se garantiza mediante un esquema de firma. 
El mensaje criptográfico que se firma se construye de forma determinista a partir de 
los campos sendero, receiver, amount y timestamp; cualquier modificación de estos campos 
hace inválida a la transacción. 

"""

from __future__ import annotations
import json
import time
from typing import Optional, Dict, Any

from crypto import sign_message, verify_signature


class Transaction:
    """
    Representa una transacción firmada entre bancos dentro del modelo de cuentas.
    """

    def __init__(
        self,
        sender: str, 
        receiver: str, 
        amount: int,
        timestamp: Optional[int] = None, 
        public_key: Optional[bytes] = None, 
        signature: Optional[bytes] = None,
        signature_scheme: Optional[str] = None 
    ) -> None:
        
        self.sender: str = sender #identificador del emisor de la transacción (banco001, banco 002,..)
        self.receiver: str = receiver #identificador del receptor de esa transacción (banco001, banco002,..)
        self.amount: int = amount #cantidad enviada
        
        #los siguientes parámetros se pueden pasar más adelante
        # Si no se da timestamp, usamos tiempo actual
        self.timestamp: int = timestamp if timestamp is not None else round(time.time()) #momento cuanto se crea/firma 

        # Estos campos se rellenan tras firmar
        self.public_key: Optional[bytes] = public_key #clave pública del firmante 
        self.signature: Optional[bytes] = signature #firma del mensaje 
        self.signature_scheme: Optional[str] = signature_scheme #indica el tipo de algoritmo (dilithium ó ed25519)
    
    
    def to_dict(self) -> Dict[str, Any]:
        """ 
        Convierte la transaccion a diccionario serializable para poder mandarse mediante HTTP
        Esto es necesario para cuando un usuario envía una transacción (API), para la propagación de las
        transacciones entre nodos (tendermint_hadler) y para poder incluir las transacciones dentro de 
        cada bloque (block) y se puedan mandar por red los bloques con ellas dentro. 
        """
        pk = self.public_key
        sig = self.signature
        if isinstance(pk, (bytes, bytearray)):
            pk = pk.hex() # Se convierte a hex porque JSON no puede transportar bytes, y hex es una forma estándar, segura y reversible (bytes.fromhex()) de hacerlo en sistemas criptográficos.
        if isinstance(sig, (bytes, bytearray)):
            sig = sig.hex()
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "amount": self.amount,
            "timestamp": self.timestamp,
            "public_key": pk,
            "signature": sig,
            "signature_scheme": self.signature_scheme
        }

    def to_json(self) -> str:
        """ 
        Convierte la transacción a JSON para enviar por API REST
        """
        return json.dumps(self.to_dict())

    
    def compute_message(self) -> bytes: #devuelve bytes para que el mensaje a firmar sea siempre en bytes (mantenemos un formato estable)
        """
        Construye el mensaje que se firma, que es el que 
        realmente se firma con EdDSA/Dilithium.
        """
        msg = f"{self.sender}|{self.receiver}|{self.amount}|{self.timestamp}"
        return msg.encode("utf-8") 

    def sign_old(self, private_key: bytes, public_key: bytes, scheme: str) -> None:
        """ 
        firma la transacción con una clave privada y el esquema elegido (ed25519 ó dilithium)
        """
        message = self.compute_message()
        signature = sign_message(message, private_key, scheme)

        self.signature = signature
        self.public_key = public_key
        self.signature_scheme = scheme
        
    def sign(self, private_key, public_key, scheme):
        """
        Firma la transacción a través del esquema elegido (ed25519 o dilithium, con una clave privada. 
        Es importante que se firme antes de hacer POST sobre esa transacción para que se considere verificable. 
        """
        message = self.compute_message()

        if scheme == "dilithium3":
            signature = private_key.sign(message)   # aquí private_key es el signer de dilithium
        else:
            signature = sign_message(message, private_key, scheme)

        self.signature = signature
        self.public_key = public_key
        self.signature_scheme = scheme

    """
    Separamos dos ideas de validación, por un lado con verify() verificamos la autenticidad 
    criptográfica; y luego por otro lado mediante is_well_formed() verificamos si el formato y los datos 
    son correctos y coherentes   
    """
    def verify(self) -> bool: 
        """ 
        Verifica la firma a través de la clave pública y el mensaje
        """
        if not self.signature or not self.public_key:
            return False
        
        message = self.compute_message()
        return verify_signature( message, self.signature, self.public_key, self.signature_scheme )

    def is_well_formed(self) -> bool:
        """ 
        Validación del formato y los datos, no verifica la firma 
        Responde a la pregunta de si esa transacción tiene sentido como operación
        """
        if self.amount <= 0:
            return False
        if self.sender == self.receiver:
            return False
        if not isinstance(self.sender, str) or not isinstance(self.receiver, str):
            return False
        return True

    def __repr__(self) -> str:
        return (
            f"Transaction({self.sender} -> {self.receiver}, "
            f"amount={self.amount}, scheme={self.signature_scheme})"
        )
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Transaction:
        """ 
        Recibe un dict con los datos de una transacción y lo convierte en un 
        objeto Transaction (que se puede firmar, es lógico, se puede verificar,...)
        """
        return cls(
            sender=data["sender"],
            receiver=data["receiver"],
            amount=data["amount"],
            timestamp=data.get("timestamp"),
            public_key=bytes.fromhex(data["public_key"]) if data.get("public_key") else None,
            signature=bytes.fromhex(data["signature"]) if data.get("signature") else None,
            signature_scheme=data.get("signature_scheme"),
        )
