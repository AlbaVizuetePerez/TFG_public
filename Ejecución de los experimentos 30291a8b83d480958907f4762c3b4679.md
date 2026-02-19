# Ejecución de los experimentos

## 1. Descripción general del proyecto

Este repositorio contiene el código utilizado para la ejecución de los **experimentos** del trabajo, centrados en el análisis de una blockchain experimental desplegada en un entorno distribuido con múltiples nodos.

Los detalles de diseño, arquitectura y funcionamiento interno del sistema están **ampliamente documentados dentro del propio código y en la memoria del trabajo**, por lo que este README se centra exclusivamente en explicar **cómo preparar el entorno y cómo ejecutar cada experimento de forma reproducible**.

Todo el sistema se ejecuta mediante **contenedores Docker**, donde cada nodo de la red se corresponde con un contenedor independiente.

---

## 2. Ejecución manual de los nodos y gestión de dependencias

Los nodos de la red **se levantan de forma manual.** Esta decisión se ha tomado de forma intencionada debido a la complejidad del entorno experimental.

Levantar los nodos manualmente permite:

- Tener control total sobre el estado y la ejecución de cada nodo.
- Observar en tiempo real la salida por terminal de cada contenedor.
- Detectar posibles errores o divergencias entre nodos durante las fases de consenso.

Además, esta decisión está directamente relacionada con la gestión manual de la librería **`liboqs`**, utilizada para la criptografía post-cuántica.

La librería `liboqs-python` depende de la compilación previa de `liboqs`, que no se encuentra disponible como paquete binario estándar en los repositorios habituales. Por ello, es necesario compilar manualmente `liboqs` antes de poder instalar el paquete de Python asociado. Esta dependencia impide que el entorno pueda prepararse únicamente mediante un `requirements.txt` o una imagen Docker genérica.

---

## 3. Preparación del entorno base (instalación de liboqs y Dilithium)

Para poder continuar es esencial tener Docker instalado. Y ya después, antes de ejecutar cualquier experimento, es necesario crear una imagen Docker base que incluya correctamente el soporte para criptografía post-cuántica. 

Este proceso se realiza **una única vez**, y el resultado se reutiliza para todos los nodos de la red y para los experimentos posteriores.

---

### 3.1 Creación del contenedor base

### Paso 1: crear un contenedor Ubuntu limpio

```bash
docker run --platform linux/amd64 -it ubuntu:22.04 bash
```

---

### Paso 2: actualizar el sistema

```bash
apt update && apt upgrade -y
```

---

### Paso 3: instalar dependencias del sistema

```bash
apt install -y python3 python3-pip python3-venv git buil-essential cmake libssl-dev
```

Es esencial que se ejecute en una sola línea (el guion es necesario, no es indicación de salto de línea). 

---

### 3.2 Compilación e instalación de liboqs

### Paso 4: clonar y compilar liboq

Se fija la versión `0.14.0` para garantizar la disponibilidad explícita de `Dilithium3`.

```bash
cd /
git clone https://github.com/open-quantum-safe/liboqs.git
cd liboqs
git checkout 0.14.0
```

Y luego compilamos

```bash
mkdir build
cd build
cmake -DCMAKE_INSTALL_PREFIX=/usr/local -DBUILD_SHARED_LIBS=ON ..
make -j1
make install
ldconfig
```

---

### 3.3 Instalación de oqs-python

### Paso 5: instalar el binding Python

```bash
cd /
git clone https://github.com/open-quantum-safe/liboqs-python.git
cd liboqs-python
git checkout 0.14.0
python3 -m pip install .
```

---

### 3.4 Verificación de la instalación

Acceder al intérprete de Python: y ejecutar: 

```python
python3 -c "import oqs; print([m for m in oqs.get_enabled_sig_mechanisms() if 'Dilithium' in m])"
```

El resultado esperado debe incluir mecanismos como:

```
['Dilithium2', 'Dilithium3', 'Dilithium5']
```

### Test adicional de firma

```python
python3 - << 'PY'
import oqs
sig = oqs.Signature("Dilithium3")
pk = sig.generate_keypair()
msg = b"test"
s = sig.sign(msg)
print(sig.verify(msg, s, pk))
PY
```

El resultado debe ser:

```
True
```

---

### 3.5 Creación de la imagen Docker base

Salir del intérprete de Python (`exit()`) y posteriormente del contenedor (`exit`).

Crear la imagen base:

```bash
docker commit {id_contenedor} {nombre_imagen}
```

El resultado de este comando debe ser el id de la imagen, que es una secuencia alfanumérica, de larga longitud. 

Esta imagen contiene:

- Ubuntu x86_64
- `liboqs` compilado manualmente
- `oqs-python` instalado
- Soporte funcional para Dilithium
- Entorno listo para ejecutar los experimentos

