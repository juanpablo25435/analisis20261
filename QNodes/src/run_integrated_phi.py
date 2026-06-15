import sys
import time
from pathlib import Path

QNODE_ROOT = Path(__file__).resolve().parents[1]
if str(QNODE_ROOT) not in sys.path:
    sys.path.insert(0, str(QNODE_ROOT))

from src.controllers.manager import Manager
from src.models.base.application import aplicacion
from src.models.enums.temporal_emd import TimeEMD
from src.strategies.k_force import KForceSIA

DEFAULT_STATE = "000"
DEFAULT_PAGE = "A"
DEFAULT_K_MAX = 3


def main() -> None:
    """Ejecuta KForceSIA calculando Phi integrado causa-efecto."""
    estado_inicial = DEFAULT_STATE
    condiciones = "1" * len(estado_inicial)
    alcance = "1" * len(estado_inicial)
    mecanismo = "1" * len(estado_inicial)

    aplicacion.set_pagina_red_muestra(DEFAULT_PAGE)
    aplicacion.set_tiempo_emd(TimeEMD.EMD_INTEGRADA)
    aplicacion.desactivar_profiling()

    gestor_redes = Manager(estado_inicial)
    tpm = gestor_redes.cargar_red()

    print("Prueba Phi integrado con KForceSIA")
    print(f"TPM: {gestor_redes.tpm_filename}")
    print(f"Estado inicial: {estado_inicial}")
    print(f"Condiciones: {condiciones}, alcance: {alcance}, mecanismo: {mecanismo}")
    print(f"Tiempo EMD: {aplicacion.tiempo_emd}")

    inicio = time.perf_counter()
    solucion = KForceSIA(tpm).aplicar_estrategia(
        estado_inicial,
        condiciones,
        alcance,
        mecanismo,
        k_max=DEFAULT_K_MAX,
    )
    tiempo_total = time.perf_counter() - inicio

    print("\n=== KForceSIA Phi Integrado ===")
    print(f"Phi integrado: {solucion.perdida:.8f}")
    print(f"Tiempo total medido: {tiempo_total:.4f}s")
    print("Partición óptima:")
    print(solucion.particion)

    aplicacion.set_tiempo_emd(TimeEMD.EMD_EFECTO)


if __name__ == "__main__":
    main()
