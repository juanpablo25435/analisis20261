from contextlib import contextmanager
from pathlib import Path
import sys

import numpy as np

from shared_core.models.core.types import PartitionSpec


REPO_ROOT = Path(__file__).resolve().parents[2]
METHOD2_ROOT = REPO_ROOT / "GeoMIP" / "src" / "Method2_Dynamic_Programming_Reformulation"


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


def test_k_geometric_builds_valid_partition_spec_from_agglomerative_clustering() -> None:
    with _project_src_import(METHOD2_ROOT):
        from src.controllers.manager import Manager
        from src.controllers.strategies.k_geometric import KGeometricSIA
        from src.models.base.application import aplicacion

        aplicacion.profiler_habilitado = False
        strategy = KGeometricSIA(Manager(estado_inicial="000"))
        strategy.distancia_metrica = _l1_distance

        solution = strategy.aplicar_estrategia(
            condiciones="111",
            alcance="111",
            mecanismo="111",
            tpm=_small_tpm(),
            k_max=2,
        )

        nodos, perfiles = strategy._extraer_perfiles_nodos()
        matriz_distancias = strategy._matriz_hamming(perfiles)
        clusters = strategy._clusterizar_aglomerativo(matriz_distancias, k=2)
        spec = strategy._spec_desde_clusters(
            clusters,
            nodos,
            set(int(indice) for indice in strategy.sia_subsistema.indices_ncubos),
            set(int(dim) for dim in strategy.sia_subsistema.dims_ncubos),
        )

        assert isinstance(spec, PartitionSpec)
        assert len(spec.bloques) == 2
        assert len(spec.mecanismos) == 2
        assert sorted(nodo for bloque in spec.bloques for nodo in bloque) == [0, 1, 2]
        assert sorted(nodo for bloque in spec.mecanismos for nodo in bloque) == [0, 1, 2]
        assert perfiles.shape[0] == 3
        assert matriz_distancias.shape == (3, 3)
        assert np.isfinite(solution.perdida)
        assert solution.distribucion_subsistema.size == 6
        assert solution.distribucion_particion.size == 6
