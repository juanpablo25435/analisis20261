import time
from collections.abc import Callable, Iterable

import numpy as np
from numpy.typing import NDArray
from src.constants.base import BASE_TWO, COLON_DELIM, NET_LABEL, VOID_STR
from src.constants.models import (
    DUMMY_ARR,
    DUMMY_EMD,
    ERROR_PARTITION,
    KGEOMETRIC_LABEL,
    KGEOMETRIC_STRAREGY_TAG,
)
from src.controllers.manager import Manager
from src.middlewares.profile import profiler_manager
from src.models.base.application import aplicacion
from src.models.base.sia import SIA
from src.models.enums.distance import MetricDistance

from shared_core.funcs.iit import ABECEDARY, LOWER_ABECEDARY, seleccionar_metrica
from shared_core.middlewares.slogger import SafeLogger
from shared_core.models.core.ncube import NCube
from shared_core.models.core.solution import Solution
from shared_core.models.core.types import PartitionSpec


class KGeometricSIA(SIA):
    """
    Heurística topológica KGeoMIP basada en clustering aglomerativo.

    Los nodos se representan por firmas binarias derivadas de sus vectores de
    probabilidad forward/backward. La distancia entre firmas es Hamming
    normalizada y los clusters se fusionan con enlace promedio.
    """

    def __init__(self, gestor: Manager):
        super().__init__(gestor)
        profiler_manager.start_session(
            f"{NET_LABEL}{len(gestor.estado_inicial)}{gestor.pagina}"
        )
        self.distancia_metrica: Callable[
            [NDArray[np.float32], NDArray[np.float32]], float
        ] = seleccionar_metrica(MetricDistance.EMD_INTEGRADA)
        self.logger = SafeLogger(KGEOMETRIC_STRAREGY_TAG)

    def aplicar_estrategia(
        self,
        condiciones: str,
        alcance: str,
        mecanismo: str,
        tpm: np.ndarray | None = None,
        k_max: int | None = None,
    ) -> Solution:
        """Evaluate KGeoMIP on a subsystem and return the best k-way partition.

        Args:
            condiciones: Binary mask of conditioned present nodes.
            alcance: Binary mask of future nodes included in the purview.
            mecanismo: Binary mask of present nodes included in the mechanism.
            tpm: Optional TPM override. If omitted, the manager loads its configured TPM.
            k_max: Optional upper bound for the number of agglomerative clusters.

        Returns:
            A `Solution` containing integrated Phi, subsystem distribution,
            partition distribution and a formatted partition string.
        """
        aplicacion.set_distancia_integrada()
        self.sia_preparar_subsistema(
            condiciones,
            alcance,
            mecanismo,
            tpm if tpm is not None else self.sia_cargar_tpm(),
        )

        nodos, perfiles = self._extraer_perfiles_nodos()
        max_bloques = len(nodos) if k_max is None else min(k_max, len(nodos))
        if max_bloques < BASE_TWO:
            return Solution(
                KGEOMETRIC_LABEL,
                DUMMY_EMD,
                self.sia_dists_marginales,
                np.array(DUMMY_ARR, dtype=np.float32),
                ERROR_PARTITION,
                tiempo_total=time.time() - self.sia_tiempo_inicio,
                hablar=False,
            )

        matriz_distancias = self._matriz_hamming(perfiles)
        futuros = set(int(indice) for indice in self.sia_subsistema.indices_ncubos)
        presentes = set(int(dim) for dim in self.sia_subsistema.dims_ncubos)

        small_phi = np.inf
        mejor_dist_marg: NDArray[np.float32] = np.array(DUMMY_ARR, dtype=np.float32)
        mejor_spec: PartitionSpec | None = None

        for k in range(BASE_TWO, max_bloques + 1):
            clusters = self._clusterizar_aglomerativo(matriz_distancias, k)
            spec = self._spec_desde_clusters(clusters, nodos, futuros, presentes)
            particion = self.sia_subsistema.aplicar_particion(spec)
            dist_marginal = particion.distribucion_marginal()
            emd_value = self.distancia_metrica(dist_marginal, self.sia_dists_marginales)

            if emd_value < small_phi:
                small_phi = emd_value
                mejor_dist_marg = dist_marginal
                mejor_spec = spec

        particion_fmt = (
            self._formatear_particion(mejor_spec)
            if mejor_spec is not None
            else ERROR_PARTITION
        )
        return Solution(
            KGEOMETRIC_LABEL,
            float(small_phi),
            self.sia_dists_marginales,
            mejor_dist_marg,
            particion_fmt,
            tiempo_total=time.time() - self.sia_tiempo_inicio,
            hablar=False,
        )

    def _extraer_perfiles_nodos(self) -> tuple[tuple[int, ...], NDArray[np.float32]]:
        futuros = tuple(int(indice) for indice in self.sia_subsistema.indices_ncubos)
        presentes = tuple(int(dim) for dim in self.sia_subsistema.dims_ncubos)
        nodos = tuple(sorted(set(futuros) | set(presentes)))
        perfiles = [
            self._perfil_nodo(nodo, self.sia_subsistema.ncubos)
            for nodo in nodos
        ]

        ncubos_causales = getattr(self.sia_subsistema, "_ncubos_causales", None)
        if ncubos_causales is not None:
            perfiles = [
                np.concatenate([perfil, self._perfil_nodo(nodo, ncubos_causales)])
                for nodo, perfil in zip(nodos, perfiles)
            ]

        return nodos, np.vstack(perfiles).astype(np.float32)

    def _perfil_nodo(
        self,
        nodo: int,
        ncubos: tuple[NCube, ...],
    ) -> NDArray[np.float32]:
        cube_by_index = {int(cubo.indice): cubo for cubo in ncubos}
        max_profile_size = max(cubo.data.size for cubo in ncubos)
        salida = np.zeros(max_profile_size, dtype=np.float32)
        if nodo in cube_by_index:
            data = cube_by_index[nodo].data.ravel().astype(np.float32)
            salida[: data.size] = data

        influencia = []
        for cubo in ncubos:
            influencia.extend(self._firma_dimension(nodo, cubo))
        return np.concatenate([salida, np.array(influencia, dtype=np.float32)])

    def _firma_dimension(self, nodo: int, cubo: NCube) -> tuple[float, float, float]:
        if nodo not in set(int(dim) for dim in cubo.dims):
            return 0.0, 0.0, 0.0

        axis = cubo.dims.size - 1 - int(np.where(cubo.dims == nodo)[0][0])
        off = np.take(cubo.data, indices=0, axis=axis)
        on = np.take(cubo.data, indices=1, axis=axis)
        mean_off = float(np.mean(off))
        mean_on = float(np.mean(on))
        return mean_off, mean_on, abs(mean_on - mean_off)

    def _matriz_hamming(self, perfiles: NDArray[np.float32]) -> NDArray[np.float32]:
        binarios = perfiles >= 0.5
        diferencias = np.logical_xor(binarios[:, None, :], binarios[None, :, :])
        return np.mean(diferencias, axis=2, dtype=np.float32)

    def _clusterizar_aglomerativo(
        self,
        matriz_distancias: NDArray[np.float32],
        k: int,
    ) -> tuple[tuple[int, ...], ...]:
        clusters = [tuple([idx]) for idx in range(matriz_distancias.shape[0])]
        while len(clusters) > k:
            mejor_par = (0, 1)
            mejor_distancia = np.inf
            for i in range(len(clusters)):
                for j in range(i + 1, len(clusters)):
                    distancia = self._distancia_promedio(
                        clusters[i],
                        clusters[j],
                        matriz_distancias,
                    )
                    if distancia < mejor_distancia:
                        mejor_distancia = distancia
                        mejor_par = (i, j)

            i, j = mejor_par
            fusion = tuple(sorted(clusters[i] + clusters[j]))
            clusters = [
                cluster
                for idx, cluster in enumerate(clusters)
                if idx not in {i, j}
            ]
            clusters.append(fusion)
            clusters.sort(key=lambda cluster: cluster[0])
        return tuple(clusters)

    def _distancia_promedio(
        self,
        cluster_a: tuple[int, ...],
        cluster_b: tuple[int, ...],
        matriz_distancias: NDArray[np.float32],
    ) -> float:
        return float(
            np.mean(
                matriz_distancias[
                    np.ix_(np.array(cluster_a, dtype=int), np.array(cluster_b, dtype=int))
                ]
            )
        )

    def _spec_desde_clusters(
        self,
        clusters: tuple[tuple[int, ...], ...],
        nodos: tuple[int, ...],
        futuros: set[int],
        presentes: set[int],
    ) -> PartitionSpec:
        bloques = tuple(
            tuple(nodos[idx] for idx in cluster if nodos[idx] in futuros)
            for cluster in clusters
        )
        mecanismos = tuple(
            tuple(nodos[idx] for idx in cluster if nodos[idx] in presentes)
            for cluster in clusters
        )
        return PartitionSpec(bloques=bloques, mecanismos=mecanismos)

    def _formatear_particion(self, spec: PartitionSpec) -> str:
        bloques_alcance = " / ".join(
            self._formatear_bloque(alcance, ABECEDARY)
            for alcance in spec.bloques
        )
        bloques_mecanismo = " / ".join(
            self._formatear_bloque(mecanismo, LOWER_ABECEDARY)
            for mecanismo in spec.mecanismos
        )
        return f"Alcance={bloques_alcance}; Mecanismo={bloques_mecanismo}"

    def _formatear_bloque(
        self,
        indices: Iterable[int],
        labels: Iterable[str],
    ) -> str:
        return f"({self._literales(indices, labels)})"

    def _literales(self, indices: Iterable[int], labels: Iterable[str]) -> str:
        label_tuple = tuple(labels)
        valores = tuple(label_tuple[int(indice)] for indice in indices)
        return COLON_DELIM.join(valores) if valores else VOID_STR