El id del contenedor es una secuencia alfanumérica, (algo como d7240d5ab89f), aparece al lado del nombre dentro de Docker. 

---

## 4. Creación de la red Docker

Se ha de elgir un nombre de red a gusto, sin espacios y en minúsculas para evitar errores. 

```bash
docker network create {nombre_red}
```

El resultado de este comando ha de ser una secuencia alfanumérica que representa el id de la red. 

Para comprobar que se ha creado bien se ejecuta lo siguiente: 

```bash
docker network ls
```

Y deberá de aparecer el nombre de la red que se acaba de crear

---

## 5. Creación y ejecución de los nodos

A partir de la imagen base se lanzan los nodos de la red.

### Paso 1: lanzar el nodo 1

```bash
docker run --platform linux/amd64 -it \
  --name nodo1 \
  --network {nombre_red} \
  -p 5100:5000 \
  -v "/ruta/a/tu/proyecto":/app \
  {id_imagen} \
  bash
```

---

### Paso 2: instalar dependencias Python del proyecto

```bash
cd /app
pip install --no-cache-dir -r requirements.txt
```

El archivo `requirements.txt` incluye dependencias como:

- `PyNaCl`
- `requests`
- `Flask`

---

### Paso 3: ejecutar el nodo

```bash
python3 main.py --bank_id nodo1
```

Este proceso se repite para `nodo2`, `nodo3` y `nodo4`, cada uno en una terminal independiente.

Quedan aqui repetidos los comandos del paso1, para que no haya problemas a la hora de lanzar cada uno de los nodos. El paso 2 es idéntico en todos los nodos. Cada nodo ha de ser levantado en una terminal diferente. 

```bash
NODO 2: 
docker run --platform linux/amd64 -it \
  --name nodo2 \
  --network {nombre_red} \
  -p 5101:5000 \
  -v"/ruta/al/proyecto":/app \
  {nombre_imagen} bash

NODO 3: 
docker run --platform linux/amd64 -it \
  --name nodo3 \
  --network {nombre_red} \
  -p 5102:5000 \
  -v"/ruta/al/proyecto":/app \
  {nombre_imagen} bash

NODO 4: 
docker run --platform linux/amd64 -it \
  --name nodo4 \
  --network {nombre_red} \
  -p 5103:5000 \
  -v"/ruta/al/proyecto":/app \
  {nombre_imagen} bash

```

Una vez terminado esto ya se tiene a los 4 nodos levantados. Podemos salir de ellos ejecutando `exit`.

---

## 5. ¿Cómo se levantan los nodos ?

En el caso de haber salido de los nodos para poder volver acceder a ellos se ha de ejecutar los siguiente. Como tenemos 4 nodos es necesario que se ejecuten estos comandos en 4 terminales diferentes.  Y es esencial que cada uno de los nodos que se pretenda levantar esté encendido dentro de Docker

Accedemos al nodo mediante este comando:

```bash
docker exec -it nodo1 bash
```

Luego para que el nodo actúe donde tiene guardado el código se ha de ejecutar lo siguiente: 

```bash
cd /app
```

```bash
python3 main.py --bank_id nodo1
```

Como en cada terminal se ejecuta un nodo diferente se ha de modificar el nombre del nodo (nodo1, nodo2, nodo3 o nodo4). 

---

## 6. Ejecución de los experimentos

Es importante cerrar y volver a levantar los nodos para evitar problemas entre cada ejecucion de cada experimento. 

### Primer Experimento— Ejecución de transacciones y consenso

1. Levantar los cuatro nodos (siguiendo la sección 5).
2. Acceder a uno de los nodos (por ejemplo, `nodo1`), para ello se ha de ejecutar, en una terminal diferente de las 4 que ya tenemos abiertas: 

```bash
docker exec -it nodo1 bash
```

1. Acceder al volúmen donde se encuentra el código:

```bash
cd /app
```

1. Ejecutar en el caso de Ed25519: 

```bash
export TX_SIGNATURE_SCHEME=ed25519
python3 tx_generator.py
```

Y en el caso de Dilithium: 

```bash
export TX_SIGNATURE_SCHEME=dilithium3
python3 tx_generator.py
```

1. Comprobar el estado de cada nodo mediante el endpoint `/status`. Para ello en la terminal del ordenador (una nueva, diferente de la de los distintos nodos) se ha de ejecutar lo siguiente: 

```bash
curl -X POST http://localhost:5100/debug/propose
```

Tras esto debemos ver algo parecido a: 

```bash
{"block_height":1,"ok":true,"proposer":"nodo1","tx_count":4}
```

Y ejecutamos: 

```bash
curl http://localhost:5100/status
curl http://localhost:5101/status
curl http://localhost:5102/status
curl http://localhost:5103/status
```

