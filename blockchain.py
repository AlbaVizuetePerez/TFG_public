""" 
La clase Blockchain constituye el núcleo lógico del sistema, es responsable 
de mantener la cadena de bloques local de cada nodo, definir qué bloque y qué 
transacciones son aceptadas con válidos, validar su coherencia y coordinar la 
aplicación de transiciones de estado derivadas del consenso. Es decir, la clase 
definida dentro de este archivo es quien decide qué información asa a formar 
parte de la verdad compartida del nodo. Así cada nodo conserva soberanía sobre 
su cadena local, validando de nuevo toda la información recibida antes de 
aceptarla y aplicarla.
"""
from __future__ import annotations

import json
from typing import List, Dict, Any

from block import Block
from transaction import Transaction
from balances import BalanceManager
import hashlib


class Blockchain:
    """
    Clase principal que gestiona la cadena de bloques, validación y aplicación de bloques.
    """

    def __init__(self, genesis_file_path: str, block_size_limit: int = 4) -> None:
        self.chain: List[Block] = [] #lista de los bloques que forman la candena 
        self.block_size_limit: int = block_size_limit #limite del tamaño del bloque 
        
        #cargar el bloque génesis. Es importante que todos los nodos usen el mismo bloque génesis (bloque inicial)
        with open(genesis_file_path, "r") as f:
            genesis_data: Dict[str, Any] = json.load(f)

        self.genesis_time: int = genesis_data["genesis_time"] # timestamp fijo del bloque génesis
        initial_balances: Dict[str, int] = genesis_data["balances"] # estado económico del incio 

        # Balance manager determinista
        self.balance_manager: BalanceManager = BalanceManager(initial_balances)

        # Crear bloque génesis
        genesis_block: Block = self.create_genesis_block()
        self.chain.append(genesis_block)

    # Bloque génesis
    def create_genesis_block(self) -> Block:
        """ 
        Creación del bloque genésis (bloque inicial)
        Este bloque no proviene del consenso, sirve como ancla de toda la cadena
        Todos los nodos lo generan localmente, pero es idéntico en todos ellos
        """
        genesis = Block(
            index=0, #es el primer bloque de la cadena 
            prev_hash="0", #No hay bloque previo 
            transactions=[],
            proposer="GENESIS",
            timestamp=self.genesis_time,   
            signature=None,
            signature_scheme="ed25519",
            block_hash=None
        )
        genesis.hash = genesis.compute_hash()
        return genesis

    # Obtener último bloque
    def get_last_block(self) -> Block:
        return self.chain[-1]

    
    def add_block(self, block: Block) -> bool:
        """
        Añade un bloque a la cadena tras validarlo por consenso.
        El bloque debe venir firmado y validado por el comité (Tendermint).
        """
        last_block: Block = self.get_last_block()

        # Validación estructural
        if not self.is_valid_new_block(block, last_block):
            print("[Blockchain] Bloque inválido por estructura o encadenamiento.")
            return False

        # Validación de transacciones (aunque las transacciones ya se hayan validado durante el consenso se han de validar de nuevo 
        # Así es como se refleja que cada nodo es soberano y no confía en los demás ciegamente
        if not self.validate_transactions(block):
            print("[Blockchain] Bloque inválido por transacciones no válidas.")
            return False

        # Aplicar transacciones (actualizar balances)
        self.balance_manager.apply_block(block)

        # Añadir bloque a la cadena
        self.chain.append(block)
        return True

    def is_valid_new_block(self, new_block: Block, previous_block: Block) -> bool:
        """
        Valida coherencia entre new_block y previous_block.
        """
        # Índice correcto
        if new_block.index != previous_block.index + 1:
            return False

        # Hash anterior correcto
        if new_block.prev_hash != previous_block.hash:
            return False

        # Estructura básica
        if not new_block.is_valid_structure():
            return False

        # Hash correcto
        expected_hash: str = new_block.compute_hash()
        if new_block.hash != expected_hash:
            return False

        return True

    def validate_transactions(self, block: Block) -> bool:
        """ 
        Validación de transacciones dentro del bloque
        """
        for tx in block.transactions:

            # Validación de firma criptográfica de la transacción
            if not tx.verify():
                print("[Blockchain] Firma inválida en transacción:", tx)
                return False

            # Validación económica: fondos, formato, etc.
            if not self.balance_manager.can_apply_transaction(tx):
                print("[Blockchain] Transacción inválida (fondos/forma):", tx)
                return False

        return True

    def is_valid_chain(self) -> bool:
        """
        Recorre toda la cadena validando encadenamiento, hashes y transacciones.
        """
        if len(self.chain) == 0:
            return True

        for i in range(1, len(self.chain)):
            prev: Block = self.chain[i - 1]
            curr: Block = self.chain[i]

            if not self.is_valid_new_block(curr, prev):
                return False

            if not self.validate_transactions(curr):
                return False

        return True

    # Obtener longitud de la cadena
    def get_chain_length(self) -> int:
        return len(self.chain)

    
    def to_dict(self) -> Dict[str, Any]:
        """ 
        Pasa la cadena completa a un diccionario 
        """
        return {
            "length": self.get_chain_length(), #longitud de la cadena
            "chain": [block.to_dict() for block in self.chain] #lista de bloques serializados
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=4)


    def replace_chain(self, new_chain: Blockchain) -> bool:
        """
        Reemplaza la cadena solo si:
        - la nueva es más larga
        - es completamente válida
        """
        if len(new_chain.chain) <= len(self.chain):
            return False

        if not new_chain.is_valid_chain():
            return False

        self.chain = new_chain.chain
        self.balance_manager = new_chain.balance_manager
        return True
    
    def chain_fingerprint(self) -> str:
        """
        Devuelve un hash que representa toda la cadena.
        Útil para comprobar correctitud entre nodos.
        """
        concat = "".join(block.hash for block in self.chain if block.hash)
        return hashlib.sha256(concat.encode("utf-8")).hexdigest()
