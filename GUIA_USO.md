# Guia de Uso: GeoMIP y QNodes

## 1. Requisitos

1. Instalar Python 3.11 o superior.

2. Instalar `uv` si no esta disponible:

```bash
python -m pip install --upgrade uv
```

3. Instalar las dependencias compartidas desde la raiz del repositorio:

```bash
cd /home/crack/analisis20261
uv sync
```

4. Instalar el entorno de GeoMIP Method2:

```bash
cd /home/crack/analisis20261/GeoMIP/src/Method2_Dynamic_Programming_Reformulation
uv sync
```

5. Instalar el entorno de QNodes:

```bash
cd /home/crack/analisis20261/QNodes
uv sync
```

## 2. Configuracion

1. GeoMIP Method2 lee su configuracion desde:

```text
GeoMIP/src/Method2_Dynamic_Programming_Reformulation/config.yaml
```

2. Parametros principales de `config.yaml`:

- `sheet_index`: indice numerico de la hoja del Excel de entrada. El conteo inicia en `0`; por ejemplo, `8` selecciona la novena hoja.
- `column`: columna del Excel que contiene los subsistemas a procesar. Por defecto se usa `B`.
- `count`: cantidad maxima de filas/subsistemas que se procesaran desde el punto de inicio configurado.
- `timeout_seconds`: tiempo maximo, en segundos, permitido para cada subsistema. Si una iteracion supera este limite, se termina y se registra sin resultado valido.
- `DEFAULT_K_MAX`: limite superior de grupos `k` que evalua la heuristica geometrica `KGeometricSIA`.

3. Ejemplo actual:

```yaml
sheet_index: 8
column: B
skiprows: 3
timeout_seconds: 3600
DEFAULT_K_MAX: 5
start: 0
count: 50
```

4. Seleccion de estrategia:

- El orquestador no esta unificado actualmente por `config.yaml`.
- GeoMIP Method2 ejecuta la estrategia geometrica `KGeometricSIA` desde `src/pipeline/batch.py`.
- QNodes se ejecuta como proyecto separado desde el directorio `QNodes`.
- Si se requiere cambiar QNodes entre fuerza bruta y algoritmo Q/submodular, la seleccion se hace editando `QNodes/src/main.py`: cambiar la importacion y la instancia de estrategia (`BruteForce` o `QNodes`) antes de ejecutar.

5. Entradas y salidas por defecto de GeoMIP:

- Excel de entrada: `GeoMIP/results/Pruebas_Metodo2.xlsx`.
- Excel de salida: `GeoMIP/results/resultados_Geometric.xlsx`.
- Tambien pueden sobrescribirse con variables de entorno:

```bash
GEOMIP_INPUT_XLSX=/ruta/entrada.xlsx GEOMIP_OUTPUT_XLSX=/ruta/salida.xlsx uv run exec.py
```

## 3. Ejecucion GeoMIP

1. Entrar al directorio de Method2:

```bash
cd /home/crack/analisis20261/GeoMIP/src/Method2_Dynamic_Programming_Reformulation
```

2. Sincronizar dependencias si aun no se hizo:

```bash
uv sync
```

3. Ejecutar GeoMIP:

```bash
uv run exec.py
```

4. El proceso lee `config.yaml`, toma los subsistemas desde `GeoMIP/results/Pruebas_Metodo2.xlsx` y escribe los resultados en `GeoMIP/results/resultados_Geometric.xlsx`.

## 4. Ejecucion QNodes

1. Entrar al directorio `QNodes`:

```bash
cd /home/crack/analisis20261/QNodes
```

2. Sincronizar dependencias si aun no se hizo:

```bash
uv sync
```

3. Ejecutar usando el wrapper principal:

```bash
uv run exec.py
```

4. Alternativamente, ejecutar directamente el modulo principal:

```bash
uv run src/main.py
```

5. Los parametros del caso de prueba se ajustan en `QNodes/src/main.py`:

- `estado_inicial`
- `condiciones`
- `alcance`
- `mecanismo`

6. La pagina de muestra se ajusta en `QNodes/exec.py` con:

```python
aplicacion.set_pagina_red_muestra("A")
```

## 5. Analisis de Resultados

1. El Excel generado por GeoMIP se guarda en:

```text
GeoMIP/results/resultados_Geometric.xlsx
```

2. Ejecutar el analisis desde la raiz del repositorio:

```bash
cd /home/crack/analisis20261
uv run GeoMIP/src/analyze_results.py
```

3. El script genera el grafico:

```text
GeoMIP/results/phi_comparison.png
```

4. Interpretacion rapida de `phi_comparison.png`:

- Cada grupo de barras corresponde a una iteracion/subsistema procesado.
- La barra `Phi_Efecto` muestra la perdida de informacion asociada al efecto.
- La barra `Phi_Causa` muestra la perdida de informacion asociada a la causa.
- Barras mas altas indican mayor perdida de informacion para esa dimension.
- Si ambas barras son cercanas, el subsistema tiene un comportamiento causa/efecto equilibrado; si una domina, la perdida se concentra en esa direccion.
