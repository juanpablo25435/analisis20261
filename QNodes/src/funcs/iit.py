from itertools import product
from typing import Callable

import numpy as np
from numpy.typing import NDArray

from src.constants.base import (
    ABC_START,
    EMPTY_STR,
    INT_ZERO,
    STR_ONE,
    VOID_STR,
)
from src.middlewares.slogger import SafeLogger
from src.models.base.application import aplicacion
from src.models.enums.distance import MetricDistance
from src.models.enums.notation import Notation
from src.models.enums.temporal_emd import TimeEMD


IIT_LOGGER = SafeLogger("iit_temporal_emd")


# @cache
def get_labels(n: int) -> tuple[str, ...]:
    """
    Genera las etiquetas STR en formato Excel para un sistema de n nodos.

    Args:
        n (int): El número de nodos.

    Returns:
        tuple[str, ...]: Las etiquetas como String en formato Excel para un sistema de n nodos.
    """

    def get_excel_column(n: int) -> str:
        if n <= 0:
            return ""
        return get_excel_column((n - 1) // 26) + chr((n - 1) % 26 + ord(ABC_START))

    return tuple([get_excel_column(i) for i in range(1, n + 1)])


ABECEDARY = get_labels(40)
LOWER_ABECEDARY = [letter.lower() for letter in ABECEDARY]


def literales(remaining_vars: NDArray[np.int8], lowercase: bool = False):
    """
    Genera las literales para un sistema de n nodos.

    Args:
        remaining_vars (NDArray[np.int8]): Los nodos restantes.
        lowercase (bool, optional): Si se deben usar letras minúsculas. Defaults to False.

    Returns:
        str: Las letras para un sistema de n nodos.
    """
    return (
        EMPTY_STR.join(
            ABECEDARY[i].lower() if lowercase else ABECEDARY[i] for i in remaining_vars
        )
        if remaining_vars.size
        else VOID_STR
    )


def seleccionar_emd(
    tipo_emd: TimeEMD | str | None = None,
) -> Callable[
    [NDArray[np.float32], NDArray[np.float32]],
    float,
]:
    """
    Selecciona la métrica de EMD a utilizar.

    Args:
        distancia_usada (str): La métrica de EMD a utilizar.

    Returns:
        dict: La función de la métrica de EMD seleccionada.
    """
    emd_metricas: dict[
        str, Callable[[NDArray[np.float32], NDArray[np.float32]], float]
    ] = {
        TimeEMD.EMD_EFECTO.value: emd_efecto,
        TimeEMD.EMD_CAUSA.value: emd_causal,
        TimeEMD.EMD_INTEGRADA.value: emd_integrada,
    }
    emd_tiempo = resolver_tiempo_emd(tipo_emd)

    if emd_tiempo not in emd_metricas:
        metricas_disponibles = ", ".join(sorted(emd_metricas.keys()))
        raise ValueError(
            f"Tiempo EMD no soportado: '{emd_tiempo}'. "
            f"Opciones disponibles: {metricas_disponibles}"
        )

    return emd_metricas[emd_tiempo]


def resolver_tiempo_emd(tipo_emd: TimeEMD | str | None = None) -> str:
    if tipo_emd is not None:
        return tipo_emd.value if isinstance(tipo_emd, TimeEMD) else str(tipo_emd)
    tiempo_configurado = aplicacion.tiempo_emd
    return (
        tiempo_configurado.value
        if isinstance(tiempo_configurado, TimeEMD)
        else str(tiempo_configurado)
    )


def generar_tpm_causal(tpm_forward: NDArray) -> NDArray[np.float32]:
    """
    Construye una TPM factorizada hacia el pasado mediante la regla de Bayes.

    La entrada representa P(X_t^j=1 | X_{t-1}=x) por fila de estado pasado y
    columna de nodo futuro. La salida conserva el formato arquitectónico:
    P(X_{t-1}^j=1 | X_t=y) por fila de estado actual/futuro y nodo pasado.
    """
    tpm_forward = np.asarray(tpm_forward, dtype=np.float64)
    if tpm_forward.ndim != 2:
        raise ValueError("La TPM forward debe ser una matriz 2D estado->nodo.")

    num_estados, num_nodos = tpm_forward.shape
    if num_estados != 1 << num_nodos:
        raise ValueError(
            "La TPM forward debe tener 2^n filas para n columnas/nodos."
        )
    if np.any((tpm_forward < 0) | (tpm_forward > 1)):
        raise ValueError("La TPM forward contiene probabilidades fuera de [0, 1].")

    estados = np.arange(num_estados, dtype=np.uint64)
    shifts = np.arange(num_nodos, dtype=np.uint64)
    bits_estado = ((estados[:, None] >> shifts) & 1).astype(np.float64)

    tpm_causal = np.empty((num_estados, num_nodos), dtype=np.float32)
    max_batch_cells = 4_000_000
    batch_size = max(1, min(num_estados, max_batch_cells // num_estados))

    probs_on = tpm_forward
    probs_off = 1 - tpm_forward

    for batch_start in range(0, num_estados, batch_size):
        batch_end = min(batch_start + batch_size, num_estados)
        bits_futuros = bits_estado[batch_start:batch_end]

        # 1) Expandimos P(X_t^j | X_{t-1}) a P(X_t=y | X_{t-1}=x)
        # por lotes. Solo existe una matriz (S,B), nunca el tensor (S,S,N).
        likelihood = np.ones(
            (num_estados, batch_end - batch_start),
            dtype=np.float64,
        )
        for nodo in range(num_nodos):
            likelihood *= np.where(
                bits_futuros[None, :, nodo] == 1,
                probs_on[:, None, nodo],
                probs_off[:, None, nodo],
            )

        # 2) Con prior uniforme, Bayes cancela el factor 1/S:
        # P(x_{t-1}|y) = P(y|x_{t-1}) / sum_x P(y|x).
        evidencia = np.sum(likelihood, axis=0)

        # 3) Volvemos al formato factorizado estado->nodo:
        # E[bit_i(X_{t-1}) | X_t=y] para todos los nodos i del batch.
        numeradores = likelihood.T @ bits_estado
        tpm_causal[batch_start:batch_end] = np.divide(
            numeradores,
            evidencia[:, None],
            out=np.full(
                (batch_end - batch_start, num_nodos),
                1 / 2,
                dtype=np.float64,
            ),
            where=evidencia[:, None] > 0,
        ).astype(np.float32)

    return tpm_causal


def emd_efecto(u: NDArray[np.float32], v: NDArray[np.float32]) -> float:
    """
    Solución analítica de la Earth Mover's Distance basada en variables independientes condicionalmente y la EMD como distribuciones marginales de probabilidad.
    Sean `X_1`, `X_2` dos variables aleatorias con su correspondiente espacio de estados. Si `X_1` y `X_2` son independientes y `u_1`, `v_1` dos distribuciones de probabilidad en `X_1` y `u_2`, `v_2` dos distribuciones de probabilidad en `X_2`.

    Args:
        `u` (NDArray[np.float32]): Histograma/distribución/vector/serie donde cada indice asocia un valor de pobabilidad de tener el nodo en estado ON/OFF.
        `v` (NDArray[np.float32]): Histograma/distribución/vector/serie donde cada indice asocia un valor de pobabilidad de tener el nodo en estado ON/OFF.

    Returns:
        float: La EMD entre los repertorios efecto es igual a la suma entre las EMD de las distribuciones marginales de cada nodo y, la EMD entre las distribuciones marginales para un nodo es la diferencia absoluta entre las probabilidades con el nodo ON/OFF.
    """
    return np.sum(np.abs(u - v))


def emd_integrada(u: NDArray[np.float32], v: NDArray[np.float32]) -> float:
    """
    EMD integrada como suma efecto + causa para distribuciones concatenadas.

    `System` en modo integrado retorna `[marginales_forward, marginales_backward]`;
    ambas mitades deben tener el mismo tamaño para evaluar la misma partición.
    """
    if u.size != v.size or u.size % 2 != 0:
        raise ValueError("EMD integrada requiere distribuciones concatenadas pares.")

    mitad = u.size // 2
    return emd_efecto(u[:mitad], v[:mitad]) + emd_causal(u[mitad:], v[mitad:])


def emd_causal(u: NDArray[np.float64], v: NDArray[np.float64]) -> float:
    """
    Implementación de la Earth Mover's Distance para el análissi desde el presente hacia el pasado.
    Sean `X_1`, `X_2` dos variables aleatorias con su correspondiente espacio de estados. Si `X_1` y `X_2` son dependientes y `u_1`, `v_1` dos distribuciones de probabilidad en `X_1` y `u_2`, `v_2` dos distribuciones de probabilidad en `X_2`.

    Args:
        `u` (NDArray[np.float64]): Histograma/distribución/vector/serie donde cada indice asocia un valor de pobabilidad de tener el nodo en estado OFF.
        `v` (NDArray[np.float64]): Histograma/distribución/vector/serie donde cada indice asocia un valor de pobabilidad de tener el nodo en estado OFF.

    Returns:
        float: La EMD entre los repertorios causal es igual a la suma entre las EMD de las distribuciones marginales de cada nodo, de forma que la EMD entre las distribuciones marginales para un nodo es la diferencia absoluta entre las probabilidades con el nodo OFF.
    """
    try:
        from pyemd import emd
    except ImportError as error:
        IIT_LOGGER.warn(
            "No se pudo importar pyemd para EMD causal. "
            "Instala la dependencia compatible antes de usar TimeEMD.EMD_CAUSA "
            "o TimeEMD.EMD_INTEGRADA.",
            error,
        )
        raise RuntimeError("pyemd es requerido para calcular EMD causal.") from error

    if not all(isinstance(arr, np.ndarray) for arr in [u, v]):
        raise TypeError("u and v must be numpy arrays.")

    u_causal = np.asarray(u, dtype=np.float64)
    v_causal = np.asarray(v, dtype=np.float64)
    n: int = u_causal.size
    coste: NDArray[np.float64] = np.empty((n, n))
    distancia_metrica: Callable = seleccionar_distancia()

    for i in range(n):
        coste[i, :i] = [distancia_metrica(i, j) for j in range(i)]
        coste[:i, i] = coste[i, :i]
    np.fill_diagonal(coste, INT_ZERO)

    mat_costes: NDArray[np.float64] = np.array(coste, dtype=np.float64)
    return emd(u_causal, v_causal, mat_costes)


def seleccionar_distancia() -> Callable[
    [NDArray[np.float32], NDArray[np.float32]],
    float,
]:
    """
    Selecciona la métrica de distancia a utilizar.
    """
    distancias_metricas: dict[
        str, Callable[[NDArray[np.float32], NDArray[np.float32]], float]
    ] = {
        MetricDistance.HAMMING.value: hamming_distance,
        # MetricDistance.EUCLIDIANA.value: euclidean_distance,
        # MetricDistance.MANHATTAN.value: manhattan_distance,
        # ...otras
    }
    distancia = (
        aplicacion.distancia_metrica.value
        if isinstance(aplicacion.distancia_metrica, MetricDistance)
        else str(aplicacion.distancia_metrica)
    )
    if distancia not in distancias_metricas:
        opciones = ", ".join(sorted(distancias_metricas.keys()))
        raise ValueError(
            f"Distancia métrica no soportada: '{distancia}'. "
            f"Opciones disponibles: {opciones}"
        )
    return distancias_metricas[distancia]


def hamming_distance(a: int, b: int) -> int:
    """
    Implementación de la distancia de Hamming.

    Args:
        a (int): Primer número a comparar.
        b (int): Segundo número a comparar.

    Returns:
        int: La distancia de Hamming entre los dos números.
    """
    return count_bits(a ^ b)


def count_bits(n: int) -> int:
    """
    Cuenta el número de bits en uno de la representación binaria de un número.

    Args:
        n (int): El número binario a contar sus bits en uno.

    Returns:
        int: El número de bits en uno de la representación binaria de n.
    """
    return bin(n).count(STR_ONE)


def reindexar(n: int) -> np.ndarray:
    """
    Genera una secuencia de números en una notación específica.
    """
    notaciones = {
        Notation.BIG_ENDIAN.value: big_endian(n),
        Notation.LIL_ENDIAN.value: lil_endian(n),
        # ...otras
    }
    notacion = (
        aplicacion.notacion_indexado.value
        if isinstance(aplicacion.notacion_indexado, Notation)
        else str(aplicacion.notacion_indexado)
    )
    if notacion not in notaciones:
        opciones = ", ".join(sorted(notaciones.keys()))
        raise ValueError(
            f"Notación de indexado no soportada: '{notacion}'. "
            f"Opciones disponibles: {opciones}"
        )
    return notaciones[notacion]


def seleccionar_estado(subestado: np.ndarray) -> np.ndarray:
    """
    Selecciona el estado de un n-cubo según la notación específica utilizada en el sistema.
    """
    # posible in-deducción por acceso inverso
    notaciones = {
        Notation.BIG_ENDIAN.value: subestado,
        Notation.LIL_ENDIAN.value: subestado[::-1],
        # ...otras
    }
    notacion = (
        aplicacion.notacion_indexado.value
        if isinstance(aplicacion.notacion_indexado, Notation)
        else str(aplicacion.notacion_indexado)
    )
    if notacion not in notaciones:
        opciones = ", ".join(sorted(notaciones.keys()))
        raise ValueError(
            f"Notación de estado no soportada: '{notacion}'. "
            f"Opciones disponibles: {opciones}"
        )
    return notaciones[notacion]


def big_endian(n: int) -> np.ndarray:
    """
    Implementación para generación de números en notación big endian.
    """
    return np.array(range(n), dtype=np.uint32)


def lil_endian(n: int) -> np.ndarray:
    """
    Implementación final optimizada para generación de números en notación little endian.
    """
    if n <= 0:
        # Caso especial para n=0
        return np.array([0], dtype=np.uint32)

    size = 1 << n
    result = np.zeros(size, dtype=np.uint32)

    # Optimización de parámetros basada en n
    block_bits = max(12, min(16, 28 - int(np.log2(n))))
    block_size = 1 << block_bits

    # Precomputar shifts de una vez
    shifts = np.array([n - i - 1 for i in range(n)], dtype=np.uint32)

    # Pre-alocar buffer para procesamientos por bloque
    block_result = np.zeros(block_size, dtype=np.uint32)

    # Determinar tamaño óptimo de grupo de bits
    bit_group_size = 6 if n > 24 else 4  # Ajuste basado en pruebas empíricas

    for start in range(0, size, block_size):
        end = min(start + block_size, size)
        current_size = end - start

        # Reset eficiente del buffer
        block_result[:current_size] = 0
        block_indices = np.arange(start, end, dtype=np.uint32)

        # Procesar bits en grupos optimizados
        for base_bit in range(0, n, bit_group_size):
            bits_remaining = min(bit_group_size, n - base_bit)
            if bits_remaining <= 0:
                break

            # Optimización: procesamiento de múltiples bits de una vez
            group_mask = np.uint32((1 << bits_remaining) - 1)
            group_values = (block_indices >> base_bit) & group_mask

            for j in range(bits_remaining):
                shift = shifts[base_bit + j]
                bit_value = (group_values >> j) & np.uint32(1)
                block_result[:current_size] |= bit_value << shift

        result[start:end] = block_result[:current_size]

    return result


def get_restricted_combinations(binary_str: str) -> tuple[list[str], list[str]]:
    """
    Genera las combinaciones para B y C basadas en la cadena binaria A.
    B solo puede tener 1s donde A tiene 1s.
    """
    # Contar cuántos 1s hay en la cadena
    ones_count = binary_str.count("1")
    width = len(binary_str)

    # Encontrar las posiciones de los 1s en A
    one_positions = [i for i, bit in enumerate(binary_str) if bit == "1"]

    def generate_valid_combinations():
        # Generamos todas las combinaciones posibles de 0s y 1s para las posiciones donde A tiene 1s
        base_combinations = list(product(["0", "1"], repeat=ones_count))
        valid_combinations = []

        # Para cada combinación base, creamos una cadena del ancho total
        for comb in base_combinations:
            # Empezamos con todos 0s
            result = ["0"] * width
            # Colocamos los bits de la combinación en las posiciones donde A tiene 1s
            for pos, bit in zip(one_positions, comb):
                result[pos] = bit
            valid_combinations.append("".join(result))

        return valid_combinations

    # B tiene restricciones, C no
    B = generate_valid_combinations()
    C = (
        B.copy()
    )  # En este caso C es igual a B, pero podría ser diferente si se necesita

    return B, C


def generate_combinations(A: str) -> list[tuple[str, str, str]]:
    """
    Genera el producto cartesiano final de A con las combinaciones válidas de B y C.
    """
    B, C = get_restricted_combinations(A)
    # Convertimos A, B y C en formato "XX XX XX"
    formatted_B = [EMPTY_STR.join(b[i : i + 2] for i in range(0, len(b), 2)) for b in B]
    formatted_C = [EMPTY_STR.join(c[i : i + 2] for i in range(0, len(c), 2)) for c in C]
    formatted_A = EMPTY_STR.join(A[i : i + 2] for i in range(0, len(A), 2))

    # Generamos el producto cartesiano
    return list(product([formatted_A], formatted_B, formatted_C))[1:]


def dec2bin(decimal: int, width: int) -> str:
    """
    Convierte un número decimal a su representación binaria.

    Args:
        decimal (int): El número decimal a convertir.
        width (int): El ancho de la representación binaria.

    Returns:
        str: La representación binaria del número decimal.
    """
    return format(decimal, f"0{width}b")


def estados_binarios(n: int) -> list[str]:
    """
    Genera los estados binarios para un sistema de n nodos.
    """
    return [dec2bin(i, n) for i in range(1 << n)][1:]
