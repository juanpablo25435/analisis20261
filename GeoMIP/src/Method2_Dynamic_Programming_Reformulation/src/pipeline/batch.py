from __future__ import annotations

import multiprocessing
import re
from dataclasses import dataclass
from multiprocessing.queues import Queue
from pathlib import Path

import numpy as np
import pandas as pd
from src.controllers.manager import Manager
from src.controllers.strategies.k_geometric import KGeometricSIA
from src.models.base.application import aplicacion

from shared_core.funcs.iit import emd_causal, emd_efecto
from shared_core.middlewares.slogger import SafeLogger
from shared_core.models.core.solution import Solution

METHOD2_ROOT = Path(__file__).resolve().parents[2]
GEOMIP_ROOT = Path(__file__).resolve().parents[4]
BATCH_LOGGER_TAG = "Geometric_batch_pipeline"
ResultadoBatch = dict[str, str | None]


@dataclass(frozen=True)
class BatchConfig:
    """Static parameters used to slice and evaluate Method2 Excel batches."""

    sheet_index: int = 8
    column: str = "B"
    skiprows: int = 3
    timeout_seconds: int = 3600
    default_k_max: int = 5
    start: int = 0
    count: int = 50
    estado_inicio: str | None = None

    @classmethod
    def from_mapping(cls, values: dict[str, object] | None) -> BatchConfig:
        """Build a config from YAML values while accepting Spanish legacy keys."""
        values = values or {}
        estado_inicio = values.get("estado_inicio")
        return cls(
            sheet_index=int(values.get("sheet_index", values.get("hoja", 8))),
            column=str(values.get("column", values.get("columna", "B"))),
            skiprows=int(values.get("skiprows", 3)),
            timeout_seconds=int(values.get("timeout_seconds", values.get("timeout", 3600))),
            default_k_max=int(values.get("DEFAULT_K_MAX", values.get("default_k_max", 5))),
            start=int(values.get("start", values.get("inicio", 0))),
            count=int(values.get("count", values.get("cantidad", 50))),
            estado_inicio=None if estado_inicio is None else str(estado_inicio),
        )


def ejecutar_desde_excel(
    ruta_excel: Path,
    ruta_salida: Path,
    config: BatchConfig,
    estado_inicio: str | None = None,
    condiciones: str | None = None,
) -> None:
    """Read subsystems from Excel, evaluate KGeometricSIA and write results.

    The function is the batch boundary for Method2. It logs the path involved
    before re-raising read/write errors so callers and shell runs fail loudly
    with enough context to diagnose missing files or malformed inputs.
    """
    logger = SafeLogger(BATCH_LOGGER_TAG)
    try:
        df = pd.read_excel(
            ruta_excel,
            sheet_name=config.sheet_index,
            usecols=config.column,
            skiprows=config.skiprows,
            names=["Subsistema"],
        )
    except FileNotFoundError as error:
        logger.error("No se encontró el Excel de entrada.", f"ruta={ruta_excel}", error)
        raise
    except (OSError, ValueError) as error:
        logger.error("No se pudo leer el Excel de entrada.", f"ruta={ruta_excel}", error)
        raise

    filas = df["Subsistema"].dropna().tolist()
    filas = filas[config.start : config.start + config.count]
    resultados = []

    estado_inicio = estado_inicio or inferir_estado_inicial()
    condiciones = condiciones or ("1" * len(estado_inicio))
    try:
        tpm_path = resolver_tpm_path(estado_inicio)
        tpm = np.genfromtxt(tpm_path, delimiter=",")
    except FileNotFoundError as error:
        logger.error("No se encontró la TPM requerida.", f"estado={estado_inicio}", error)
        raise
    except (OSError, ValueError) as error:
        logger.error("No se pudo leer la TPM requerida.", f"estado={estado_inicio}", error)
        raise

    for row_index, fila in enumerate(filas, start=config.start + 1):
        partes = str(fila).split("|")
        if len(partes) != 2:
            logger.error("Fila de subsistema inválida; se omite.", f"iteracion={row_index}", fila)
            continue

        alcance = convertir_a_binario(partes[0][: len(partes[0]) - 3], n_bits=len(estado_inicio))
        mecanismo = convertir_a_binario(partes[1][: len(partes[1]) - 1], n_bits=len(estado_inicio))
        config_sistema = Manager(estado_inicial=estado_inicio)

        resultado = _ejecutar_iteracion_con_timeout(
            config_sistema=config_sistema,
            condiciones=condiciones,
            alcance=alcance,
            mecanismo=mecanismo,
            tpm=tpm,
            subsistema_id=row_index,
            timeout_seconds=config.timeout_seconds,
            k_max=config.default_k_max,
            logger=logger,
        )
        resultados.append(
            {
                "Iteración": row_index,
                "Alcance": alcance,
                "Mecanismo": mecanismo,
                "Partición": resultado["particion"],
                "Phi_Efecto": resultado["phi_efecto"],
                "Phi_Causa": resultado["phi_causa"],
                "Phi_Integrado": resultado["phi_integrado"],
                "Tiempo de ejecución (s)": resultado["tiempo"],
            }
        )

    df_resultados = pd.DataFrame(resultados)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    try:
        df_resultados.to_excel(ruta_salida, index=False)
    except (OSError, ValueError) as error:
        logger.error("No se pudo escribir el Excel de resultados.", f"ruta={ruta_salida}", error)
        raise


