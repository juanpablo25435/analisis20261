from collections.abc import Callable
from itertools import product

import numpy as np
from numpy.typing import NDArray

ABC_START = "A"
EMPTY_STR = ""
STR_ONE = "1"
VOID_STR = "∅"
BIG_ENDIAN = "big-endian"
LITTLE_ENDIAN = "little-endian"
EMD_EFFECT = "emd-effect"
EMD_CAUSE = "emd-cause"
EMD_INTEGRATED = "emd-cause-effect"
HAMMING = "distancia-hamming"


def enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def get_labels(n: int) -> tuple[str, ...]:
    def get_excel_column(index: int) -> str:
        if index <= 0:
            return ""
        return get_excel_column((index - 1) // 26) + chr((index - 1) % 26 + ord(ABC_START))

    return tuple(get_excel_column(index) for index in range(1, n + 1))


ABECEDARY = get_labels(40)
LOWER_ABECEDARY = [letter.lower() for letter in ABECEDARY]


def literales(remaining_vars: NDArray[np.int8], lowercase: bool = False, lower: bool = False) -> str:
    use_lowercase = lowercase or lower
    return (
        EMPTY_STR.join(
            ABECEDARY[i].lower() if use_lowercase else ABECEDARY[i]
            for i in remaining_vars
        )
        if remaining_vars.size
        else VOID_STR
    )


def generar_tpm_causal(tpm_forward: NDArray) -> NDArray[np.float32]:
    tpm_forward = np.asarray(tpm_forward, dtype=np.float64)
    if tpm_forward.ndim != 2:
        raise ValueError("La TPM forward debe ser una matriz 2D estado->nodo.")

    num_estados, num_nodos = tpm_forward.shape
    if num_estados != 1 << num_nodos:
        raise ValueError("La TPM forward debe tener 2^n filas para n columnas/nodos.")
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

        evidencia = np.sum(likelihood, axis=0)
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
    return float(np.sum(np.abs(u - v)))


def emd_integrada(u: NDArray[np.float32], v: NDArray[np.float32]) -> float:
    if u.size != v.size or u.size % 2 != 0:
        raise ValueError("EMD integrada requiere distribuciones concatenadas pares.")

    mitad = u.size // 2
    return emd_efecto(u[:mitad], v[:mitad]) + emd_causal(u[mitad:], v[mitad:])


def emd_causal(
    u: NDArray[np.float64],
    v: NDArray[np.float64],
    *,
    logger: object | None = None,
    metric_fn: Callable[[int, int], int] | None = None,
) -> float:
    try:
        from pyemd import emd
    except ImportError as error:
        if logger is not None and hasattr(logger, "warn"):
            logger.warn("No se pudo importar pyemd para EMD causal/integrada.", error)
        raise RuntimeError("pyemd es requerido para calcular EMD causal.") from error

    if not all(isinstance(arr, np.ndarray) for arr in [u, v]):
        raise TypeError("u and v must be numpy arrays.")

    distancia = metric_fn or hamming_distance
    u_causal = np.asarray(u, dtype=np.float64)
    v_causal = np.asarray(v, dtype=np.float64)
    n = u_causal.size
    coste: NDArray[np.float64] = np.empty((n, n))

    for i in range(n):
        coste[i, :i] = [distancia(i, j) for j in range(i)]
        coste[:i, i] = coste[i, :i]
    np.fill_diagonal(coste, 0)

    return float(emd(u_causal, v_causal, np.array(coste, dtype=np.float64)))


def seleccionar_emd(tiempo_emd: object | None = None) -> Callable:
    emd_tiempo = enum_value(tiempo_emd or _active_emd_mode())
    metricas = {
        EMD_EFFECT: emd_efecto,
        EMD_CAUSE: emd_causal,
        EMD_INTEGRATED: emd_integrada,
    }
    if emd_tiempo not in metricas:
        opciones = ", ".join(sorted(metricas.keys()))
        raise ValueError(f"Tiempo EMD no soportado: '{emd_tiempo}'. Opciones disponibles: {opciones}")
    return metricas[emd_tiempo]


def seleccionar_metrica(tiempo_emd: object | None = None) -> Callable:
    return seleccionar_emd(tiempo_emd)


def seleccionar_distancia(distancia_metrica: object | None = None) -> Callable[[int, int], int]:
    distancia = enum_value(distancia_metrica or _active_distance_mode())
    distancias = {HAMMING: hamming_distance}
    if distancia not in distancias:
        opciones = ", ".join(sorted(distancias.keys()))
        raise ValueError(
            f"Distancia métrica no soportada: '{distancia}'. Opciones disponibles: {opciones}"
        )
    return distancias[distancia]


def hamming_distance(a: int, b: int) -> int:
    return count_bits(a ^ b)


def count_bits(n: int) -> int:
    return bin(n).count(STR_ONE)


def reindexar(n: int, notacion_indexado: object = LITTLE_ENDIAN) -> np.ndarray:
    notacion = enum_value(notacion_indexado)
    notaciones = {
        BIG_ENDIAN: big_endian(n),
        LITTLE_ENDIAN: lil_endian(n),
    }
    if notacion not in notaciones:
        opciones = ", ".join(sorted(notaciones.keys()))
        raise ValueError(
            f"Notación de indexado no soportada: '{notacion}'. Opciones disponibles: {opciones}"
        )
    return notaciones[notacion]


def seleccionar_estado(subestado: tuple[int, ...], notacion_indexado: object = LITTLE_ENDIAN):
    notacion = enum_value(notacion_indexado)
    notaciones = {
        BIG_ENDIAN: subestado,
        LITTLE_ENDIAN: subestado[::-1],
    }
    if notacion not in notaciones:
        opciones = ", ".join(sorted(notaciones.keys()))
        raise ValueError(
            f"Notación de estado no soportada: '{notacion}'. Opciones disponibles: {opciones}"
        )
    return notaciones[notacion]


def big_endian(n: int) -> np.ndarray:
    return np.array(range(n), dtype=np.uint32)


def lil_endian(n: int) -> np.ndarray:
    if n <= 0:
        return np.array([0], dtype=np.uint32)

    size = 1 << n
    result = np.zeros(size, dtype=np.uint32)
    block_bits = max(12, min(16, 28 - int(np.log2(n))))
    block_size = 1 << block_bits
    shifts = np.array([n - i - 1 for i in range(n)], dtype=np.uint32)
    block_result = np.zeros(block_size, dtype=np.uint32)
    bit_group_size = 6 if n > 24 else 4

    for start in range(0, size, block_size):
        end = min(start + block_size, size)
        current_size = end - start
        block_result[:current_size] = 0
        block_indices = np.arange(start, end, dtype=np.uint32)

        for base_bit in range(0, n, bit_group_size):
            bits_remaining = min(bit_group_size, n - base_bit)
            if bits_remaining <= 0:
                break

            group_mask = np.uint32((1 << bits_remaining) - 1)
            group_values = (block_indices >> base_bit) & group_mask

            for j in range(bits_remaining):
                shift = shifts[base_bit + j]
                bit_value = (group_values >> j) & np.uint32(1)
                block_result[:current_size] |= bit_value << shift

        result[start:end] = block_result[:current_size]

    return result


def get_restricted_combinations(binary_str: str) -> tuple[list[str], list[str]]:
    ones_count = binary_str.count(STR_ONE)
    width = len(binary_str)
    one_positions = [i for i, bit in enumerate(binary_str) if bit == STR_ONE]

    def generate_valid_combinations() -> list[str]:
        base_combinations = list(product(["0", "1"], repeat=ones_count))
        valid_combinations = []

        for comb in base_combinations:
            result = ["0"] * width
            for pos, bit in zip(one_positions, comb):
                result[pos] = bit
            valid_combinations.append("".join(result))

        return valid_combinations

    combinaciones = generate_valid_combinations()
    return combinaciones, combinaciones.copy()


def generate_combinations(a_value: str) -> list[tuple[str, str, str]]:
    b_values, c_values = get_restricted_combinations(a_value)
    formatted_b = [
        EMPTY_STR.join(value[i : i + 2] for i in range(0, len(value), 2))
        for value in b_values
    ]
    formatted_c = [
        EMPTY_STR.join(value[i : i + 2] for i in range(0, len(value), 2))
        for value in c_values
    ]
    formatted_a = EMPTY_STR.join(a_value[i : i + 2] for i in range(0, len(a_value), 2))
    return list(product([formatted_a], formatted_b, formatted_c))[1:]


def dec2bin(decimal: int, width: int) -> str:
    return format(decimal, f"0{width}b")


def estados_binarios(n: int) -> list[str]:
    return [dec2bin(i, n) for i in range(1 << n)][1:]


def _active_emd_mode() -> object:
    try:
        from src.models.base.application import aplicacion
    except (ImportError, ModuleNotFoundError):
        return EMD_EFFECT
    return getattr(aplicacion, "tiempo_emd", getattr(aplicacion, "distancia_metrica", EMD_EFFECT))


def _active_distance_mode() -> object:
    try:
        from src.models.base.application import aplicacion
    except (ImportError, ModuleNotFoundError):
        return HAMMING
    return getattr(aplicacion, "distancia_metrica", HAMMING)
