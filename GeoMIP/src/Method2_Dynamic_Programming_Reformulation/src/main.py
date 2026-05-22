# from src.controllers.manager import Manager

# from src.controllers.strategies.force import BruteForce
# from src.controllers.strategies.q_nodes import QNodes
# from src.controllers.strategies.geometric import GeometricSIA


# def iniciar():
#     """Punto de entrada principal"""
#                     # ABCD #
#     # estado_inicial = "100"
#     # condiciones =    "111"
#     # alcance =        "111"
#     # mecanismo =      "111"
#     # estado_inicial = "0000"
#     # condiciones =    "1111"
#     # alcance =        "1111"
#     # mecanismo =      "1111"
#     # estado_inicial = "1000"
#     # condiciones =    "1111"
#     # alcance =        "0111"
#     # mecanismo =      "1111"
#     # estado_inicial = "100000"
#     # condiciones =    "111111"
#     # alcance =        "101011"
#     # mecanismo =      "111111"
#     # estado_inicial = "100000"
#     # condiciones =    "111111"
#     # alcance =        "111111"
#     # mecanismo =      "111111"
#     # estado_inicial = "100000"
#     # condiciones =    "111111"
#     # alcance =        "111111"
#     # mecanismo =      "011111"
#     # estado_inicial = "1000000000"
#     # condiciones =    "1111111111"
#     # alcance =        "1111111111"
#     # mecanismo =      "1111111111"
#     estado_inicial = "1000000000"
#     condiciones =    "1111111111"
#     alcance =        "0101010101"
#     mecanismo =      "1111111111"
#     # estado_inicial = "1000000000"
#     # condiciones =    "1111111111"
#     # alcance =        "1111111110"
#     # mecanismo =      "1111111111"
#     # estado_inicial = "10000000000000000000"
#     # condiciones =    "11111111111111111111"
#     # alcance =        "11111111111111111111"
#     # mecanismo =      "11111111111111111111"
#     # estado_inicial = "10000000000000000000"
#     # condiciones =    "11111111111111111111"
#     # alcance =        "11011011011011011011"
#     # mecanismo =      "10101010101010101010"

#     gestor_sistema = Manager(estado_inicial)

#     ### Ejemplo de solución mediante módulo de fuerza bruta ###
#     analizador_fb = GeometricSIA(gestor_sistema)
#     # analizador_fb = BruteForce(gestor_sistema)
#     sia_uno = analizador_fb.aplicar_estrategia(
#         condiciones,
#         alcance,
#         mecanismo,
#     )
#     print(sia_uno)
from src.controllers.manager import Manager
from src.controllers.strategies.geometric import GeometricSIA
from src.controllers.strategies.k_geometric import KGeometricSIA
from src.controllers.strategies.q_nodes import QNodes
from src.funcs.base import emd_causal, emd_efecto
from src.models.base.application import aplicacion
from src.middlewares.slogger import SafeLogger
# Optional import: this project often runs only geometric strategy.
try:
    from src.controllers.strategies.phi import Phi
except Exception:
    Phi = None
import multiprocessing
import numpy as np
import pandas as pd
import os
import re
from pathlib import Path


METHOD2_ROOT = Path(__file__).resolve().parents[1]
GEOMIP_ROOT = Path(__file__).resolve().parents[3]
BATCH_LOGGER_TAG = "Geometric_batch_pipeline"
DEFAULT_K_MAX = 5

def convertir_a_binario(texto, n_bits=20):
    posiciones = "ABCDEFGHIJKLMNOPQRST"[:n_bits]
    binario = ["0"] * n_bits
    for letra in texto:
        if letra in posiciones:
            binario[posiciones.index(letra)] = "1"
    return "".join(binario)


def _resultado_nulo():
    return {
        "particion": None,
        "phi_efecto": None,
        "phi_causa": None,
        "phi_integrado": None,
        "tiempo": None,
    }


def _formatear_float(valor: float | None) -> str | None:
    return None if valor is None else str(valor).replace(".", ",")


def _separar_phi_integrado(solucion) -> tuple[float, float, float]:
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

