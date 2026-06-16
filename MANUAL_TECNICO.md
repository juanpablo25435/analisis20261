# Manual Técnico de KGeoMIP

## 1. Introducción y Objetivos

KGeoMIP es una extensión geométrica del problema de la Partición de Mínima
Información (MIP, *Minimum Information Partition*) en el marco de la Teoría de
la Información Integrada (IIT). Su objetivo principal es estudiar cómo la
información causal de un sistema discreto se degrada al imponer particiones
sobre sus variables presentes y futuras.

En IIT, un sistema se evalúa comparando el repertorio causal/efectual del
subsistema original contra el repertorio inducido por una partición. La MIP es
la partición que minimiza la pérdida de información:

$$
\Phi = D\left(P_{\text{subsistema}}, P_{\text{partición}}\right)
$$

donde:

- $P_{\text{subsistema}}$ es la distribución marginal del subsistema sin
  particionar.
- $P_{\text{partición}}$ es la distribución marginal resultante tras imponer
  una partición.
- $D$ es una distancia entre distribuciones, implementada mediante variantes de
  EMD/IIT.

La formulación clásica de la MIP se ha aplicado con frecuencia a biparticiones
($k=2$). KGeoMIP generaliza esta idea a k-particiones:

$$
k \ge 2
$$

En este contexto, una partición ya no separa el sistema en dos bloques, sino en
un conjunto de bloques no vacíos que agrupan nodos de alcance y mecanismo. El
propósito técnico de KGeoMIP es hacer viable esta búsqueda en sistemas de mayor
tamaño mediante:

- representación compacta con hipercubos (`NCube`);
- cálculo causal por lotes;
- reutilización de estructuras geométricas;
- heurística de agrupamiento aglomerativo;
- límite operativo `DEFAULT_K_MAX`;
- separación del pipeline batch para validación empírica masiva.

## 2. Arquitectura Multi-capa

El repositorio se organiza en tres capas conceptuales:

1. `shared_core`: núcleo unificado de modelado y cálculo causal.
2. KQNodes (`QNodes`): enfoque submodular y ejecución directa.
3. KGeoMIP (`GeoMIP`): enfoque geométrico y procesamiento batch masivo.

Esta separación reduce duplicación, permite pruebas unitarias compartidas y
evita que las estrategias dependan de implementaciones divergentes de
hipercubos, sistemas o distancias.

### 2.1 `shared_core`: núcleo unificado

`shared_core` contiene las abstracciones comunes que antes estaban duplicadas
entre KQNodes (`QNodes`) y el flujo geométrico de KGeoMIP (`Method2`).

Componentes principales:

- `shared_core.models.core.NCube`
- `shared_core.models.core.System`
- `shared_core.models.core.Solution`
- `shared_core.models.core.PartitionSpec`
- `shared_core.funcs.iit`
- `shared_core.funcs.format`
- `shared_core.middlewares.slogger.SafeLogger`

#### `NCube`

`NCube` representa un hipercubo n-dimensional asociado a un nodo de la TPM. Cada
cubo almacena:

- `indice`: nodo futuro o causal representado;
- `dims`: dimensiones activas del cubo;
- `data`: tensor de probabilidad con forma $(2,)^{|\text{dims}|}$.

Sus operaciones fundamentales son:

- `condicionar(...)`: fija dimensiones según el estado inicial.
- `marginalizar(...)`: promedia dimensiones no conservadas.

Estas operaciones son la base para construir repertorios de efecto y causa
después de aplicar condiciones, sustracciones o particiones.

#### `System`

`System` construye un conjunto de `NCube` a partir de una TPM estado-nodo. Su
responsabilidad es convertir una matriz:

$$
\text{TPM} \in \mathbb{R}^{2^n \times n}
$$

en una colección de hipercubos indexables por nodo.

El sistema soporta:

- validación dimensional de TPM y estado inicial;
- creación de hipercubos forward;
- creación de hipercubos causales cuando se requiere EMD causal o integrada;
- condicionamiento del sistema;
- sustracción de alcance/mecanismo;
- aplicación de particiones k-vías mediante `PartitionSpec`;
- cálculo de distribución marginal.

En modo integrado (`emd-cause-effect`), `System` mantiene dos familias de cubos:

