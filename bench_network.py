from __future__ import annotations
import os
import json
import csv
import time
import requests
from typing import Any


from crypto import generate_keypair
from transaction import Transaction

# CONFIGURACIÓN

# Variable de entorno mediante la cual se selecciona el algoritmo de firma 
TX_SIGNATURE_SCHEME = os.getenv("TX_SIGNATURE_SCHEME", "ed25519")

# Nodos de la red 
NODES = [
    "http://nodo1:5000",
    "http://nodo2:5000",
    "http://nodo3:5000",
    "http://nodo4:5000",
]
 
PROPOSER = "http://nodo1:5000" #Nodo que actuará como proponente 

# Endpoints
TX_ENDPOINT = "/tx"
STATUS_ENDPOINT = "/status"
CHAIN_ENDPOINT = "/chain"
PROPOSE_ENDPOINT = "/debug/propose"

DATASET_FILE = "tx_dataset.json"  
OUTPUT_CSV = "network_benchmark_results.csv"

POLL_INTERVAL = 0.1
TIMEOUT_SEC = 20



def get_status(node_url: str) -> dict[str, Any]:
    """
    Consulta el Endpoint status d eun nodo y devuelve su respuetsa (el estado del nodo) como un diccionario JSON
    """
    r = requests.get(node_url + STATUS_ENDPOINT, timeout=3)
    r.raise_for_status()
    return r.json()

def get_chain(node_url: str) -> dict[str, Any]:
    """  
    Consulta el endpoint chain de un nodo y devuelve su cadena (lista de bloques serializados) como un diccionario JSON
    """
    r = requests.get(node_url + CHAIN_ENDPOINT, timeout=5)
    r.raise_for_status()
    return r.json()

def wait_all_nodes_height(target_height: int) -> None:
    """  
    Espera hasta que todos los nodos alcancen al menos la altura target_height.
    Se utiliza para determinar el momento en que el bloque ha sido aplicado por toda la red.
    """
    deadline = time.time() + TIMEOUT_SEC
    while time.time() < deadline:
        heights = []
        for n in NODES:
            try:
                st = get_status(n)
                heights.append(int(st.get("height", -1)))
            except Exception:
                heights.append(-1)

        if all(h >= target_height for h in heights):
            return

        time.sleep(POLL_INTERVAL)

    raise TimeoutError(f"No todos los nodos alcanzaron height={target_height}")

# TRANSACCIONES

def load_dataset()-> list[dict[str, Any]]:
    """   
    Carga el dataset de transacciones desde un fichero JSON
    """
    with open(DATASET_FILE, "r") as f:
        return json.load(f)

def sign_and_send_transactions() -> None:
    """   
    Firma y envía al nodo proponente todas las transacciones del dataset 
    """
    dataset = load_dataset()

    key_obj, public_key = generate_keypair(TX_SIGNATURE_SCHEME)
    private_key = key_obj  # ed25519: bytes | dilithium3: oqs.Signature

    for tx_data in dataset:
        tx = Transaction(
            sender=tx_data["sender"],
            receiver=tx_data["receiver"],
            amount=tx_data["amount"],
            timestamp=tx_data["timestamp"]
        )

        tx.sign(
            private_key=private_key,
            public_key=public_key,
            scheme=TX_SIGNATURE_SCHEME
        )

        r = requests.post(PROPOSER + TX_ENDPOINT, json=tx.to_dict(), timeout=5)
        if r.status_code != 200:
            try:
                body = r.json()
            except Exception:
                body = r.text
            raise RuntimeError(f"POST /tx falló ({r.status_code}): {body}")

# BENCHMARK

def run_single_round()-> dict[str, Any]:
    """  
    Ejecuta la ronda de consenso y calcula las métricas de rendimiento
    """
    # Altura inicial
    start_status = get_status(PROPOSER)
    start_height = int(start_status.get("height", 0))
    target_height = start_height + 1

    # Enviar TX
    sign_and_send_transactions()

    # Proponer bloque y medir latencia
    t0 = time.perf_counter()
    r = requests.post(PROPOSER + PROPOSE_ENDPOINT, timeout=10)
    r.raise_for_status()
    info = r.json()
    wait_all_nodes_height(target_height)
    t1 = time.perf_counter()

    latency = t1 - t0
    tx_count = int(info.get("tx_count", 4))

    # Tamaño del bloque
    chain = get_chain(PROPOSER)
    blocks = chain.get("chain", [])
    last_block = blocks[-1] if blocks else chain
    block_size = len(json.dumps(last_block).encode("utf-8"))

    tps = tx_count / latency if latency > 0 else 0.0

    return {
        "timestamp": int(time.time()),
        "scheme": TX_SIGNATURE_SCHEME,
        "block_height": target_height,
        "tx_count": tx_count,
        "latency_sec": round(latency, 6),
        "block_size_bytes": block_size,
        "tps": round(tps, 6),
    }

# MAIN

def main() -> None:
    print(f"\nExperimento C — esquema={TX_SIGNATURE_SCHEME}")
    print("Ejecutando UNA ronda de consenso...\n")

    result = run_single_round()

    file_exists = os.path.exists(OUTPUT_CSV)
    with open(OUTPUT_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=result.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(result)

    print(
        f"Bloque {result['block_height']} | "
        f"latency={result['latency_sec']}s | "
        f"tx={result['tx_count']} | "
        f"size={result['block_size_bytes']}B | "
        f"tps={result['tps']}"
    )
    print(f"Resultado añadido a {OUTPUT_CSV}\n")

if __name__ == "__main__":
    main()
