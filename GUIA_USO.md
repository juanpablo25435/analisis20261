# Guia de Usuario: Dashboard KGeoMIP y QNodes

Esta guia explica como usar la interfaz grafica de Streamlit para cargar datos, elegir el metodo de analisis y revisar resultados de Phi sin editar codigo. El flujo recomendado es trabajar siempre desde el dashboard: primero se abre la aplicacion, luego se selecciona el origen de datos, despues se ejecuta el motor matematico y finalmente se revisan las visualizaciones.

## 1. Requisitos rapidos

Antes de abrir el dashboard, verifica que el equipo tenga:

- Python 3.11 o superior.
- `uv` instalado.
- Acceso a la carpeta del proyecto.
- Un archivo Excel `.xlsx` o `.xls` con los subsistemas a analizar, o una matriz TPM en `.csv` si se hara una prueba personalizada.

Si `uv` no esta instalado, ejecuta:

```bash
python -m pip install --upgrade uv
```

Desde la raiz del proyecto, sincroniza las dependencias una sola vez:

```bash
cd /home/crack/analisis20261
uv sync --all-extras --dev
```

## 2. Abrir el dashboard

Desde la raiz del proyecto, inicia la interfaz grafica con:

```bash
uv run streamlit run app.py
```

Streamlit abrira una direccion local en el navegador, normalmente `http://localhost:8501`. Si el navegador no se abre automaticamente, copia esa direccion desde la terminal y pegala en tu navegador.

Al entrar veras el titulo `KGeoMIP Analytics Framework`, una barra lateral llamada `Control del Motor` y cuatro pestanas principales:

- `Configuracion Dinamica`: prepara los datos, el metodo y los parametros.
- `Monitor de Ejecucion y Resiliencia`: muestra el avance y permite detener una ejecucion.
- `Dashboard de Resultados`: revisa tablas, filtros y graficas de Phi.
- `Arena Comparativa`: compara tiempos de ejecucion entre QNodes y GeoMIP cuando hay resultados disponibles.

[INSERTAR CAPTURA DE PANTALLA: pantalla inicial del dashboard Streamlit con barra lateral Control del Motor y las cuatro pestanas principales]

## 3. Cargar los datos

En la barra lateral, elige el origen de datos:

- `Cargar desde Excel Completo`: recomendado para procesar varias filas o subsistemas desde un libro Excel.
- `Subir Matriz TPM Personalizada (.csv)`: util para una prueba puntual con una matriz TPM propia.

Para usar Excel, entra en `Configuracion Dinamica` y revisa estos campos:

- `sheet_index`: numero de hoja dentro del Excel. El conteo empieza en `0`; por ejemplo, `8` significa la novena hoja.
- `column`: columna donde estan los subsistemas. Por defecto se usa `B`.
- `skiprows`: filas iniciales que se omiten antes de leer datos.
- `start`: fila de inicio dentro del bloque leido.
- `count`: cantidad de subsistemas que se procesaran.
- `timeout_seconds por subsistema`: tiempo maximo permitido para cada subsistema.
- `Ruta del Excel completo`: ruta del archivo de entrada.
- `Opcional: subir Excel completo`: carga un Excel temporal desde tu equipo.

[INSERTAR CAPTURA DE PANTALLA: carga o seleccion de Excel completo en Configuracion Dinamica mostrando Ruta del Excel completo y Opcional subir Excel completo]

Si eliges una TPM `.csv`, usa el cargador `Matriz TPM personalizada (.csv)`. Cuando el archivo sea aceptado, el dashboard mostrara una vista previa para confirmar que la matriz se leyo correctamente.

## 4. Elegir el metodo de analisis

En `Control del Motor`, selecciona el motor matematico que corresponde al objetivo del analisis:

- `Metodo 1: QNodes (Optimizacion Submodular)`: recomendado para casos pequenos o demostraciones donde se quiere estudiar una configuracion puntual con estado, condiciones, alcance y mecanismo definidos.
- `Metodo 2: GeoMIP (Aglomeracion Geometrica)`: recomendado para sistemas mas grandes o procesamiento por lotes desde Excel. Para `N > 12`, usa KGeoMIP antes que KQNodes para reducir el consumo de memoria.

[INSERTAR CAPTURA DE PANTALLA: seleccion de Metodo 1 KQNodes y Metodo 2 KGeoMIP en la barra lateral Control del Motor]

### Metodo 1: KQNodes

Selecciona `Metodo 1: QNodes (Optimizacion Submodular)` cuando quieras ejecutar KQNodes. En `Configuracion Dinamica`, completa:

- `estado_inicial`: estado inicial del sistema, por ejemplo `1000`.
- `condiciones`: nodos condicionados, por ejemplo `1110`.
- `alcance`: parte del sistema que se evalua como efecto.
- `mecanismo`: parte del sistema que se evalua como causa.
- `pagina de muestra`: pagina o red de muestra, por ejemplo `A`.
- `activar profiling QNodes`: dejalo desactivado salvo que necesites medir rendimiento con detalle.

KQNodes genera resultados en `QNodes/results/resultados_QNodes.csv`. El dashboard los detecta para visualizarlos en `Dashboard de Resultados`.

### Metodo 2: KGeoMIP

Selecciona `Metodo 2: GeoMIP (Aglomeracion Geometrica)` cuando quieras ejecutar KGeoMIP. Es la opcion recomendada para procesar varios subsistemas desde Excel y para redes de mayor tamano.

En `Configuracion Dinamica`, ajusta:

- `DEFAULT_K_MAX`: valor maximo de `k` que explorara el metodo. Puedes probar `k` en `{2, 3, 4, 5}` para comparar particiones.
- `estado_inicio`: estado inicial usado por el analisis.
- `condiciones`: condiciones aplicadas durante el calculo.