def ejecutar_con_tiempo(
    config_sistema,
    condiciones,
    alcance,
    mecanismo,
    resultado_queue,
    tpm,
    subsistema_id=None,
):
    logger = SafeLogger(BATCH_LOGGER_TAG)
    contexto = (
        f"subsistema={subsistema_id} "
        f"estado={config_sistema.estado_inicial} "
        f"condiciones={condiciones} alcance={alcance} mecanismo={mecanismo}"
    )
    try:
        aplicacion.set_distancia_integrada()
        analizador_fi = KGeometricSIA(config_sistema)
        sia_dos = analizador_fi.aplicar_estrategia(
            condiciones,
            alcance,
            mecanismo,
            tpm=tpm,
            k_max=DEFAULT_K_MAX,
        )
        phi_efecto, phi_causa, phi_integrado = _separar_phi_integrado(sia_dos)
        resultado_queue.put({
            "particion": sia_dos.particion,
            "phi_efecto": _formatear_float(phi_efecto),
            "phi_causa": _formatear_float(phi_causa),
            "phi_integrado": _formatear_float(phi_integrado),
            "tiempo": _formatear_float(sia_dos.tiempo_ejecucion),
        })

    except ValueError as error:
        logger.error("Error de validación dimensional/tipado en evaluación IIT.", contexto, error)
        resultado_queue.put(_resultado_nulo())
    except Exception as error:
        logger.critic("Fallo estructural crítico en evaluación IIT.", contexto, error)
        resultado_queue.put(_resultado_nulo())

def resolver_tpm_path(estado_inicio: str) -> Path:
    """Find TPM file in common project locations based on state size."""
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
        f"No se encontró la TPM '{sample_name}'. Busqué en: {', '.join(str(c) for c in candidates)}"
    )


def inferir_estado_inicial() -> str:
    """Infer an initial state from available datasets (prefers largest NxA.csv)."""
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


def ejecutar_desde_excel(
    ruta_excel: Path,
    ruta_salida: Path,
    inicio=0,
    cantidad=50,
    estado_inicio: str | None = None,
    condiciones: str | None = None,
):
    df = pd.read_excel(ruta_excel, sheet_name=8, usecols="B", skiprows=3, names=["Subsistema"]) #! here
    filas = df["Subsistema"].dropna().tolist()
    filas = filas[inicio:inicio + cantidad]
    resultados = []

    estado_inicio = estado_inicio or inferir_estado_inicial()
    condiciones = condiciones or ("1" * len(estado_inicio))
    tpm_path = resolver_tpm_path(estado_inicio)
    tpm = np.genfromtxt(tpm_path, delimiter=",")

    for i, fila in enumerate(filas, start=inicio + 1):
        partes = fila.split("|")
        if len(partes) != 2:
            continue

        alcance = convertir_a_binario(partes[0][:len(partes[0]) - 3], n_bits=len(estado_inicio))
        mecanismo = convertir_a_binario(partes[1][:len(partes[1]) - 1], n_bits=len(estado_inicio))
        print(f"Iteración {i} - Alcance: {alcance}, Mecanismo: {mecanismo}")

        config_sistema = Manager(estado_inicial=estado_inicio)

        resultado_queue = multiprocessing.Queue()
        proceso = multiprocessing.Process(
            target=ejecutar_con_tiempo,
            args=(config_sistema, condiciones, alcance, mecanismo, resultado_queue, tpm, i),
        )
        
        proceso.start()
        proceso.join(timeout=3600)  

        if proceso.is_alive():
            print(f"Iteración {i} - Tiempo límite alcanzado, terminando proceso...")
            proceso.terminate()
            proceso.join()
            resultado = _resultado_nulo()
        else:
            resultado = (
                resultado_queue.get()
                if not resultado_queue.empty()
                else _resultado_nulo()
            )

        resultados.append({
            "Iteración": i,
            "Alcance": alcance,
            "Mecanismo": mecanismo,
            "Partición": resultado["particion"],
            "Phi_Efecto": resultado["phi_efecto"],
            "Phi_Causa": resultado["phi_causa"],
            "Phi_Integrado": resultado["phi_integrado"],
            "Tiempo de ejecución (s)": resultado["tiempo"],
        })
    df_resultados = pd.DataFrame(resultados)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    df_resultados.to_excel(ruta_salida, index=False)
    print(f"Resultados guardados en {ruta_salida}")

def iniciar():
    ruta_entrada = Path(
        os.getenv(
            "GEOMIP_INPUT_XLSX",
            str(GEOMIP_ROOT / "results" / "Pruebas_Metodo2.xlsx"),
        )
    )
    ruta_salida = Path(
        os.getenv(
            "GEOMIP_OUTPUT_XLSX",
            str(GEOMIP_ROOT / "results" / "resultados_Geometric.xlsx"),
        )
    )
    ejecutar_desde_excel(ruta_entrada, ruta_salida)