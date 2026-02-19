""" 
Dentro de este archivo se define la unidad fundamental de la cadena, 
los bloques que la componen. Es sobre estos bloques sobre los que se ejecuta 
el consenso. Dentro de cada uno de ellos se guardan las transacciones aceptadas 
y validadas previamente por la red, y contienen el hash del bloque anterior 
para poder ir formando la cadena ordenadamente. Block actúa como puente entre 
consenso, criptografía e impacto económico en el estado global del sistema. 
"""

from __future__ import annotations

import json
import time
import hashlib
from typing import List, Dict, Any, Optional

from transaction import Transaction
from crypto import sign_message, verify_signature


class Block:
    """
    Representa un bloque dentro del blockchain.
    Un bloque contiene transacciones y metadatos, y está firmado por el nodo proponente.
    """

    def __init__(
        self,
        index: int,
        prev_hash: str,
        transactions: List[Transaction], 
        proposer: str,
        timestamp: Optional[int] = None,
        signature: Optional[bytes] = None,
        signature_scheme: str = "ed25519",
        block_hash: Optional[str] = None
    ) -> None:
        
        self.index: int = index #posición del bloque en la cadena 
        self.prev_hash: str = prev_hash # hash del bloque anterior 
        self.transactions: List[Transaction] = transactions #lista de todas las transacciones dentro del bloque 
        self.proposer: str = proposer #identificador de quien ha sido el nodo que ha propuesto este bloque 
        self.timestamp: int = timestamp if timestamp is not None else int(time.time()) #momeno de creación del bloque 

        # Se rellenan cuando el bloque se firma
        self.signature: Optional[bytes] = signature #firma criptográfica del bloque (hecha por el proposer)
        self.signature_scheme: str = signature_scheme #con que firma se ha firmado este bloque 

        # Hash del bloque (se calcula después de firmar)
        self.hash: Optional[str] = block_hash

    def to_dict(self, include_hash: bool = True) -> Dict[str, Any]:
        """ 
        Converte un bloque a diccionario serializable para poder mandarlo mediante HTTP. 
        Estp es necesario para la propagación de bloques entre nodos para distintas fases del proceso 
        del consenso (api + tendermint_handler). Además nos permite incluir las trnasacciones del bloque para 
        poder almacenarlo correctamente
        """
        tx_list = [tx.to_dict() for tx in self.transactions]

        signature = self.signature
        if isinstance(signature, (bytes, bytearray)):
            signature = signature.hex() #Se convierte a hex porque JSON no puede transportar bytes

        block_data: Dict[str, Any] = {
            "index": self.index,
            "timestamp": self.timestamp,
            "prev_hash": self.prev_hash,
            "transactions": tx_list,
            "proposer": self.proposer,
            "signature": signature,
            "signature_scheme": self.signature_scheme,
        }

        if include_hash:
            block_data["hash"] = self.hash

        return block_data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Block:
        """ 
        Recibe un dict con los datos de un bloque y lo convierte en un objeto Block (al que se le pueden aplicar todas sus funciones)
        """
        transactions = [
            Transaction.from_dict(tx) for tx in data.get("transactions", [])
        ]

        signature = data.get("signature")
        if isinstance(signature, str):
            signature = bytes.fromhex(signature) #pasa la firma de hex a bytes 

        return cls(
            index=data["index"],
            prev_hash=data["prev_hash"],
            transactions=transactions,
            proposer=data["proposer"],
            timestamp=data.get("timestamp"),
            signature=signature,
            signature_scheme=data.get("signature_scheme", "ed25519"),
            block_hash=data.get("hash"),
        )

    def to_json(self) -> str:
        """ 
        Convertir bloque a JSON 
        """
        return json.dumps(self.to_dict(), indent=4)


    """
    Es importante separar estos conceptos para no entrar en un círculo vicioso: 
    Por un lado tenemos la firma del bloque, que prueba quién lo propuso y que el contenido no ha sido modificado
    Por el otro lado tenemos el hash del bloque, que es el identificador del bloque y se utiliza para encadenar los 
    distintos bloques entre sí. 
    De esta manera como el hash se calcula después de que el bloque se haya firmado, si hay cualquier cambio en el 
    interior del bloque el hash se verá modificado y es facil de identificar el error. 
    """
    def compute_message(self) -> bytes:
        """
        Construye el mensaje que se friam cuando el nodo proponente firma un bloque. 
        Este mensje se construye priemro pasando todos los datos del bloque, menos el hash, a un diccionario, 
        luego se serializa dicho diccionario y finalmente se pasa a bytes, para que lo firme el algoritmo seleccionado. 
        Esto 
        Construye un mensaje para firmar el bloque
        El mensaje que se firma es el hash del bloque sin firma ni hash final  
        """
        block_dict = self.to_dict(include_hash=False)
        block_str = json.dumps(block_dict, sort_keys=True)
        return block_str.encode("utf-8")  # bytes

    def compute_hash(self) -> str:
        """
        Tras la firma del bloque se calcula su hash que es un resumen de todo el contenido del bloque, 
        incluida su firma, calculado mediante SHA-256. 
    
        """
        block_dict = self.to_dict(include_hash=False)
        block_str = json.dumps(block_dict, sort_keys=True)
        return hashlib.sha256(block_str.encode("utf-8")).hexdigest()

    def sign_block(self, private_key: bytes) -> None:
        """ 
        Firma el bloque con Ed25519 
        """
        message = self.compute_message()
        signature = sign_message(message, private_key, self.signature_scheme)
        self.signature = signature

        # Tras firmarlo, calculamos el hash final del bloque
        self.hash = self.compute_hash()

    
    def verify_block(self, public_key: bytes) -> bool:
        """ 
        Verifica que la firma y el hash del bloque son válidos
        """
        message = self.compute_message()
        if not verify_signature( message, self.signature, public_key, self.signature_scheme ):
            return False

        expected_hash = self.compute_hash()
        if expected_hash != self.hash:
            return False

        return True

    def is_valid_structure(self) -> bool:
        """ 
        Validación básica de la estructura (sin firmas ni hashes ni balances -> todo esto se hace en blockchain)
        """
        if self.index < 0:
            return False
        if not isinstance(self.transactions, list):
            return False
        if not self.proposer:
            return False
        if not isinstance(self.timestamp, int):
            return False
        return True

    def __repr__(self) -> str:
        return (
            f"Block(index={self.index}, txs={len(self.transactions)}, "
            f"proposer={self.proposer})"
        )
