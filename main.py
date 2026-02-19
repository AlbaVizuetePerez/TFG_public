""" 
Es el punto de entrada del sistema y actúa como el orquestador del nodo. 
Inicializa y conecta todos los componentes necesarios para que un nodo blockchain 
funcione. En concreto, se encarga de obtener la identidad del nodo (por argumentos CLI),
configurar el conjunto de validadores y sus direcciones, generar o cargar el material 
criptográfico, crear la blockchain local a partir del fichero de génesis 
(incluyendo balances iniciales), instanciar el gestor de consenso y exponer la API REST mediante Flask.
"""
from typing import Dict, List
import argparse

from crypto import generate_keypair
from balances import BalanceManager
from blockchain import Blockchain
from tendermint_handler import TendermintHandler
from api import create_app


# PARSEO DE ARGUMENTOS

def parse_args():
    """ 
    Lee argumentos por línea de comandos para arrancar múltiples nodos con el mismo código.
    El parámetro --bank_id identifica de forma lógica al nodo (nodo1, nodo2, etc.) y se usa
    para seleccionar su clave privada y construir su lista de peers.
    """
    parser = argparse.ArgumentParser(description="Nodo del blockchain TFG")

    parser.add_argument(
        "--bank_id",
        required=True,
        help="Identificador del nodo (ej: nodo1, nodo2, Banco_001...)"
    )

    return parser.parse_args()


args = parse_args()
NODE_ID: str = args.bank_id

# Puerto interno fijo 
PORT: int = 5000


# CONFIGURACIÓN DE VALIDADORES

VALIDATOR_IDS: List[str] = ["nodo1", "nodo2", "nodo3", "nodo4"]

# Docker crea DNS internos automáticamente: nodo1 → se resuelve a su IP en la red Docker
VALIDATOR_ADDRS: Dict[str, str] = {
    vid: f"{vid}:5000" for vid in VALIDATOR_IDS
}

# Peers = todos menos yo
PEERS: List[str] = [
    addr for vid, addr in VALIDATOR_ADDRS.items()
    if vid != NODE_ID
]


# CLAVES CRIPTOGRÁFICAS

private_keys: Dict[str, bytes] = {}
public_keys: Dict[str, bytes] = {}

for vid in VALIDATOR_IDS:
    priv: bytes
    pub:bytes
    priv, pub = generate_keypair("ed25519")  # Cambia "dilithium3" para PQC
    private_keys[vid] = priv
    public_keys[vid] = pub

MY_PRIVATE_KEY: bytes = private_keys[NODE_ID]


# BLOCKCHAIN Y ESTADO INICIAL (GÉNESIS)
# Creación de la cadena de blockchain
GENESIS_FILE: str = "genesis_state.json"

blockchain: Blockchain = Blockchain(
    genesis_file_path=GENESIS_FILE,
    block_size_limit=4
)

balance_manager: BalanceManager = blockchain.balance_manager


# NODO DE CONSENSO (TENDERMINT)

tendermint_node: TendermintHandler = TendermintHandler(
    node_id=NODE_ID,
    private_key=MY_PRIVATE_KEY,
    public_keys=public_keys,
    blockchain=blockchain,
    peers=PEERS,
    validator_addrs=VALIDATOR_ADDRS,
    block_size_limit=4
)


# API (HTTP DEL NODO)

app = create_app(
    blockchain=blockchain,
    balance_manager=balance_manager,
    tendermint_node=tendermint_node
)

print(f"✔ Nodo {NODE_ID} escuchando en puerto interno {PORT}")
app.run(host="0.0.0.0", port=PORT)