- `ncubos`: repertorio de efecto hacia $t+1$;
- `_ncubos_causales`: repertorio causal hacia $t-1$.

La distribución marginal integrada se representa como concatenación:

$$
P_{\text{integrado}} =
\left[
P_{\text{efecto}},
P_{\text{causa}}
\right]
$$

#### `PartitionSpec`

`PartitionSpec` formaliza una k-partición:

$$
\mathcal{P}_k = \{B_1, B_2, \dots, B_k\}
$$

y mantiene dos componentes:

- `bloques`: partición del alcance/futuro;
- `mecanismos`: partición del mecanismo/presente.

La clase normaliza los bloques, evita nodos repetidos y garantiza que alcance y
mecanismo tengan la misma cantidad de bloques.

### 2.2 KQNodes (`QNodes`): enfoque submodular

KQNodes conserva el flujo de ejecución directa y sirve como base clásica para
comparaciones, experimentación controlada y validación local de estrategias.
Cuando se menciona `QNodes`, el término se refiere al directorio o paquete de
implementación; cuando se describe el método, se utiliza KQNodes.

Flujo principal:

1. `QNodes/exec.py` configura la aplicación y página de muestra.
2. `QNodes/src/main.py` define estado inicial, condiciones, alcance y mecanismo.
3. `Manager` carga una TPM desde `QNodes/src/.samples/`.
4. `BruteForce` o `KForceSIA` prepara el subsistema usando `SIA`.
5. `SIA` construye un `System` de `shared_core`.
6. Se evalúan particiones y se retorna una `Solution`.

Este enfoque es importante porque:

- opera como baseline conceptual;
- permite validar casos pequeños;
- facilita comparar heurísticas contra fuerza bruta;
- conserva scripts de prueba manual para k-particiones.

### 2.3 KGeoMIP (`GeoMIP`): enfoque geométrico y batch

KGeoMIP, implementado en
`GeoMIP/src/Method2_Dynamic_Programming_Reformulation`, materializa el flujo
masivo:

1. `exec.py` inicializa la aplicación.
2. `src/main.py` carga `config.yaml`.
3. `src/pipeline/batch.py` lee subsistemas desde Excel.
4. Cada subsistema se evalúa en proceso separado con timeout.
5. `KGeometricSIA` calcula una partición k-vía eficiente como clase concreta de
   implementación de KGeoMIP.
6. El resultado se escribe en `resultados_Geometric.xlsx`.

La configuración central se encuentra en `config.yaml`:

- `sheet_index`
- `column`
- `skiprows`
- `timeout_seconds`
- `DEFAULT_K_MAX`
- `start`
- `count`

El pipeline batch separa explícitamente:

- lectura Excel;
- resolución de TPM;
- ejecución de estrategia;
- control de timeout;
- extracción de Phi causal/efectual/integrado;
- escritura de resultados.

### 2.4 Análisis visual

`GeoMIP/src/analyze_results.py` lee `resultados_Geometric.xlsx` y genera
`GeoMIP/results/phi_comparison.png`, comparando:

- `Phi_Efecto`;
- `Phi_Causa`.

Esto permite observar asimetría temporal entre repertorios hacia $t+1$ y
$t-1$.

## 3. Fundamentos de k-Particiones y Geometría

### 3.1 Explosión combinatoria

La formulación bipartita tradicional considera particiones con $k=2$. Esta
restricción es útil como punto de partida porque separa el sistema en dos
componentes causalmente comparables, pero no agota las formas en que un sistema
puede perder integración. KGeoMIP extiende la pregunta hacia particiones con:

$$
k \in \{2,3,4,5\}
$$

en las configuraciones operativas actuales, o más generalmente hacia
$2 \le k \le K_{\max}$. El tránsito de biparticiones a k-particiones cambia la
escala matemática del problema: ya no se pregunta solamente qué corte binario
minimiza la pérdida, sino qué descomposición en $k$ bloques no vacíos induce la
menor divergencia entre el repertorio original y el repertorio particionado.

El número de formas de particionar un conjunto de $n$ elementos en exactamente
$k$ bloques no vacíos está dado por los Números de Stirling de segundo tipo:

$$
S(n,k) =
\frac{1}{k!}
\sum_{j=0}^{k}
(-1)^{k-j}
\binom{k}{j}
j^n
$$

