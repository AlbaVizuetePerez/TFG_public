"""
La clase TendermintHandler representa el comportamiento de un nodo 
validador desde el punto de vista del consenso. Es decir, implementa 
el mecanismo de consenso seleccionado para la toma de decisiones en este 
sistema (Tendermint). Coordina la recepción de transacciones, la creación 
y la difusión de propuestas de bloque, la gestión de votaciones en dos fases,
el acuerdo final para un bloque, y la comunicación entre nodos mediante HTTP. 
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple, Any

import requests

from block import Block
from transaction import Transaction
from blockchain import Blockchain


class TendermintHandler:
    """
    Implementación local y completa del consenso estilo Tendermint.
    Un objeto = un nodo/banco
    """

    def __init__(
        self,
        node_id: str, #nombre del nodo (banco001,...)
        private_key: bytes, #clave privada del nodo (solo sirve para firmar bloques)
        public_keys: Dict[str, bytes], #diccionario con las claves públicas de todos los nodos 
        blockchain: Blockchain, #blockchain 
        peers: List[str], #lista de las direcciones de los nodos (peers)
        validator_addrs: Dict[str, str], #diccionario con node_id, dirección (de ese nodo)
        block_size_limit: int = 4, 
        mempool_limit: int = 2000
    ) -> None:
        self.node_id: str = node_id
        self.private_key: bytes = private_key
        self.public_keys: Dict[str, bytes] = public_keys          # dict node_id -> public_key
        self.blockchain: Blockchain = blockchain
        self.peers: List[str] = peers
        self.validator_addrs: Dict[str, str] = validator_addrs
        self.block_size_limit: int = block_size_limit
        self.mempool_limit : int = mempool_limit

        # Estado local
        self.mempool: List[Transaction] = []

        # Estado de consenso
        self.current_height: int = blockchain.get_last_block().index #altura actual de la cadena 

        self.current_round: int = 0 #ronda en la que estamos (no hay timeouts)

        self.proposal: Optional[Block] = None #bloque actual propuesto 
        self.prevotes: Dict[str, bool] = {}     # node_id -> bool, votos en al fase de prevotes
        self.precommits: Dict[str, bool] = {}   # node_id -> bool, votos en al fase de precommits 


    def quorum_size(self) -> int:
        """
        Esta función hace respetar la regla matemática del consenso Tendermint. 
        No hay consenso hasta que no haya ≥ 2/3 votos a favor. 
        """
        n = len(self.public_keys)
        return math.ceil(2 * n / 3) 

    def proposal_id(self) -> Optional[str]:
        """
        Identificador estable de la propuesta:
        hash del bloque SIN firma.
        Se añade en payloads de prevote y precommit para asociar los votos a una propuesta concreta
        """
        if self.proposal is None:
            return None
        return self.proposal.compute_hash()

    # MEMPOOL (sala de espera donde viven las transacciones antes de ser añadidas a un bloque)

    def add_transaction_to_mempool(self, tx):
        """ 
        Almacenamos las transacciones pendientes de añadirse a un bloque 
        """
        if len(self.mempool) >= self.mempool_limit:
            return False #se devuelve false si el mempool llego a su límite 
        self.mempool.append(tx)
        return True


    # FASE DE PROPUESTA DEL BLOQUE (PROPOSE)
    
    def create_proposal(self) -> Optional[Block]: #solo se ejecuta cuando hay transacciones en el mempool y cuando eres el proposer 
        """ 
        Crea una propuesta de bloque a partir de las transacciones pendientes del mempool seleccionando las primeras transacciones (hasta block_size_limit)
        y construye un Block enlazado al último bloque aceptado (prev_hash = last_block.hash). Este bloque será pasado por los procesos del consenso 
        hasta decidirse si es totalmente correcto y se acepta y por tanto se añade a la cadena. 
        """
        if not self.mempool:
            return None

        last_block = self.blockchain.get_last_block()
        txs = self.mempool[:self.block_size_limit]

        block = Block(
            index=last_block.index + 1,
            prev_hash=last_block.hash,
            transactions=txs,
            proposer=self.node_id,
            signature_scheme="ed25519",
        )

        self.proposal = block
        self.prevotes = {}
        self.precommits = {}

        return block

    # FASE DE VALIDACIÓN DE PROPUESTAS (PREVOTE)

    def handle_proposal(self, block: Block) -> bool:
        """
        Recibe una propuesta de bloque y decide su prevote a través de las siguientes comprobaciones.
        """

        # Altura correcta
        if block.index != self.current_height + 1:
            self.prevotes[self.node_id] = False
            return False

        # prev_hash correcto
        last_block = self.blockchain.get_last_block()
        if block.prev_hash != last_block.hash:
            self.prevotes[self.node_id] = False
            return False

        # Estructura válida
        if not block.is_valid_structure():
            self.prevotes[self.node_id] = False
            return False

        # Transacciones válidas
        if not self.blockchain.validate_transactions(block):
            self.prevotes[self.node_id] = False
            return False

        # Guardar propuesta y votar sí
        self.proposal = block
        self.prevotes[self.node_id] = True

        return True

    def handle_prevote(self, voter_id: str, vote: bool) -> bool:
        """
        Procesa un prevote recibido: guarda el voto, cuenta votos afirmativos y comprueba quórum.
        Este método es usado principalmente por el nodo proponente que es quien acumula los votos. 
        """

        if self.proposal is None:
            return False

        self.prevotes[voter_id] = vote

        yes_votes = sum(v for v in self.prevotes.values())
        return yes_votes >= self.quorum_size()

    # FASE DE CONFIRMACIÓN (PRECOMMIT)

    def handle_precommit(self, voter_id: str, vote: bool) -> bool:
        """
        Registra una confirmación recibida (precommit) y comprueba si se alcanza quórum (≥ 2/3).
        La fase de precommit representa el compromiso final de los validadores con la propuesta:
        si se alcanza quórum, el proposer puede ejecutar el compromiso final del bloque (commit).
        """

        if self.proposal is None:
            return False

        self.precommits[voter_id] = vote

        yes_votes = sum(v for v in self.precommits.values())
        return yes_votes >= self.quorum_size()

    # FASE DE COMPROMISO FINAL (COMMIT)

    def commit_block(self) -> bool:
        """
        Commit final del bloque (solo cuando hay quórum de precommits).
        El proposer firma, añade el bloque y lo difunde.
        """

        if self.proposal is None:
            return False

        # Firmar bloque (solo el proposer)
        if self.proposal.proposer == self.node_id:
            self.proposal.sign_block(self.private_key)

        # Añadir bloque a la blockchain local
        success = self.blockchain.add_block(self.proposal)

        if success:
            print(f"[{self.node_id}] Bloque {self.proposal.index} añadido localmente")

            # Difundir bloque comprometido a los peers
            self.broadcast_commit()

            # Limpiar mempool local
            self.mempool = self.mempool[len(self.proposal.transactions):]

            # Actualizar altura
            self.current_height = self.blockchain.get_chain_length()

        # Resetear estado de consenso
        self.proposal = None
        self.prevotes = {}
        self.precommits = {}

        return success

    # RED / HTTP

    def _post( self, peer: str, path: str, payload: Dict[str, Any], timeout: float = 2.0 ) -> Tuple[Optional[int], Optional[Any]]:
        """ 
        Se encarga de mandar mensajes de un nodo a otros a través de una comunicación HTTP entre ellos. 
        Devuelve (status_code, json_response) si la petición tiene éxito; si falla, devuelve (None, None).
        """
        url = f"http://{peer}{path}"
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            return (
                r.status_code,
                r.json() if r.headers.get("content-type", "").startswith("application/json") else None
            )
        except Exception as e:
            print(f"[{self.node_id}] ⚠️ POST falló a {url}: {e}")
            return None, None

    def broadcast_transaction(self, tx: Transaction) -> None:
        """ 
        Propaga una transacción a todos los peers mediante el endpoint /tx (api.py).
        Se utiliza cuando un nodo recibe una transacción y quiere difundirla para que el resto
        la almacene en su mempool. Se envía propagate=False para evitar bucles de propagación.
        """
        payload: Dict[str, Any] = {"tx": tx.to_dict(), "propagate": False}
        for peer in self.peers:
            self._post(peer, "/tx", payload)

    def broadcast_proposal(self) -> None:
        """ 
        Difunde la propuesta de bloque actual a todos los peers (/consensus/propose).
        Se envía el bloque en formato serializable sin hash final, ya que
        en esta fase el bloque aún no está comprometido; será validado y votado por los demás nodos.
        """
        if self.proposal is None:
            return
        payload: Dict[str, Any] = {
            "height": self.proposal.index,
            "round": self.current_round,
            "proposer_id": self.node_id,
            "block": self.proposal.to_dict(include_hash=False)  # sin hash final aún
        }
        for peer in self.peers:
            self._post(peer, "/consensus/propose", payload)

    def send_prevote(self, proposer_id: str, vote_bool: bool) -> None:
        """
        Vota una propuesta y le manda su resultado al nodo proponente (solo el nodo proponente necesita contar los votos)
        """
        payload: Dict[str, Any] = {
            "height": self.proposal.index if self.proposal else None,
            "round": self.current_round,
            "voter_id": self.node_id,
            "vote": vote_bool,
            "proposal_id": self.proposal_id(), #para asociar el voto a una propuesta de bloque concreta 
        }
        proposer_addr = self.validator_addrs[proposer_id]
        self._post(proposer_addr, "/consensus/prevote", payload)

    def send_precommit(self, proposer_id: str, vote_bool: bool = True) -> None:
        """
        Envía la confirmación de este nodo al proponente. 
        """
        payload: Dict[str, Any] = {
            "height": self.proposal.index if self.proposal else None,
            "round": self.current_round,
            "voter_id": self.node_id,
            "vote": vote_bool,
            "proposal_id": self.proposal_id(),
        }
        proposer_addr = self.validator_addrs[proposer_id]
        self._post(proposer_addr, "/consensus/precommit", payload)

    
    def broadcast_commit(self) -> None:
        """
        Difunde el bloque ya firmado y comprometido
        a todos los peers para que lo añadan a su cadena.
        En esta fase el bloque ya está firmado por el proposer y contiene 
        hash final, de modo que cada nodo receptor puede validarlo 
        y añadirlo a su cadena local.
        """
        if self.proposal is None:
            return

        payload: Dict[str, Any] = {
            "block": self.proposal.to_dict(include_hash=True)
        }

        for peer in self.peers:
            self._post(peer, "/consensus/commit", payload)
    
    
    def broadcast_precommit_request(self) -> None:
        """ 
        El nodo proponente pide a todos que manden su confirmación (precommit).
        Se ejecuta cuando el proposer detecta quórum de pre-votos y quiere pasar a la fase de
        confirmación final antes del commit. 
        """
        payload: Dict[str, Any] = {
            "height": self.proposal.index if self.proposal else None,
            "round": self.current_round,
            "proposer_id": self.node_id,
            "proposal_id": self.proposal_id(),
        }
        for peer in self.peers:
            self._post(peer, "/consensus/precommit_request", payload)

    def __repr__(self) -> str:
        return f"TendermintHandler(node={self.node_id})"
