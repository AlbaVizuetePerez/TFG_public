""" 
Benchmark del segundo experimento
"""

from __future__ import annotations
import csv
import time
from typing import Any

from crypto import (
    generate_keypair,
    sign_message,
    verify_signature
)

# CONFIGURACIÓN

MESSAGE = b"benchmark-message-for-crypto-cost"
#Número de repeticiones de cada operación
KEYGEN_ITERATIONS = 100 #Es menor porque la generación de claves es más costoso
SIGN_ITERATIONS = 1000
VERIFY_ITERATIONS = 1000

OUTPUT_FILE = "crypto_benchmark_results.csv"


def average(values: list[float]) -> float:
    """  
    Calcula la media aritmética de una lista de valores numéricos
    """
    return sum(values) / len(values)


# BENCHMARK POR ESQUEMA

def benchmark_scheme(scheme: str) -> dict[str, Any]:
    """
    Ejecuta el benhmark completo para un esquema concreto 
    """
    results = {
        "scheme": scheme
    }

    # Generación de claves 
    keygen_times = []
    for _ in range(KEYGEN_ITERATIONS):
        start = time.perf_counter()
        private_key, public_key = generate_keypair(scheme)
        end = time.perf_counter()
        keygen_times.append(end - start)

    results["keygen_time_avg"] = average(keygen_times)
    
    # Se gestiona con none el hecho de que Dilithium no puede mostrar el tamaño de su clave privada
    results["private_key_size"] = len(private_key) if isinstance(private_key, (bytes, bytearray)) else None
    results["public_key_size"] = len(public_key) if isinstance(public_key, (bytes, bytearray)) else None

    # Firma del mensaje 
    sign_times = []
    for _ in range(SIGN_ITERATIONS):
        start = time.perf_counter()
        signature = sign_message(MESSAGE, private_key, scheme)
        end = time.perf_counter()
        sign_times.append(end - start)

    results["sign_time_avg"] = average(sign_times)
    results["signature_size"] = len(signature)

    # Verificación de las firmas
    verify_times = []
    for _ in range(VERIFY_ITERATIONS):
        start = time.perf_counter()
        verify_signature(MESSAGE, signature, public_key, scheme)
        end = time.perf_counter()
        verify_times.append(end - start)

    results["verify_time_avg"] = average(verify_times)

    return results



def main() -> None:
    print("Ejecutando benchmark criptográfico...")

    all_results = []
    for scheme in ["ed25519", "dilithium3"]:
        print(f"  → Benchmark {scheme}")
        results = benchmark_scheme(scheme)
        all_results.append(results)

    # Guardar CSV
    with open(OUTPUT_FILE, "w", newline="") as csvfile:
        fieldnames = all_results[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in all_results:
            writer.writerow(row)

    print(f"Resultados guardados en {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
