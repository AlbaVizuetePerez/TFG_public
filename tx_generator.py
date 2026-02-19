from __future__ import annotations
import os
import json
import requests
from typing import Any

from transaction import Transaction
from crypto import generate_keypair

#CONFIGURACIÓN

NODE_URL = "http://localhost:5000/tx" #URL del nodo al que se le envían las transacciones
DATASET_FILE = "tx_dataset.json" #Archivo JSON qe contiene el dataset base de transacciones

# El esquema de firma utilizado se controla mediante una variable de entorno
TX_SIGNATURE_SCHEME = os.getenv("TX_SIGNATURE_SCHEME", "ed25519")

def main() -> None:
    print(f" Usando esquema de firma: {TX_SIGNATURE_SCHEME}")

    key_obj, public_key = generate_keypair(TX_SIGNATURE_SCHEME)

    if TX_SIGNATURE_SCHEME == "dilithium3":
        private_key = key_obj      # oqs.Signature
    else:
        private_key = key_obj      # bytes (Ed25519)

    with open(DATASET_FILE, "r") as f:
        dataset = json.load(f)

    for i, tx_data in enumerate(dataset):
        # Construcción del objeto Transaction 
        tx = Transaction(
            sender=tx_data["sender"],
            receiver=tx_data["receiver"],
            amount=tx_data["amount"],
            timestamp=tx_data["timestamp"]
        )

        #firma de las transacciones
        tx.sign(
            private_key=private_key,
            public_key=public_key,
            scheme=TX_SIGNATURE_SCHEME
        )

        #Envío al nodo mediante HTTP POST
        r = requests.post(NODE_URL, json=tx.to_dict())
        try:
            body = r.json()
        except Exception:
            body = r.text

        print(f"TX {i} → status {r.status_code} | {body}")


if __name__ == "__main__":
    main()