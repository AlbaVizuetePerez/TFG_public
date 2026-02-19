from __future__ import annotations
import os
import csv
import time

from transaction import Transaction
from crypto import generate_keypair

#CONFIGURACIÓN

TX_SIGNATURE_SCHEME = os.getenv("TX_SIGNATURE_SCHEME", "ed25519") #Variable de entorno para seleccionar el esquema de firma usado en esa ejecución

#Organizamos las transacciones en lotes que van incrementando en tamaño 
START_N = 1000 #Primer tamaño del lote
END_N = 2000 #Último tamaño del lote
STEP = 100 #Incremento entre tamaños de lotes

#Se repite cada lote 5 veces para así hacer la media de esos resultados y estabilizar el resultado frente a 
#diferentes problemas como la gestión de memoria o el cache
REPEATS = 5
OUTPUT_FILE = "tx_sign_verify_scaling.csv" #nombre del archivo donde se guarda la tabla de los resultados


def make_dummy_transactions(n: int) -> list[Transaction]:
    """
    Esta función genera una lista de N transacciones (N siendo el tamaño del lote)
    """
    txs = []
    base_ts = 1700000000
    for i in range(n):
        txs.append(
            Transaction(
                sender="Banco_001",
                receiver="Banco_002",
                amount=1,
                timestamp=base_ts + i
            )
        )
    return txs


def time_sign_total(n: int, private_key, public_key, scheme: str) -> float:
    """  
    Mide el tiempo total (en segundos) para firmar N transacciones. 
    """
    txs = make_dummy_transactions(n)
    t0 = time.perf_counter()
    for tx in txs:
        tx.sign(private_key=private_key, public_key=public_key, scheme=scheme)
    t1 = time.perf_counter()
    return t1 - t0


def time_verify_total(n: int, private_key, public_key, scheme: str) -> float:
    """  
    Mide el tiempo total (en segundos) para verificar N firmas
    """
    txs = make_dummy_transactions(n)
    for tx in txs:
        tx.sign(private_key=private_key, public_key=public_key, scheme=scheme)

    t0 = time.perf_counter()
    ok = 0
    for tx in txs:
        if tx.verify():
            ok += 1
    t1 = time.perf_counter()

    if ok != n:
        raise RuntimeError(f"Verificación falló: {ok}/{n} correctas") #Se verifica que todas se han verificado de forma correcta

    return t1 - t0


def main() -> None:
    print(f"Scaling firma/verificación (totales) | scheme={TX_SIGNATURE_SCHEME}")

    key_obj, public_key = generate_keypair(TX_SIGNATURE_SCHEME)
    private_key = key_obj  # ed25519: bytes | dilithium3: oqs.Signature

    rows = []
    for n in range(START_N, END_N + 1, STEP):
        sign_times = []
        verify_times = []
        
        #Se repite el experimento para estabilizar las medidas
        for _ in range(REPEATS):
            sign_times.append(time_sign_total(n, private_key, public_key, TX_SIGNATURE_SCHEME))
            verify_times.append(time_verify_total(n, private_key, public_key, TX_SIGNATURE_SCHEME))
        #Se hace la media de todos los resultados de las repeticiones para esas N transacciones, de esta forma eliminamos ruido
        sign_total_avg = sum(sign_times) / len(sign_times)
        verify_total_avg = sum(verify_times) / len(verify_times)

        rows.append({
            "scheme": TX_SIGNATURE_SCHEME,
            "n_transactions": n,
            "repeats": REPEATS,
            "sign_total_sec_avg": round(sign_total_avg, 6),
            "verify_total_sec_avg": round(verify_total_avg, 6),
        })

        print(f"N={n} | sign_total={sign_total_avg:.6f}s | verify_total={verify_total_avg:.6f}s")

    # Cambios clave: append + cabecera solo si hace falta
    file_exists = os.path.exists(OUTPUT_FILE)
    file_is_empty = (not file_exists) or (os.path.getsize(OUTPUT_FILE) == 0)

    with open(OUTPUT_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        if file_is_empty:
            writer.writeheader()
        writer.writerows(rows)

    print(f"\nResultados añadidos a: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
