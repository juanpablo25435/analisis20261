from collections.abc import Iterable, Iterator
from itertools import product
import time
from typing import Callable

import numpy as np
from numpy.typing import NDArray

from src.constants.base import BASE_TWO, COLON_DELIM, NET_LABEL, VOID_STR
from src.constants.models import (
    DUMMY_ARR,
    DUMMY_EMD,
    ERROR_PARTITION,
    KFORCE_LABEL,
    KFORCE_STRAREGY_TAG,
)
from src.controllers.manager import Manager
from src.funcs.base import ABECEDARY, LOWER_ABECEDARY, seleccionar_metrica
from src.middlewares.profile import profiler_manager
from src.middlewares.slogger import SafeLogger
from src.models.base.application import aplicacion
from src.models.base.sia import SIA
from src.models.core.solution import Solution
from src.models.core.types import PartitionSpec


Bloques = tuple[tuple[int, ...], ...]


class KForceSIA(SIA):
    """
    Fuerza bruta exhaustiva para particiones k-vías en Method2.
    """

    def __init__(self, gestor: Manager):
        super().__init__(gestor)
        profiler_manager.start_session(
            f"{NET_LABEL}{len(gestor.estado_inicial)}{gestor.pagina}"
        )
        self.distancia_metrica: Callable[
            [NDArray[np.float32], NDArray[np.float32]], float
        ] = seleccionar_metrica(aplicacion.distancia_metrica)
        self.logger = SafeLogger(KFORCE_STRAREGY_TAG)

    def aplicar_estrategia(
        self,
        condiciones: str,
        alcance: str,
        mecanismo: str,
        tpm: np.ndarray | None = None,
        k_max: int | None = None,
    ) -> Solution:
        self.sia_preparar_subsistema(
            condiciones,
            alcance,
            mecanismo,
            tpm if tpm is not None else self.sia_cargar_tpm(),
        )

        futuros = tuple(int(indice) for indice in self.sia_subsistema.indices_ncubos)
        presentes = tuple(int(dim) for dim in self.sia_subsistema.dims_ncubos)
        max_bloques = min(len(futuros), len(presentes))
        if k_max is not None:
            max_bloques = min(max_bloques, k_max)

        if max_bloques < BASE_TWO:
            return Solution(
                KFORCE_LABEL,
                DUMMY_EMD,
                self.sia_dists_marginales,
                np.array(DUMMY_ARR, dtype=np.float32),
                ERROR_PARTITION,
                tiempo_total=time.time() - self.sia_tiempo_inicio,
                hablar=False,
            )

        small_phi = np.inf
        mejor_dist_marg: NDArray[np.float32] = np.array(DUMMY_ARR, dtype=np.float32)
        mejor_spec: PartitionSpec | None = None

        for spec in self._generar_specs(futuros, presentes, max_bloques):
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
            KFORCE_LABEL,
            float(small_phi),
            self.sia_dists_marginales,
            mejor_dist_marg,
            particion_fmt,
            tiempo_total=time.time() - self.sia_tiempo_inicio,
            hablar=False,
        )

    def _generar_specs(
        self,
        futuros: tuple[int, ...],
        presentes: tuple[int, ...],
        k_max: int,
    ) -> Iterator[PartitionSpec]:
        for k in range(BASE_TWO, k_max + 1):
            for bloques_futuro in self._particiones_k(futuros, k):
                for bloques_presente in self._asignaciones_k(presentes, k):
                    yield PartitionSpec(
                        bloques=bloques_futuro,
                        mecanismos=bloques_presente,
                    )

    def _asignaciones_k(self, elementos: tuple[int, ...], k: int) -> Iterator[Bloques]:
        for etiquetas in product(range(k), repeat=len(elementos)):
            bloques = tuple(
                tuple(
                    elemento
                    for elemento, etiqueta in zip(elementos, etiquetas)
                    if etiqueta == bloque_idx
                )
                for bloque_idx in range(k)
            )
            yield bloques

    def _particiones_k(self, elementos: tuple[int, ...], k: int) -> Iterator[Bloques]:
        if k < 1 or k > len(elementos):
            return

        bloques: list[list[int]] = [[] for _ in range(k)]
        yield from self._particionar_recursivo(elementos, k, 0, 0, bloques)

    def _particionar_recursivo(
        self,
        elementos: tuple[int, ...],
        k: int,
        indice: int,
        bloques_usados: int,
        bloques: list[list[int]],
    ) -> Iterator[Bloques]:
        if indice == len(elementos):
            if bloques_usados == k:
                yield tuple(tuple(bloque) for bloque in bloques)
            return

        restantes = len(elementos) - indice
        if bloques_usados + restantes < k:
            return

        elemento = elementos[indice]
        for bloque_idx in range(bloques_usados):
            bloques[bloque_idx].append(elemento)
            yield from self._particionar_recursivo(
                elementos,
                k,
                indice + 1,
                bloques_usados,
                bloques,
            )
            bloques[bloque_idx].pop()

        if bloques_usados < k:
            bloques[bloques_usados].append(elemento)
            yield from self._particionar_recursivo(
                elementos,
                k,
                indice + 1,
                bloques_usados + 1,
                bloques,
            )
            bloques[bloques_usados].pop()

    def _formatear_particion(self, spec: PartitionSpec) -> str:
        partes = [
            self._formatear_bloque(mecanismo, alcance)
            for alcance, mecanismo in zip(spec.bloques, spec.mecanismos)
        ]
        tops, bottoms = zip(*partes)
        return f"{''.join(tops)}\n{''.join(bottoms)}\n"

    def _formatear_bloque(
        self,
        mecanismo: Iterable[int],
        alcance: Iterable[int],
    ) -> tuple[str, str]:
        purview = self._literales(alcance, ABECEDARY)
        mechanism = self._literales(mecanismo, LOWER_ABECEDARY)
        width = max(len(purview), len(mechanism)) + BASE_TWO
        return f"⎛{purview:^{width}}⎞", f"⎝{mechanism:^{width}}⎠"

    def _literales(self, indices: Iterable[int], labels: Iterable[str]) -> str:
        label_tuple = tuple(labels)
        valores = tuple(label_tuple[int(indice)] for indice in indices)
        return COLON_DELIM.join(valores) if valores else VOID_STR
