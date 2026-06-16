# Proyecto-20261 / KGeoMIP

> [!IMPORTANT]
> **ENTREGABLES Y CARPETA DE TRABAJO (Google Drive):**  
> 🔗 [Acceder a la Carpeta Compartida de Google Drive](https://drive.google.com/drive/folders/1T9VukBYFVKpFDuDR4za6YnbwnpFVZd4m?usp=sharing)
>
> Este enlace contiene los manuales técnicos compilados, el PDF del manual, datasets, y documentación oficial del proyecto.

Este repositorio contiene implementaciones y utilidades para el analisis de
MIP/IIT con tres bloques arquitectonicos principales:

1. `shared_core/`: nucleo unificado de hipercubos, sistemas, particiones,
   soluciones, EMD/IIT, formateo y logging compartido.
2. `QNodes/`: enfoque submodular y ejecucion directa de casos puntuales,
   incluyendo fuerza bruta clasica y pruebas auxiliares de k-particiones.
3. `GeoMIP/`: enfoque geometrico masivo orientado a procesamiento batch desde
   Excel, con `KGeometricSIA`, configuracion YAML y salida separada de Phi.

## Requisitos

- Linux (probado en Ubuntu/WSL)
- Python 3.11+
- `uv` instalado

Instalacion de `uv`:

```bash
pip install uv
```

## Estructura Rapida

- `shared_core/models/core/`: `System`, `NCube`, `Solution` y `PartitionSpec`.
- `shared_core/funcs/`: funciones compartidas de EMD/IIT y formateo.
- `shared_core/middlewares/`: `SafeLogger` y utilidades transversales.
- `QNodes/`: flujo submodular para ejecucion directa desde `exec.py`.
- `GeoMIP/src/Method2_Dynamic_Programming_Reformulation/`: pipeline batch de
  Method2/KGeoMIP.
- `GeoMIP/data/samples/`: datasets TPM `N*.csv`.
- `GeoMIP/results/`: Excel de entrada y salidas generadas del pipeline.
- `tests/`: pruebas automatizadas de modelos core, estrategias k y analisis
  visual.

## Entorno de Calidad

Desde la raiz del repositorio:

```bash
uv sync
uv run pytest
uv run ruff check
```

La configuracion raiz define el paquete local `shared-core` y las herramientas
de calidad. Los subproyectos `QNodes` y `Method2` consumen `shared-core` como
dependencia editable.

## Ejecutar QNodes

Desde `QNodes/`:

```bash
uv sync
uv run exec.py
```

Flujo principal:

- `QNodes/exec.py` configura la aplicacion y pagina de muestra.
- `QNodes/src/main.py` define el estado inicial, condiciones, alcance y
  mecanismo de un caso puntual.
- `Manager` carga la TPM desde `QNodes/src/.samples/`.
- `BruteForce` prepara el subsistema usando `shared_core.System` y calcula la
  particion minima.

Scripts auxiliares:

- `QNodes/src/run_kforce_test.py`: compara `BruteForce` contra `KForceSIA`.
- `QNodes/src/run_integrated_phi.py`: ejecuta `KForceSIA` en modo Phi integrado.

## Ejecutar GeoMIP / Method2

Desde `GeoMIP/src/Method2_Dynamic_Programming_Reformulation/`:

```bash
uv sync
uv run exec.py
```

Entrada por defecto:

- Excel entrada: `GeoMIP/results/Pruebas_Metodo2.xlsx`
- Configuracion: `GeoMIP/src/Method2_Dynamic_Programming_Reformulation/config.yaml`
- TPMs: `GeoMIP/data/samples/N*.csv`

Salida por defecto:

- Excel salida: `GeoMIP/results/resultados_Geometric.xlsx`

El pipeline batch esta separado en `src/pipeline/batch.py`. Lee subsistemas
desde Excel, ejecuta `KGeometricSIA` con timeout por proceso y escribe
`Phi_Efecto`, `Phi_Causa`, `Phi_Integrado` y la cadena de particion.

## Analisis Visual

`GeoMIP/src/analyze_results.py` lee `GeoMIP/results/resultados_Geometric.xlsx`
y genera una comparacion visual de asimetria temporal entre `Phi_Efecto` y
`Phi_Causa`:

```bash
uv run python GeoMIP/src/analyze_results.py
```

Salida:

- `GeoMIP/results/phi_comparison.png`