Si se permite cualquier cantidad de bloques, el número total de particiones es
el Número de Bell:

$$
B_n = \sum_{k=0}^{n} S(n,k)
$$

Así, $S(n,k)$ mide la complejidad de un tamaño de partición fijo, mientras que
$B_n$ mide la complejidad del espacio completo de particiones. En el problema
MIP extendido, la explosión es todavía más severa porque deben considerarse
particiones compatibles de:

- alcance/futuro;
- mecanismo/presente.

Si alcance y mecanismo se enumeraran de manera independiente, el espacio
candidato tendría una presión combinatoria cercana a productos del tipo
$S(n,k)^2$ para un $k$ fijo, antes de aplicar restricciones de compatibilidad.
Por ello, una búsqueda exhaustiva k-vía tiende a crecer de forma Bell-like y
KGeoMIP no intenta enumerar todo el espacio salvo en estrategias de referencia
como `KForceSIA`, usadas únicamente como oráculo local en sistemas pequeños.

### 3.2 Independencia causal inducida por una partición

Una partición no es solamente una división descriptiva de nodos. En IIT, imponer
una partición equivale a evaluar una hipótesis contrafáctica: los bloques
particionados se tratan como causalmente independientes para reconstruir el
repertorio global. Si una partición se escribe como:

$$
\mathcal{P}_k = \{B_1, B_2,\dots,B_k\}
$$

entonces el repertorio particionado se aproxima mediante el producto tensorial
de los repertorios marginales de cada bloque:

$$
P_{\mathcal{P}_k}(X_{t+1} \mid X_t)
=
\bigotimes_{i=1}^{k}
P_{B_i}(X_{B_i,t+1} \mid X_{B_i,t})
$$

El símbolo $\otimes$ expresa que la dinámica conjunta se reconstruye componiendo
distribuciones marginales, no conservando todas las dependencias del sistema
original. La pérdida de información integrada se mide precisamente al comparar:

$$
P_{\text{subsistema}}(X_{t+1} \mid X_t)
\quad \text{contra} \quad
P_{\mathcal{P}_k}(X_{t+1} \mid X_t)
$$

La misma idea se aplica al repertorio causal hacia $t-1$, donde la partición
induce independencia entre bloques del mecanismo pasado reconstruido. Por tanto,
la MIP no es una partición puramente geométrica: es la partición que, al imponer
independencia causal entre bloques, produce la mínima degradación medible del
repertorio.

### 3.3 Estados binarios e hipercubo n-dimensional

Un sistema binario de $n$ nodos tiene:

$$
2^n
$$

estados posibles. Cada estado puede interpretarse como un vértice de un
hipercubo n-dimensional:

$$
H_n = \{0,1\}^n
$$

Por ejemplo, para $n=3$:

$$
H_3 = \{000,001,010,011,100,101,110,111\}
$$

La TPM estado-nodo:

$$
\text{TPM} \in \mathbb{R}^{2^n \times n}
$$

asigna a cada vértice del hipercubo una probabilidad de activación para cada
nodo futuro. `System` transforma cada columna nodo de la TPM en un `NCube`, de
forma que condicionar y marginalizar corresponden a operaciones geométricas
sobre dimensiones del hipercubo.

### 3.4 Tabla de costos de transiciones

La distancia causal usa una matriz de costos entre estados. En la implementación
actual, `emd_causal` construye una matriz:

$$
C \in \mathbb{R}^{m \times m}
$$

donde:

$$
C_{ij} = d(i,j)
$$

y por defecto:

$$
d(i,j) = \text{Hamming}(i,j)
$$

La distancia de Hamming se calcula como:

$$
\text{Hamming}(i,j) = \text{popcount}(i \oplus j)
$$

Punto clave: esta tabla de costos depende del espacio de estados y de la
métrica, no de $k$. Por tanto, la estructura de transición causal se define una
vez para el espacio de estados y puede reutilizarse masivamente al comparar
particiones con diferente número de bloques.

En KGeoMIP, además de la matriz de costos EMD, se construye una matriz de
distancias de perfiles:

$$
D_{\text{perfil}}(a,b)
$$