def ejecutar_con_tiempo(
    config_sistema: Manager,
    condiciones: str,
    alcance: str,
    mecanismo: str,
    resultado_queue: Queue,
    tpm: np.ndarray,
    k_max: int,
    subsistema_id: int | None = None,
) -> None:
    """Run one subsystem evaluation and put a serializable result in a queue."""
    logger = SafeLogger(BATCH_LOGGER_TAG)
    contexto = (
        f"subsistema={subsistema_id} "
        f"estado={config_sistema.estado_inicial} "
        f"condiciones={condiciones} alcance={alcance} mecanismo={mecanismo}"
    )
    try:
        aplicacion.set_distancia_integrada()
        analizador_fi = KGeometricSIA(config_sistema)
        solucion = analizador_fi.aplicar_estrategia(
            condiciones,
            alcance,
            mecanismo,
            tpm=tpm,
            k_max=k_max,
        )
        phi_efecto, phi_causa, phi_integrado = _separar_phi_integrado(solucion)
        resultado_queue.put(
            {
                "particion": solucion.particion,
                "phi_efecto": _formatear_float(phi_efecto),
                "phi_causa": _formatear_float(phi_causa),
                "phi_integrado": _formatear_float(phi_integrado),
                "tiempo": _formatear_float(solucion.tiempo_ejecucion),
            }
        )
    except ValueError as error:
        logger.error("Error de validación dimensional/tipado en evaluación IIT.", contexto, error)
        resultado_queue.put(_resultado_nulo())


def convertir_a_binario(texto: str, n_bits: int = 20) -> str:
    """Convert subsystem node labels such as 'ABC' into a fixed-width bitmask."""
    posiciones = "ABCDEFGHIJKLMNOPQRST"[:n_bits]
    binario = ["0"] * n_bits
    for letra in texto:
        if letra in posiciones:
            binario[posiciones.index(letra)] = "1"
    return "".join(binario)


def resolver_tpm_path(estado_inicio: str) -> Path:
    """Resolve the TPM sample file matching the length of the initial state."""
    sample_name = f"N{len(estado_inicio)}A.csv"
    candidates = (
        METHOD2_ROOT / "src" / ".samples" / sample_name,
        METHOD2_ROOT / ".samples" / sample_name,
        GEOMIP_ROOT / "data" / "samples" / sample_name,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"No se encontró la TPM '{sample_name}'. Busqué en: "
        f"{', '.join(str(candidate) for candidate in candidates)}"
    )


def inferir_estado_inicial() -> str:
    """Infer the largest available sample size and return its default state."""
    sample_dirs = (
        METHOD2_ROOT / "src" / ".samples",
        METHOD2_ROOT / ".samples",
        GEOMIP_ROOT / "data" / "samples",
    )
    pattern = re.compile(r"N(\d+)[A-Z]\.csv$")
    available_sizes = []

    for sample_dir in sample_dirs:
        if not sample_dir.exists():
            continue
        for sample_file in sample_dir.glob("N*.csv"):
            match = pattern.match(sample_file.name)
            if match:
                available_sizes.append(int(match.group(1)))

    if not available_sizes:
        raise FileNotFoundError("No hay archivos de muestras TPM disponibles en data/samples ni .samples.")

    n_bits = max(available_sizes)
    return "1" + ("0" * (n_bits - 1))


def _ejecutar_iteracion_con_timeout(
    config_sistema: Manager,
    condiciones: str,
    alcance: str,
    mecanismo: str,
    tpm: np.ndarray,
    subsistema_id: int,
    timeout_seconds: int,
    k_max: int,
    logger: SafeLogger,
) -> ResultadoBatch:
    resultado_queue = multiprocessing.Queue()
    proceso = multiprocessing.Process(
        target=ejecutar_con_tiempo,
        args=(
            config_sistema,
            condiciones,
            alcance,
            mecanismo,
            resultado_queue,
            tpm,
            k_max,
            subsistema_id,
        ),
    )

    proceso.start()
    proceso.join(timeout=timeout_seconds)

    if proceso.is_alive():
        logger.error("Tiempo límite alcanzado; terminando proceso.", f"iteracion={subsistema_id}")
        proceso.terminate()
        proceso.join()
        return _resultado_nulo()

    if proceso.exitcode not in (0, None):
        logger.error(
            "Proceso de evaluación terminó con error.",
            f"iteracion={subsistema_id}",
            f"exitcode={proceso.exitcode}",
        )
        return _resultado_nulo()

    if resultado_queue.empty():
        logger.error("Proceso de evaluación no devolvió resultado.", f"iteracion={subsistema_id}")
        return _resultado_nulo()

    return resultado_queue.get()


def _resultado_nulo() -> ResultadoBatch:
    return {
        "particion": None,
        "phi_efecto": None,
        "phi_causa": None,
        "phi_integrado": None,
        "tiempo": None,
    }


def _formatear_float(valor: float | None) -> str | None:
    return None if valor is None else str(valor).replace(".", ",")


def _separar_phi_integrado(solucion: Solution) -> tuple[float, float, float]:
    """Split a concatenated integrated solution into effect, cause and total Phi."""
    distribucion_subsistema = solucion.distribucion_subsistema
    distribucion_particion = solucion.distribucion_particion
    if (
        distribucion_subsistema.size != distribucion_particion.size
        or distribucion_subsistema.size % 2 != 0
    ):
        raise ValueError("La solución integrada no contiene distribuciones concatenadas pares.")

    mitad = distribucion_subsistema.size // 2
    phi_efecto = emd_efecto(
        distribucion_particion[:mitad],
        distribucion_subsistema[:mitad],
    )
    phi_causa = emd_causal(
        distribucion_particion[mitad:],
        distribucion_subsistema[mitad:],
    )
    return phi_efecto, phi_causa, phi_efecto + phi_causa
