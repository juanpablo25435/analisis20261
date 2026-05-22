import sys
import time
from pathlib import Path


QNODE_ROOT = Path(__file__).resolve().parents[1]
if str(QNODE_ROOT) not in sys.path:
    sys.path.insert(0, str(QNODE_ROOT))

from src.controllers.manager import Manager
from src.models.base.application import aplicacion
from src.strategies.force import BruteForce
from src.strategies.k_force import KForceSIA


DEFAULT_STATE = "000"
DEFAULT_PAGE = "A"
DEFAULT_K_MAX = 3
FLOAT_TOLERANCE = 1e-8


def _print_resultado(nombre: str, perdida: float, particion: str, segundos: float) -> None:
    print(f"\n=== {nombre} ===")
    print(f"Phi: {perdida:.8f}")
    print(f"Tiempo total medido: {segundos:.4f}s")
    print("Partición:")
    print(particion)


def main() -> None:
    """Ejecuta una comparación rápida entre BruteForce y KForceSIA."""
    estado_inicial = DEFAULT_STATE
    condiciones = "1" * len(estado_inicial)
    alcance = "1" * len(estado_inicial)
    mecanismo = "1" * len(estado_inicial)

    aplicacion.set_pagina_red_muestra(DEFAULT_PAGE)
    aplicacion.desactivar_profiling()

    gestor_redes = Manager(estado_inicial)
    tpm = gestor_redes.cargar_red()

    print("Prueba KForceSIA")
    print(f"TPM: {gestor_redes.tpm_filename}")
    print(f"Estado inicial: {estado_inicial}")
    print(f"Condiciones: {condiciones}, alcance: {alcance}, mecanismo: {mecanismo}")

    brute_force = BruteForce(tpm)
    inicio_brute = time.perf_counter()
    solucion_brute = brute_force.aplicar_estrategia(
        estado_inicial,
        condiciones,
        alcance,
        mecanismo,
    )
    tiempo_brute = time.perf_counter() - inicio_brute

    k_force = KForceSIA(tpm)
    inicio_kforce = time.perf_counter()
    solucion_kforce = k_force.aplicar_estrategia(
        estado_inicial,
        condiciones,
        alcance,
        mecanismo,
        k_max=DEFAULT_K_MAX,
    )
    tiempo_kforce = time.perf_counter() - inicio_kforce

    _print_resultado(
        "BruteForce bipartito",
        solucion_brute.perdida,
        solucion_brute.particion,
        tiempo_brute,
    )
    _print_resultado(
        f"KForceSIA k_max={DEFAULT_K_MAX}",
        solucion_kforce.perdida,
        solucion_kforce.particion,
        tiempo_kforce,
    )

    if solucion_kforce.perdida <= solucion_brute.perdida + FLOAT_TOLERANCE:
        print("\nValidación OK: KForceSIA encontró Phi igual o menor que BruteForce.")
        return

    raise AssertionError(
        "Validación fallida: KForceSIA produjo una pérdida mayor que BruteForce "
        f"({solucion_kforce.perdida:.8f} > {solucion_brute.perdida:.8f})."
    )


if __name__ == "__main__":
    main()