mediante Hamming normalizado sobre firmas binarias. Esta matriz también es
independiente de $k$ y se reutiliza en el agrupamiento aglomerativo para
distintos valores de $k$.

## 4. Análisis de Causalidad Temporal ($t-1$ y $t+1$)

La evaluación integrada distingue dos direcciones temporales que no son
intercambiables. El repertorio de efecto pregunta qué futuros son compatibles
con el estado presente, mientras que el repertorio de causa pregunta qué pasados
pudieron haber producido el estado presente observado. Esta asimetría es central
en IIT: aun cuando la TPM forward sea el objeto empírico disponible, el análisis
causal exige reconstruir una distribución hacia $t-1$ y compararla con la
distribución hacia $t+1$.

### 4.1 Repertorio de efecto

El repertorio de efecto describe cómo un estado presente restringe el futuro
del sistema:

$$
P(X_{t+1} \mid X_t)
$$

En la implementación, este repertorio proviene directamente de la TPM forward.
`System` crea `NCube` sobre la TPM original cuando el modo EMD es:

- `emd-effect`
- `emd-cause-effect`

La distribución marginal de efecto se obtiene seleccionando el estado inicial
en cada cubo y aplicando marginalizaciones inducidas por el subsistema o la
partición. Formalmente, el cálculo evalúa cómo la intervención o condición en
$X_t=x_t$ contrae el espacio de futuros posibles en $X_{t+1}$.

### 4.2 Repertorio de causa

El repertorio causal describe cómo un estado futuro observado restringe los
estados pasados posibles:

$$
P(X_{t-1} \mid X_t)
$$

Este repertorio no está almacenado directamente en la TPM forward. Debe
derivarse mediante Bayes:

$$
P(x_{t-1} \mid x_t)
=
\frac{
P(x_t \mid x_{t-1})P(x_{t-1})
}{
P(x_t)
}
$$

Bajo una distribución previa uniforme, la normalización queda determinada por
la evidencia:

$$
P(x_t) = \sum_{x_{t-1}} P(x_t \mid x_{t-1})P(x_{t-1})
$$

El supuesto uniforme no significa que el sistema sea causalmente trivial; sólo
establece que, antes de observar $x_t$, todos los estados pasados se ponderan
por igual. La estructura causal sigue entrando por el término de verosimilitud
$P(x_t \mid x_{t-1})$, obtenido de la TPM forward.

### 4.3 El Rescate Bayesiano

La función `generar_tpm_causal` implementa la conversión forward-to-causal por
lotes. El problema técnico aparece porque una TPM estado-nodo densa induce, al
aplicar Bayes, una relación entre todos los estados pasados y todos los estados
presentes posibles. Para $n$ nodos binarios, esa matriz conceptual tiene:

$$
2^n \times 2^n = 4^n
$$

celdas de verosimilitud. Si se materializa completa junto con tensores
intermedios, el cálculo causal hacia $t-1$ puede colapsar la RAM incluso antes
de evaluar particiones. El Rescate Bayesiano evita ese colapso procesando la
regla de Bayes en lotes acotados por 4.000.000 de celdas operativas.

Con una previa uniforme:

$$
P(x_{t-1}) = \frac{1}{2^n}
$$

el numerador bayesiano puede calcularse por segmentos de estados presentes sin
almacenar la matriz completa. Para cada lote $\mathcal{B}$ de estados actuales,
se evalúa:

$$
N_{\mathcal{B}}(x_{t-1},x_t)
=
P(x_t \mid x_{t-1})P(x_{t-1}),
\quad x_t \in \mathcal{B}
$$

y luego se normaliza por la evidencia:

$$
P(x_{t-1} \mid x_t)
=
\frac{N_{\mathcal{B}}(x_{t-1},x_t)}
{\sum_{x'_{t-1}}N_{\mathcal{B}}(x'_{t-1},x_t)}
$$

La implementación:

1. enumera los estados binarios como enteros;
2. extrae bits mediante operaciones vectorizadas;
3. calcula likelihoods por batch;
4. aplica la previa uniforme;
5. acumula evidencia por columna causal;
6. obtiene numeradores mediante producto matricial;
7. normaliza con `np.divide`;
8. escribe el resultado en una TPM causal compacta.

El tamaño de lote se controla con:

