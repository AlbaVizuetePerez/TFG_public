""" 
Este archivo centraliza la configuración básica de cada nodo del sistema
"""
import os

NODE_ID = os.getenv("NODE_ID")
PORT = int(os.getenv("PORT", 5001))

PEERS = os.getenv("PEERS", "")
PEER_LIST = [p for p in PEERS.split(",") if p]

BLOCK_SIZE_LIMIT = 4
DEFAULT_TX_SIGNATURE_SCHEME = "ed25519"