Esto mostrará el estado de los nodos. Todos deben mostrar el mismo:

- `block_height`
- `chain_fingerprint`
- estado de balances

Algo parecido a lo siguiente: 

```bash
{"balances":{"Banco_001":1493,"Banco_002":905,"Banco_003":1798,"Banco_004":1104},"chain_fingerprint":"a6e23cb60eb024dffb9447aec72cd069efa40310ee6cc5100ec35161113fcb3e","height":1,"last_block_hash":"63664364a724ef87ae1dd40db13152f9d403cf791d3bc7996bc0e02464867fc0","node_id":"nodo1","peers":["nodo2:5000","nodo3:5000","nodo4:5000"],"total_transactions":4,"tx_count_last_block":4}
{"balances":{"Banco_001":1493,"Banco_002":905,"Banco_003":1798,"Banco_004":1104},"chain_fingerprint":"a6e23cb60eb024dffb9447aec72cd069efa40310ee6cc5100ec35161113fcb3e","height":1,"last_block_hash":"63664364a724ef87ae1dd40db13152f9d403cf791d3bc7996bc0e02464867fc0","node_id":"nodo2","peers":["nodo1:5000","nodo3:5000","nodo4:5000"],"total_transactions":4,"tx_count_last_block":4}
{"balances":{"Banco_001":1493,"Banco_002":905,"Banco_003":1798,"Banco_004":1104},"chain_fingerprint":"a6e23cb60eb024dffb9447aec72cd069efa40310ee6cc5100ec35161113fcb3e","height":1,"last_block_hash":"63664364a724ef87ae1dd40db13152f9d403cf791d3bc7996bc0e02464867fc0","node_id":"nodo3","peers":["nodo1:5000","nodo2:5000","nodo4:5000"],"total_transactions":4,"tx_count_last_block":4}
{"balances":{"Banco_001":1493,"Banco_002":905,"Banco_003":1798,"Banco_004":1104},"chain_fingerprint":"a6e23cb60eb024dffb9447aec72cd069efa40310ee6cc5100ec35161113fcb3e","height":1,"last_block_hash":"63664364a724ef87ae1dd40db13152f9d403cf791d3bc7996bc0e02464867fc0","node_id":"nodo4","peers":["nodo1:5000","nodo2:5000","nodo3:5000"],"total_transactions":4,"tx_count_last_block":4}
```

---

### Segundo Experimento — Benchmark criptográfico

1. Crear un contenedor aislado:

```bash
docker run --platform linux/amd64 -it \
 --name bench_crypto \
 --network {nombre_red} \
 -v"/ruta/al/proyecto":/app \
 {nombre_imagen} \
 bash
```

1. Instalar dependencias y ejecutar (dentro de ese nuevo contenedor):

```bash
cd /app
pip install --no-cache-dir -r requirements.txt
python3 bench_crypto.py
```

Si después de ejecutar 

`pip install --no-cache-dir -r requirements.txt` se sale del contenedor mediante `exit`, se ha de ejecutar lo siguiente por pasos en una terminal nueva:

```bash
docker exec -it bench_crypto bash
```

```bash
cd /app
```

```bash
python3 bench_crypto.py 
```

1. Al finalizar se genera el archivo:

```
crypto_benchmark_results.csv
```

---

### Tercer Experimento — Escalabilidad criptográfica

En el contenedor creado en el experimento anterior ejecutamos lo siguiente por pasos: 

```bash
docker exec -it bench_crypto  bash
```

```bash
cd /app
```

Dependiendo de sobre que algoritmo de firma se quiera ejecutar el código se ejecuta una de las dos opciones siguientes: 

```bash
TX_SIGNATURE_SCHEME=ed25519 python3 bench_tx_sign_verify_scaling.py

ó 

TX_SIGNATURE_SCHEME=dilithium3 python3 bench_tx_sign_verify_scaling.py
```

---

### Cuarto Experimento — Benchmark de red y consenso

1. Levantar los cuatro nodos (siguiendo la sección 5).
2. Acceder a `nodo1` desde una terminal diferente, ejecutando lo siguiente en orden: 

```bash
docker exec -it nodo1 bash
```

```bash
cd /app
```

En el caso de Edd25519 a continuación se ejecuta: 

```bash
export TX_SIGNATURE_SCHEME=ed25519
python3 bench_network.py

```

Y en el caso de Dilithium:

1. a la que está levantado y ejecutar:

```bash
export TX_SIGNATURE_SCHEME=dilithium3
python3 bench_network.py
```

Esto se realiza de forma repetida y se obtienen los resultados dentro de una tabla. 

1. Los resultados se almacenan en:

```
network_benchmark_results.csv
```

---

## 6. Resultados

Los resultados de los experimentos se almacenan automáticamente en archivos CSV dentro del directorio del proyecto, listos para su posterior análisis.