$$
\text{max\_batch\_cells} = 4\,000\,000
$$

y:

$$
\text{batch\_size}
=
\max\left(1,
\min\left(2^n,\left\lfloor
\frac{\text{max\_batch\_cells}}{2^n}
\right\rfloor\right)\right)
$$

Este rediseño es el denominado Rescate Bayesiano: una factorización por lotes
del Teorema de Bayes que evita construir tensores completos de tamaño
prohibitivo. En la práctica de la refactorización, esto redujo una estimación
de consumo de memoria del orden de 120 GB a una huella mucho más cercana a
crecimiento lineal por batch operativo.

La diferencia arquitectónica es decisiva:

- antes: materialización global de estructuras causales densas;
- ahora: procesamiento incremental por bloques de estados con normalización
  bayesiana local por lote.

## 5. Algoritmo KGeoMIP y Heurística

### 5.1 Herencia desde `SIA`

La clase `KGeometricSIA` es la implementación concreta de la estrategia
KGeoMIP y hereda de `SIA`:

$$
\texttt{KGeometricSIA} \subset \texttt{SIA}
$$

La clase base `SIA` aporta:

- gestor de TPM (`Manager`);
- carga de TPM;
- validación de máscaras binarias;
- preparación del subsistema;
- almacenamiento de distribución marginal base;
- temporización.

`KGeometricSIA.__init__` llama:

```python
super().__init__(gestor)
```

Luego configura:

- sesión de profiling;
- métrica integrada;
- `SafeLogger`.

La ejecución principal ocurre en `aplicar_estrategia(...)`, que:

1. activa distancia integrada;
2. llama a `sia_preparar_subsistema(...)`;
3. extrae perfiles por nodo;
4. construye matriz de Hamming entre perfiles;
5. evalúa agrupamientos desde $k=2$ hasta `k_max`;
6. convierte clusters a `PartitionSpec`;
7. aplica la partición sobre `System`;
8. calcula distribución marginal;
9. mide pérdida EMD integrada;
10. retorna la mejor `Solution`.

### 5.2 Perfiles geométricos de nodos

Cada nodo se representa mediante un perfil construido desde los `NCube` del
subsistema. Para un nodo $v$, el perfil contiene:

- valores propios si el nodo tiene cubo asociado;
- firmas de influencia sobre dimensiones donde aparece;
- en modo integrado, concatenación con perfiles causales.

La firma local de una dimensión considera:

$$
\mu_{\text{off}},\quad
\mu_{\text{on}},\quad
|\mu_{\text{on}} - \mu_{\text{off}}|
$$

Esto aproxima cómo cambia el repertorio al activar o desactivar una dimensión.

### 5.3 Matriz Hamming de perfiles

KGeoMIP binariza perfiles con umbral:

$$
x \ge 0.5
$$

y calcula distancia Hamming normalizada:

$$
D(i,j) =
\frac{1}{p}
\sum_{\ell=1}^{p}
\mathbf{1}
\left[
b_{i\ell} \ne b_{j\ell}
\right]
$$

Esta matriz resume similitud geométrica/causal entre nodos y sirve como base
para clustering.

### 5.4 Agrupamiento aglomerativo

El agrupamiento inicia con cada nodo como cluster independiente:

$$
\mathcal{C}_0 = \{\{v_1\}, \{v_2\}, \dots, \{v_n\}\}
$$

Luego fusiona iterativamente el par de clusters con menor distancia promedio:

$$
d(A,B)
=
\frac{1}{|A||B|}
\sum_{a \in A}
\sum_{b \in B}
D(a,b)
$$

El proceso se detiene cuando quedan $k$ clusters. Cada cluster se proyecta a:

- bloque de alcance;
- bloque de mecanismo.

La conversión se formaliza con `PartitionSpec`.

### 5.5 Complejidad

Un oráculo exhaustivo de MIP que evalúa todas las particiones arbitrarias del
sistema tiene complejidad estructural asociada a los Números de Bell:

$$
O(B_n)
$$

donde:

$$
B_n = \sum_{k=0}^{n} S(n,k)
$$