[INSERTAR CAPTURA DE PANTALLA: selector DEFAULT_K_MAX para elegir k en KGeoMIP con valores de 2 a 5]

Cuando se trabaja desde Excel, el dashboard toma `alcance` y `mecanismo` desde cada fila del libro. Los resultados de KGeoMIP se guardan en `GeoMIP/results/resultados_Geometric.xlsx`.

## 5. Ejecutar y monitorear

Cuando los parametros esten listos, presiona `Lanzar Pipeline por Lotes`.

Despues abre `Monitor de Ejecucion y Resiliencia`. Alli puedes:

- Ver la barra de progreso.
- Leer mensajes de avance por iteracion.
- Confirmar que el motor seleccionado esta procesando datos.
- Usar `Detener Inmediatamente` si necesitas interrumpir la ejecucion. Si hay resultados parciales, el sistema intentara guardarlos.

[INSERTAR CAPTURA DE PANTALLA: monitor de ejecucion con barra de progreso mensajes de avance y boton Detener Inmediatamente]

Recomendacion de uso: empieza con `count` pequeno, por ejemplo `1` a `5`, para confirmar que el Excel, la hoja y la columna estan bien configurados. Luego aumenta `count` para procesar mas subsistemas.

## 6. Revisar resultados en el dashboard

Abre `Dashboard de Resultados` despues de completar una ejecucion. Selecciona el archivo de resultados en `Archivo de resultados`. El dashboard mostrara:

- Metricas resumen, como filas procesadas y promedios de Phi.
- Una tabla filtrable con particiones, estados, mecanismos, alcances y tiempos.
- Un filtro textual para buscar subsistemas o particiones.
- Un filtro por rango Phi cuando hay columnas numericas de Phi.
- Una grafica interactiva de Phi por subsistema.

[INSERTAR CAPTURA DE PANTALLA: dashboard de resultados con selector Archivo de resultados tabla filtrable y grafica interactiva de Phi]

### Interpretar Phi causa y Phi efecto

En resultados de KGeoMIP, las columnas principales son:

- `Phi_Causa`: perdida de informacion asociada a la dimension causal.
- `Phi_Efecto`: perdida de informacion asociada a la dimension de efecto.
- `Phi_Integrado`: resultado integrado reportado por el metodo.

Si `Phi_Causa` y `Phi_Efecto` son cercanos, el subsistema presenta una relacion causa-efecto relativamente equilibrada. Si una de las dos domina, la perdida de informacion se concentra mas en esa direccion.

Cuando esta disponible el grafico `phi_comparison.png`, el dashboard lo muestra como comparacion visual de asimetria entre `Phi_Efecto` y `Phi_Causa`.

[INSERTAR CAPTURA DE PANTALLA: visualizacion temporal de asimetria Phi y dashboard Phi causa vs efecto]

## 7. Comparar KQNodes y KGeoMIP

Usa `Arena Comparativa` para revisar tiempos de ejecucion por tamano de red `N`. Esta vista es util cuando ya existen resultados de uno o ambos metodos.

La comparacion ayuda a decidir que motor usar:

- Para pruebas pequenas y explicaciones paso a paso, KQNodes es facil de inspeccionar.
- Para sistemas grandes o lotes desde Excel, KGeoMIP suele ser mas practico.
- Para `N > 12`, prioriza KGeoMIP, especialmente si el equipo tiene RAM limitada.

## 8. Problemas frecuentes

| Problema | Posible causa | Como resolverlo |
| --- | --- | --- |
| Streamlit indica que el puerto `8501` esta ocupado. | Ya hay otro dashboard abierto o un proceso anterior quedo ejecutandose. | Cierra la terminal anterior o deten el proceso que usa `8501`. Tambien puedes abrir en otro puerto con `uv run streamlit run app.py --server.port 8502`. |
| El dashboard no abre despues de ejecutar el comando. | El navegador no se abrio automaticamente o la terminal quedo esperando. | Copia la URL que muestra Streamlit, normalmente `http://localhost:8501`, y pegala en el navegador. |
| Aparecen errores de dependencias o paquetes faltantes. | El entorno no esta sincronizado con el proyecto. | Desde la raiz ejecuta `uv lock` y luego `uv sync --all-extras --dev`. Despues vuelve a abrir el dashboard. |
| El Excel no carga o no aparecen filas. | `sheet_index`, `column`, `skiprows`, `start` o `count` no apuntan a los datos esperados. | Revisa la hoja y la columna en el Excel. Prueba con `count` pequeno y confirma la carga antes de ejecutar un lote grande. |
| Error de memoria RAM con `N > 12`. | El numero de estados crece rapidamente y KQNodes puede requerir demasiada memoria. | Usa KGeoMIP en lugar de KQNodes para sistemas grandes. Reduce `count`, prueba valores menores de `k` y cierra aplicaciones innecesarias. |
| La ejecucion tarda demasiado. | El lote tiene muchos subsistemas, `timeout_seconds` es alto o el sistema tiene `N` grande. | Ejecuta primero pocas filas, revisa resultados parciales y aumenta el lote gradualmente. |
| No se ven graficas de Phi. | El archivo seleccionado no tiene columnas Phi numericas o aun no hay resultados. | Ejecuta un pipeline y selecciona el archivo generado en `Dashboard de Resultados`. |

## 9. Buenas practicas de uso

- Guarda una copia del Excel original antes de hacer cambios.
- Usa nombres de archivo descriptivos para distinguir pruebas.
- Ejecuta primero un lote pequeno para validar configuracion.
- Documenta el valor de `k`, el metodo usado y el tamano `N` cuando compares resultados.
- Para presentaciones o informes, captura la configuracion, el monitor de ejecucion y el dashboard final.