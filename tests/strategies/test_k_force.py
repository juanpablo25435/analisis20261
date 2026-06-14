from contextlib import contextmanager
from pathlib import Path
import sys

import numpy as np

from shared_core.models.core.types import PartitionSpec


REPO_ROOT = Path(__file__).resolve().parents[2]
QNODES_ROOT = REPO_ROOT / "QNodes"


@contextmanager
def _project_src_import(project_root: Path):
    original_path = list(sys.path)
    original_src_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "src" or name.startswith("src.")
    }
    for name in list(original_src_modules):
        sys.modules.pop(name, None)
    sys.path.insert(0, str(project_root))
    try:
        yield
    finally:
        for name in [
            module_name
            for module_name in sys.modules
            if module_name == "src" or module_name.startswith("src.")
        ]:
            sys.modules.pop(name, None)
        sys.modules.update(original_src_modules)
        sys.path[:] = original_path


def _small_tpm() -> np.ndarray:
    return np.array(
        [
            [0.10, 0.20, 0.30],
            [0.20, 0.35, 0.45],
            [0.35, 0.45, 0.55],
            [0.45, 0.55, 0.65],
            [0.55, 0.65, 0.75],
            [0.65, 0.75, 0.85],
            [0.75, 0.85, 0.90],
            [0.85, 0.90, 0.95],
        ],
        dtype=np.float32,
    )


def _l1_distance(u: np.ndarray, v: np.ndarray) -> float:
    return float(np.sum(np.abs(u - v)))


def test_k_force_enumerates_k_partitions_and_returns_integrated_solution() -> None:
    with _project_src_import(QNODES_ROOT):
        from src.models.base.application import aplicacion
        from src.models.enums.temporal_emd import TimeEMD
        from src.strategies.k_force import KForceSIA

        aplicacion.set_tiempo_emd(TimeEMD.EMD_INTEGRADA)
        aplicacion.desactivar_profiling()

        strategy = KForceSIA(_small_tpm())
        strategy.distancia_metrica = _l1_distance

        specs = list(strategy._generar_specs((0, 1, 2), (0, 1, 2), k_max=2))
        assert len(specs) == 24
        assert all(isinstance(spec, PartitionSpec) for spec in specs)

        solution = strategy.aplicar_estrategia(
            estado_inicial="000",
            condiciones="111",
            alcance="111",
            mecanismo="111",
            k_max=2,
        )

        assert solution.estrategia == "K-BruteForce"
        assert np.isfinite(solution.perdida)
        assert solution.distribucion_subsistema.size == 6
        assert solution.distribucion_particion.size == 6
        assert solution.particion.strip()