Esto crece super-exponencialmente y hace inviable una enumeración exacta en
sistemas grandes. Para un $k$ fijo, el coste combinatorio correspondiente es
$O(S(n,k))$; al permitir todos los valores de $k$, la suma de esos términos
recupera $O(B_n)$. En formulaciones que separan alcance y mecanismo, esta
presión puede aumentar por combinaciones compatibles entre ambas particiones,
por lo que $O(B_n)$ debe leerse como el umbral combinatorio central, no como una
cota optimista de implementación.

KGeoMIP reemplaza esa enumeración por:

- extracción de perfiles sobre estructuras `NCube`;
- cálculo único y cacheado de la matriz de Hamming de perfiles de tamaño
  $n \times n$;
- clustering aglomerativo acotado por `DEFAULT_K_MAX`;
- evaluación de una partición candidata por cada $k$.

La reducción práctica proviene de una regla de reutilización estricta: los
costos geométricos entre nodos no se recalculan para cada valor de $k$. La
matriz de Hamming se calcula y se cachea exactamente una vez, y los agrupamientos
para distintos tamaños de partición reutilizan esa misma estructura. Así, el
paso exponencial dominante queda asociado a preparar perfiles y distribuciones
en el espacio de estados binarios:

$$
O(n \cdot 2^n)
$$

mientras que la búsqueda sobre $k$ deja de enumerar particiones Bell y pasa a
recorrer una secuencia acotada de candidatos geométricamente inducidos:

$$
k \in \{2,\dots,K_{\max}\}
$$

El coste adicional del clustering aglomerativo directo es polinomial:

$$
O(n^3)
$$

Esta complejidad no convierte el cálculo de IIT en un problema polinomial en
sentido fuerte, porque los repertorios siguen viviendo sobre $2^n$ estados y EMD
mantiene su propio coste de optimización. La contribución de KGeoMIP es más
precisa: sustituye la enumeración $O(B_n)$ del oráculo por una aproximación
heurística donde el coste combinatorio de variar $k$ queda absorbido por
reutilización geométrica y por el límite operativo `DEFAULT_K_MAX`.

### 5.6 Pruebas de estrés multiescala

Después de desacoplar $N$ desde `config.yaml`, el pipeline batch pudo validar
redes de distintas hojas Excel sin asumir que la dimensión del sistema coincidía
con la hoja activa. Las ejecuciones recientes muestran el siguiente
comportamiento operativo:

| Escala | Fuente Excel | Tiempo promedio por iteración | Memoria observada | Resultado operativo |
| --- | --- | --- | --- | --- |
| N=3 | Hoja 0 | <1 segundo | insignificante (~50 MB) | Instantáneo |
| N=5 | Hoja 2 | ~4 segundos | estable (~100 MB) | Escala fluida |
| N=15 | Hoja 6 | ~75 segundos | acotada (~180 MB) | Éxito con heurística acotada |

Estos resultados no eliminan el crecimiento exponencial del espacio causal, pero
sí confirman que la arquitectura actual sostiene evaluación multiescala cuando
la búsqueda se mantiene acotada por heurística geométrica, límites de $k$ y
procesamiento por lotes.

### 5.7 Caso de borde y resiliencia

Durante la validación multiescala se capturó de forma segura un error
estructural:

```text
La solución integrada no contiene distribuciones concatenadas pares
```

El caso apareció en el Subsistema 19, donde el alcance/mecanismo colapsó a
tamaño 1 dentro de una red leída con dimensión de 15 nodos
(`estado=100000000000000`). La condición invalidó la expectativa estructural
del cálculo integrado, que requiere distribuciones de causa y efecto
concatenadas de forma par.

El comportamiento relevante no es ocultar el error, sino aislarlo
correctamente. Gracias al wrapper de seguridad, al aislamiento por timeout y a
`SafeLogger`, el pipeline registró la fila problemática, evitó detener la
ejecución global y completó de forma autónoma el lote completo de 25 sistemas.
Esto confirma una propiedad práctica de resiliencia batch: los fallos locales se
conservan como evidencia diagnóstica sin comprometer el procesamiento del resto
del experimento.

### 5.8 Límite físico-algorítmico observado

El cuello de botella dominante sigue siendo el cálculo de distancia EMD mediante
Programación Lineal. En un portátil convencional, el máximo práctico para
evaluar un subsistema con todos los nodos interconectados y activos
simultáneamente se ubica alrededor de $N=12$ o $N=13$, porque la matriz de costo
de transporte crece exponencialmente con el espacio de estados.

