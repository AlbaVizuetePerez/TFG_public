""" 
Dentro de este archivo se expone a cada nodo de la red como un servicio accesible
por HTTP mediante una API REST. u objetivo es permitir tanto la interacción con 
usuarios/clientes (envío de transacciones y consulta de estado) como la comunicación entre 
nodos durante el consenso (propagación de propuestas, votos y commit). Cada endpoint traduce 
datos JSON recibidos por red a objetos internos (Transaction y Block) mediante from_dict, 
valida la información localmente (firmas, coherencia, quórum, etc.) y delega la lógica de 
consenso y actualización del estado en TendermintHandler y Blockchain.
"""

from typing import Any, Dict
from flask import Flask, request, jsonify

from transaction import Transaction
from block import Block
from blockchain import Blockchain
from balances import BalanceManager
from tendermint_handler import TendermintHandler

def create_app(
    blockchain: Blockchain,
    balance_manager: BalanceManager,
    tendermint_node: TendermintHandler
) -> Flask:
    """
    Crea y configura la API REST de un nodo. 
    Recibe infrmación local de Blockchain, BalanceManager y TendermintHandler y devuelve una aplicación
    Flask con distintos enpoints para envío de transacciones, consultas de estado e intercambio de mensajes para 
    el consenso. 
    """

    app: Flask = Flask(__name__)

    # CLIENTE / USUARIO -> Estos endpoints son solo para enviar transacciones y consultar el estado 

    @app.route("/tx", methods=["POST"])
    def new_transaction() -> Any:
        """
        Recibe una transaccion vía HTTP (JSON), la reconstruye como un objeto Transaction y valida
        su firma. Si la firma es correcta, se añade al mempool local y se propaga a los peers para que el 
        resto de nodos también la almacenen.
        """
        data: Dict[str, Any] = request.json or {}

        tx_data: Dict[str, Any] = data.get("tx", data) #permite dos formatos 
        propagate: bool = data.get("propagate", True)

        try:
            tx: Transaction = Transaction.from_dict(tx_data) #convierte los datos en un objeto de tipo Transaction
        except Exception as e:
            return jsonify({
                "error": "Formato de transacción inválido",
                "details": str(e)
            }), 400

        if not tx.verify():
            return jsonify({"error": "Firma inválida"}), 400

        if not tendermint_node.add_transaction_to_mempool(tx):
            return jsonify({"error": "Mempool lleno"}), 400

        if propagate:
            tendermint_node.broadcast_transaction(tx)

        return jsonify({
            "status": "ok",
            "mempool_size": len(tendermint_node.mempool)
        })


    @app.route("/chain", methods=["GET"])
    def get_chain() -> Any: 
        """  
        Devuelve la cadena completa del nodo en formato JSON
        """
        return blockchain.to_json()


    @app.route("/balances", methods=["GET"])
    def get_balances() -> Any: 
        """  
        Permite consultar el estado económico actual del nodo
        """
        return jsonify(balance_manager.snapshot())


    @app.route("/node/info", methods=["GET"])
    def node_info() -> Any: 
        """ 
        Permite ver la información general del nodo
        """ 
        return jsonify({
            "node_id": tendermint_node.node_id,
            "height": blockchain.get_chain_length(),
            "mempool_size": len(tendermint_node.mempool),
            "peers": tendermint_node.peers,
        })

    # CONSENSO — NODO ↔ NODO

    @app.route("/consensus/propose", methods=["POST"])
    def receive_proposal() -> Any:
        """ 
        Recibe una propuesta de bloque enviada por el nodo proponente. Luego delega su validación 
        (TendermintHandler.handle_proposal()). Y envñia el prevote de vuelta al nodo proponente 
        """
        data: Dict[str, Any] = request.json or {}
        print(f">>> [{tendermint_node.node_id}] /consensus/propose recibido")

        try:
            block: Block = Block.from_dict(data["block"]) #reconstruye el bloque como un objeto Block, reconstruyendo así tambien las transacciones como un objeto Transaction
            proposer_id: str = data["proposer_id"]
        except Exception as e:
            return jsonify({
                "accepted": False,
                "error": str(e)
            }), 400

        print(
            f">>> [{tendermint_node.node_id}] "
            f"proposal index={block.index} txs={len(block.transactions)}"
        )

        vote_yes: bool = tendermint_node.handle_proposal(block)
        print(f">>> [{tendermint_node.node_id}] prevote = {vote_yes}")

        tendermint_node.send_prevote(proposer_id, vote_yes)

        return jsonify({
            "accepted": True,
            "prevote": vote_yes
        })


    @app.route("/consensus/prevote", methods=["POST"])
    def receive_prevote() -> Any:
        """
        Recibe los votos de los otros nodos, los acumula y si es el proposer puede solicitar se solicita la fase de
        confirmación (precommit) a los peers mediante broadcast_precommit_request().    
        """
        data: Dict[str, Any] = request.json or {}
        print(f">>> [{tendermint_node.node_id}] /consensus/prevote recibido {data}")

        try:
            voter_id: str = data["voter_id"]
            vote: bool = data["vote"]
        except KeyError:
            return jsonify({"error": "Prevote mal formado"}), 400

        quorum: bool = tendermint_node.handle_prevote(voter_id, vote)
        print(f">>> [{tendermint_node.node_id}] quorum prevote = {quorum}")

        #si soy proposer y hay quórum -> pedir precommits 
        if quorum and tendermint_node.proposal is not None:
            if tendermint_node.proposal.proposer == tendermint_node.node_id:
                print(f">>> [{tendermint_node.node_id}] soy proposer, pidiendo precommits")
                tendermint_node.broadcast_precommit_request()

        return jsonify({ "received": True, "quorum_reached": quorum })


    @app.route("/consensus/precommit_request", methods=["POST"])
    def receive_precommit_request() -> Any:  
        """  
        Recibe una petición del proposer para enviar precommit (confirmación).
        El nodo responde con precommit=True solo si:
        - mantiene la propuesta local almacenada,
        - y su prevote para esa propuesta fue afirmativo.
        En caso contrario envía precommit=False.
        """
        data: Dict[str, Any] = request.json or {}
        print(f">>> [{tendermint_node.node_id}] /consensus/precommit_request recibido")

        try:
            proposer_id: str = data["proposer_id"]
        except KeyError:
            return jsonify({"error": "Precommit request mal formado"}), 400

        # Si yo tengo la proposal y he votado sí, mando precommit sí 
        vote_yes: bool = tendermint_node.prevotes.get(
            tendermint_node.node_id, False
        )

        if tendermint_node.proposal is None:
            vote_yes = False

        print(f">>> [{tendermint_node.node_id}] envío precommit vote={vote_yes}")

        tendermint_node.send_precommit(proposer_id, vote_yes)

        return jsonify({
            "received": True,
            "sent_precommit": vote_yes
        })


    @app.route("/consensus/precommit", methods=["POST"])
    def receive_precommit() -> Any: 
        """ 
        Recibe un precommit (confirmación) de otro nodo y actualiza el conteo de confirmaciones.
        Si se alcanza quórum de precommits y este nodo es el proposer de la propuesta en curso,
        ejecuta el compromiso final y difunde el commit al resto de la red. 
        """
        data: Dict[str, Any] = request.json or {}
        print(f">>> [{tendermint_node.node_id}] /consensus/precommit recibido {data}")

        try:
            voter_id: str = data["voter_id"]
            vote: bool = data["vote"]
        except KeyError:
            return jsonify({"error": "Precommit mal formado"}), 400

        quorum: bool = tendermint_node.handle_precommit(voter_id, vote)
        print(f">>> [{tendermint_node.node_id}] quorum precommit = {quorum}")

        if quorum and tendermint_node.proposal is not None:
            if tendermint_node.proposal.proposer == tendermint_node.node_id:
                print(f">>> [{tendermint_node.node_id}] COMMIT del bloque")
                success: bool = tendermint_node.commit_block()
                if success:
                    tendermint_node.broadcast_commit()

        return jsonify({ "received": True, "quorum_reached": quorum })


    @app.route("/consensus/commit", methods=["POST"])
    def receive_commit() -> Any:  #cada nodo valida por sí mismo (no hay confianza ciega)
        """ 
        Recibe un bloque ya comprometido (commit final) desde el proposer.
        Reconstruye el bloque con y lo añade a la cadena local, que vuelve a validar encadenamiento, hashes y 
        transacciones, y aplica el estado económico (balances).
        Si el bloque se aplica correctamente, se actualiza la altura y se resetea el estado de consenso local
        (proposal, prevotes, precommits).
        """
        data: Dict[str, Any] = request.json or {}
        print(f">>> [{tendermint_node.node_id}] /consensus/commit recibido")

        try:
            block: Block = Block.from_dict(data["block"])
        except Exception as e:
            return jsonify({"error": str(e)}), 400

        success: bool = tendermint_node.blockchain.add_block(block)
        print(f">>> [{tendermint_node.node_id}] bloque aplicado = {success}")

        if success:
            tendermint_node.current_height = tendermint_node.blockchain.get_chain_length()
            tendermint_node.proposal = None
            tendermint_node.prevotes = {}
            tendermint_node.precommits = {}

        return jsonify({
            "committed": success,
            "height": tendermint_node.blockchain.get_chain_length()
        })



    @app.route("/debug/propose", methods=["POST"])
    def debug_propose() -> Any:
        """
        Fuerza al nodo local a proponer un bloque.
        Se utiliza en pruebas/experimentos para disparar el consenso de forma controlada, sin depender de
        triggers externos. Si el mempool está vacío, devuelve error.
        """

        block: Block | None = tendermint_node.create_proposal()

        if block is None:
            return jsonify({
                "ok": False,
                "error": "No hay transacciones en el mempool"
            }), 400

        tendermint_node.broadcast_proposal()

        return jsonify({
            "ok": True,
            "proposer": tendermint_node.node_id,
            "block_height": block.index,
            "tx_count": len(block.transactions)
        })
        
    @app.route("/health")
    def health():
        """  
        Endpoint de salud para comprobar que el nodo está vivo y respondiendo.
        """
        return jsonify({"status": "ok", "node": tendermint_node.node_id})
    
    
    @app.route("/status")
    def status():
        """ 
        Devuelve un resumen del estado del nodo
        """
        chain = blockchain

        # Bloque actual
        current_height = len(chain.chain) - 1
        last_block = chain.chain[-1] if current_height >= 0 else None

        # Datos del bloque
        last_hash = last_block.hash if last_block else None
        tx_count_last_block = len(last_block.transactions) if last_block else 0

        # Total de transacciones desde el génesis
        total_txs = sum(len(b.transactions) for b in chain.chain)

        # Saldos actuales desde balance_manager
        balances = balance_manager.balances
        
        # Hash que representa a la candena entera de blockchain
        hash_cadena = blockchain.chain_fingerprint()


        info = {
            "node_id": tendermint_node.node_id,
            "height": current_height,
            "last_block_hash": last_hash,
            "tx_count_last_block": tx_count_last_block,
            "total_transactions": total_txs,
            "balances": balances,
            "chain_fingerprint": hash_cadena,
            "peers": tendermint_node.peers,
        }

        return jsonify(info)


    return app
