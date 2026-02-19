"""
Este archivo genera transacciones de forma aleatoria que se guardan en un archivo json y son utilizadas para 
los experimentos. 
"""


import json
import random
import time

OUTPUT = "tx_dataset.json"

# CONFIGURACIÓN 

# Balances iniciales 
BALANCES = {
    "Banco_001": 1500,
    "Banco_002": 900,
    "Banco_003": 1800,
    "Banco_004": 1100,
}

BANKS = list(BALANCES.keys())

N_TX = 4 #cantidad de transacciones
MIN_AMT = 1 #cantidad minima a transferirse en una transacción
MAX_AMT = 5 #cantidad máxima a transferirse en una transacción
SEED = 12345 #semilla del generador de números aleatorios

def main():
    rng = random.Random(SEED)

    # copia local de balances para no crear tx inválidas
    local = BALANCES.copy()
    dataset = [] # Lista donde se almacenarán las transacciones generadas
    base_ts = int(time.time()) #timestamp del momento de ejecución

    for i in range(N_TX):
        # elegir sender con fondos
        candidates = [b for b in BANKS if local[b] >= MIN_AMT] # Seleccionamos solo los bancos con saldo suficiente
        if not candidates: #Si no hay bancos con fondos suficientes paramos la ejecución
            break

        sender = rng.choice(candidates)
        receiver = rng.choice([b for b in BANKS if b != sender])

        amt = rng.randint(MIN_AMT, min(MAX_AMT, local[sender]))
        ts = base_ts + i  # timestamps deterministas
        
        #Creación de la transacción
        dataset.append({  
            "sender": sender,
            "receiver": receiver,
            "amount": amt,
            "timestamp": ts
        })
        
        #Actualización de los estados locales simulados tras las transacciones
        local[sender] -= amt
        local[receiver] += amt

    with open(OUTPUT, "w") as f:
        json.dump(dataset, f, indent=2)

    print(f"Generado {len(dataset)} tx en {OUTPUT}")

if __name__ == "__main__":
    main()