Esta cota no implica que el software quede limitado a universos pequeños. El
pipeline puede procesar universos de $N=20$ o mayores cuando los subsistemas
efectivamente evaluados son acotados, dispersos o restringidos en alcance activo.
En otras palabras, el límite crítico depende del tamaño efectivo del problema
EMD resuelto en cada fila, no únicamente del número nominal de nodos del universo
Excel.

## 6. Validación y Regresión

La validación se apoya en tres niveles y debe interpretarse con una distinción
metodológica explícita: los oráculos exactos sólo son viables en sistemas
pequeños, mientras que en redes de mayor escala KGeoMIP opera como aproximación
heurística informada por geometría causal. Por tanto, la evidencia empírica a
escala no sustituye la prueba exhaustiva; la complementa bajo restricciones de
coste computacional.

### 6.1 Consistencia con bipartición ($k=2$)

Para $k=2$, KGeoMIP debe ser consistente con el caso tradicional de MIP
bipartita. El repositorio conserva estrategias de referencia:

- `BruteForce`
- `KForceSIA`
- `KGeometricSIA`

La consistencia se evalúa verificando que:

- se genere una partición válida;
- se preserve cobertura de nodos;
- la distribución de partición sea comparable con la del subsistema;
- `Phi_Integrado` sea finito y separable en causa/efecto.

### 6.2 Fuerza bruta como ground truth local

`KForceSIA` enumera k-particiones en sistemas pequeños y funciona como ground
truth interno para evaluar la heurística. Aunque no es viable para sistemas
grandes, es útil en redes pequeñas porque permite comprobar:

$$
\Phi_{\text{heurística}}
\ge
\Phi_{\text{óptimo exacto}}
$$

cuando ambos algoritmos evalúan el mismo espacio.

### 6.3 PyPhi como oráculo externo

PyPhi se conserva como dependencia en los subproyectos y actúa como oráculo de
verdad para sistemas pequeños, donde el cálculo exacto es computacionalmente
posible. Su rol académico es contrastar:

- repertorios de causa;
- repertorios de efecto;
- pérdidas de información;
- coherencia de la MIP bipartita.

PyPhi no se usa como motor principal para redes grandes porque su coste
combinatorio y memoria requerida crecen rápidamente. En cambio, se usa como
referencia para validar implementaciones propias en casos reducidos.

### 6.4 Pruebas automatizadas actuales

La suite de pruebas cubre:

- `NCube`
- `System`
- `KForceSIA`, como clase de fuerza bruta para oráculo local;
- `KGeometricSIA`, como clase de implementación de KGeoMIP;
- generación visual con `analyze_results.py`

Los tests de estrategias usan TPM pequeñas para garantizar convergencia y
evitar explosión de memoria durante integración continua.

## 7. Impacto de la Arquitectura en la Viabilidad del Cálculo Causal

La viabilidad de KGeoMIP proviene de decisiones arquitectónicas específicas:

- centralizar `System` y `NCube` en `shared_core`;
- representar repertorios como hipercubos marginalizables;
- calcular TPM causal por lotes;
- separar pipeline batch de estrategia;
- convertir particiones a objetos inmutables (`PartitionSpec`);
- limitar búsqueda mediante `DEFAULT_K_MAX`;
- usar heurística geométrica en lugar de enumeración Bell completa.

Estas decisiones convierten un problema inicialmente dominado por:

$$
O(B_n)
$$

en un flujo práctico donde los pasos dominantes dependen de:

$$
O(n \cdot 2^n)
$$

y de operaciones polinomiales sobre una matriz de distancia entre nodos.
Esta conversión depende de que la matriz de costos geométricos se compute una
sola vez y se reutilice al comparar diferentes valores de $k$, evitando
recalcular Hamming para cada partición candidata.

## 8. Limitaciones y Trabajo Futuro

### 8.1 Dependencia del procesamiento iterativo

Aunque el procesamiento por lotes reduce memoria, el sistema todavía depende
de iteraciones sobre subsistemas. En ejecuciones masivas, el tiempo total puede
seguir siendo alto porque cada fila del Excel activa:

- preparación de subsistema;
- construcción de perfiles;
- evaluación de particiones candidatas;
- cálculo de EMD integrada.

La paralelización por proceso permite controlar timeouts, pero también añade
coste de serialización y arranque.
La consecuencia metodológica es que los tiempos reportados deben interpretarse
como tiempos del pipeline completo, no como una medida pura del coste matemático
de una única operación IIT.

### 8.2 Sensibilidad al estado inicial

Los repertorios causales y efectuales dependen del estado inicial:

$$
x_t
$$

En sistemas grandes, pequeñas variaciones del estado pueden cambiar:

- dimensiones condicionadas;
- marginales observados;
- perfiles geométricos;
- clusters generados;
- partición seleccionada.

Por tanto, una extensión futura relevante es estudiar estabilidad de la MIP
frente a múltiples estados iniciales. Una validación académica más fuerte debe
reportar si la partición seleccionada es robusta bajo perturbaciones de $x_t$ o
si corresponde a una configuración causal local altamente dependiente del estado
observado.

### 8.3 Heurística no exacta

KGeoMIP no garantiza encontrar la MIP global para todo $k$. Su objetivo es
aproximar una partición informada causalmente con coste viable. Desde el punto
de vista matemático, el agrupamiento aglomerativo es una heurística codiciosa:
una vez que fusiona dos clusters, no reabre esa decisión. Por tanto, en sistemas
ruidosos o con señales causales débiles puede converger a un mínimo local que no
coincida con la partición globalmente óptima. La heurística puede fallar si:

- la geometría de perfiles no refleja la pérdida EMD real;
- existen interacciones de alto orden no capturadas por promedios de perfiles;
- la primera fusión codiciosa bloquea una combinación posterior mejor;
- el valor óptimo requiere $k > K_{\max}$.

### 8.4 Validación externa limitada por tamaño

PyPhi es útil como oráculo en sistemas pequeños, pero no resuelve la validación
exhaustiva en sistemas grandes. Para redes grandes, la evidencia debe
combinar:

- regresión en casos pequeños;
- comparación contra fuerza bruta acotada;
- análisis estadístico de lotes;
- inspección visual de asimetría temporal;
- estabilidad ante variaciones de configuración.

### 8.5 Persistencia del cuello de botella EMD

El Rescate Bayesiano y la reutilización de Hamming reducen memoria y evitan
enumerar el espacio Bell completo, pero no eliminan el cuello de botella de EMD.
La distancia Earth Mover's Distance se resuelve mediante Programación Lineal, y
su matriz de transporte crece con el número de estados activos. Por esta razón,
la computación práctica de subsistemas completamente activos se mantiene
limitada alrededor de N=12 o N=13 en hardware convencional.

Este límite debe comunicarse con precisión: KGeoMIP puede procesar universos
nominales mayores cuando el subsistema evaluado es pequeño, disperso o acotado,
pero el caso completamente activo sigue dominado por el coste de EMD. En
términos de trabajo futuro, las rutas razonables incluyen aproximaciones de EMD,
relajaciones de transporte, poda por cotas inferiores y validación empírica de
cuándo esas aproximaciones preservan el orden relativo de las particiones.

## 9. Conclusión

KGeoMIP extiende el análisis MIP desde biparticiones hacia k-particiones
mediante una arquitectura diseñada para sostener cálculo causal en sistemas
grandes. La contribución central no es únicamente algorítmica, sino también
arquitectónica: separar el núcleo causal (`shared_core`), conservar un enfoque
submodular de referencia KQNodes (`QNodes`) y construir un flujo geométrico batch
KGeoMIP (`GeoMIP`) permite que el análisis de causa y efecto sea reproducible,
testeable y escalable.

El "Rescate Bayesiano" por lotes y la reutilización de matrices geométricas
independientes de $k$ son los elementos que hacen viable el cálculo. Frente a
la explosión combinatoria asociada a los Números de Bell, KGeoMIP propone una
heurística polinomialmente manejable que preserva interpretabilidad causal y
permite experimentación empírica masiva.

En términos académicos, el proyecto establece una plataforma para estudiar la
asimetría temporal de la información integrada y explorar particiones de orden
superior sin quedar limitado por la enumeración exhaustiva del espacio de
particiones.
