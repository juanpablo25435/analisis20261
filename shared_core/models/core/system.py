import numpy as np
from numpy.typing import NDArray

from shared_core.funcs.iit import (
    EMD_CAUSE,
    EMD_EFFECT,
    EMD_INTEGRATED,
    LITTLE_ENDIAN,
    enum_value,
    generar_tpm_causal,
    reindexar,
    seleccionar_estado,
)
from shared_core.models.core.ncube import NCube
from shared_core.models.core.types import PartitionSpec


class System:
    """Core system representation for conditioning, subtraction and partitions."""

    def __init__(
        self,
        tpm: np.ndarray,
        estado_inicio: np.ndarray,
        *,
        notacion_llegada: object | None = None,
        notacion_indexado: object | None = None,
        tiempo_emd: object | None = None,
        distribucion_complementaria: bool | None = None,
    ):
        defaults = _default_system_config()
        num_nodos = self.validacion_inicial(tpm, estado_inicio)
        self.estado_inicial = estado_inicio
        self.notacion_llegada = enum_value(notacion_llegada or defaults["notacion_llegada"])
        self.notacion_indexado = enum_value(notacion_indexado or defaults["notacion_indexado"])
        self.tiempo_emd = enum_value(tiempo_emd or defaults["tiempo_emd"])
        self.distribucion_complementaria = (
            defaults["distribucion_complementaria"]
            if distribucion_complementaria is None
            else distribucion_complementaria
        )

        if self.tiempo_emd == EMD_CAUSE:
            self.ncubos = self._crear_ncubos(
                generar_tpm_causal(tpm),
                num_nodos,
                self.notacion_llegada,
                self.notacion_indexado,
            )
            self._ncubos_causales: tuple[NCube, ...] | None = None
        elif self.tiempo_emd == EMD_INTEGRATED:
            self.ncubos = self._crear_ncubos(
                tpm,
                num_nodos,
                self.notacion_llegada,
                self.notacion_indexado,
            )
            self._ncubos_causales = self._crear_ncubos(
                generar_tpm_causal(tpm),
                num_nodos,
                self.notacion_llegada,
                self.notacion_indexado,
            )
        else:
            self.ncubos = self._crear_ncubos(
                tpm,
                num_nodos,
                self.notacion_llegada,
                self.notacion_indexado,
            )
            self._ncubos_causales = None

        self.memo = {}

    @staticmethod
    def _crear_ncubos(
        tpm: np.ndarray,
        num_nodos: int,
        notacion_llegada: str,
        notacion_indexado: str = LITTLE_ENDIAN,
    ) -> tuple[NCube, ...]:
        return tuple(
            NCube(
                indice=idx,
                dims=np.array(range(num_nodos), dtype=np.int8),
                data=(
                    tpm[:, idx]
                    if notacion_llegada == LITTLE_ENDIAN
                    else tpm[:, idx][reindexar(num_nodos, notacion_indexado)]
                ).reshape((2,) * num_nodos),
            )
            for idx in range(num_nodos)
        )

    def validacion_inicial(self, tpm: np.ndarray, estado_inicio: np.ndarray) -> int:
        if estado_inicio.size != (num_nodos := tpm.shape[1]):
            raise ValueError(f"Estado inicial debe tener longitud {num_nodos}")
        return num_nodos

    @property
    def indices_ncubos(self):
        return np.array([cube.indice for cube in self.ncubos], dtype=np.int8)

    @property
    def dims_ncubos(self):
        return self.ncubos[0].dims if len(self.ncubos) > 0 else np.array([])

    def condicionar(self, indices: NDArray[np.int8]) -> "System":
        indices_validos = np.intersect1d(self.indices_ncubos, indices)
        if not indices_validos.size:
            return self
        nuevo_sistema = self._new_like()
        nuevo_sistema.ncubos = tuple(
            cube.condicionar(indices_validos, self.estado_inicial)
            for cube in self.ncubos
            if cube.indice not in indices_validos
        )
        nuevo_sistema._ncubos_causales = (
            tuple(
                cube.condicionar(indices_validos, self.estado_inicial)
                for cube in self._ncubos_causales
                if cube.indice not in indices_validos
            )
            if self._ncubos_causales is not None
            else None
        )
        return nuevo_sistema

    def substraer(
        self,
        alcance_idx: NDArray[np.int8] | None = None,
        mecanismo_dims: NDArray[np.int8] | None = None,
        alcance_dims: NDArray[np.int8] | None = None,
    ) -> "System":
        alcance = alcance_idx if alcance_idx is not None else alcance_dims
        if alcance is None or mecanismo_dims is None:
            raise TypeError("substraer requiere alcance_idx/alcance_dims y mecanismo_dims.")

        futuros_validos = np.setdiff1d(self.indices_ncubos, alcance)
        nuevo_sistema = self._new_like()
        nuevo_sistema.ncubos = tuple(
            cube.marginalizar(mecanismo_dims)
            for cube in self.ncubos
            if cube.indice in futuros_validos
        )
        nuevo_sistema._ncubos_causales = (
            tuple(
                cube.marginalizar(mecanismo_dims)
                for cube in self._ncubos_causales
                if cube.indice in futuros_validos
            )
            if self._ncubos_causales is not None
            else None
        )
        return nuevo_sistema

    def bipartir(
        self,
        alcance: NDArray[np.int8],
        mecanismo: NDArray[np.int8],
    ) -> "System":
        dims_particion = tuple(
            sorted({int(dim) for cubo in self.ncubos for dim in cubo.dims})
        )
        spec = PartitionSpec.from_bipartition(
            alcance=alcance,
            mecanismo=mecanismo,
            indices_ncubos=self.indices_ncubos,
            dims_ncubos=dims_particion,
        )
        return self.aplicar_particion(spec)

    def aplicar_particion(self, spec: PartitionSpec) -> "System":
        bloque_por_indice = {
            int(indice): bloque_idx
            for bloque_idx, bloque in enumerate(spec.bloques)
            for indice in bloque
        }
        indices_sin_bloque = [
            int(cubo.indice)
            for cubo in self.ncubos
            if int(cubo.indice) not in bloque_por_indice
        ]
        if indices_sin_bloque:
            raise ValueError(f"PartitionSpec no cubre los n-cubos {indices_sin_bloque}.")

        nuevo_sistema = self._new_like(share_memo=True)
        if spec not in self.memo:
            self.memo[spec] = tuple(
                cubo.marginalizar(
                    np.setdiff1d(
                        cubo.dims,
                        np.array(
                            spec.mecanismos[bloque_por_indice[int(cubo.indice)]],
                            dtype=np.int8,
                        ),
                    )
                )
                for cubo in self.ncubos
            )
        nuevo_sistema.ncubos = self.memo[spec]
        nuevo_sistema._ncubos_causales = (
            tuple(
                cubo.marginalizar(
                    np.setdiff1d(
                        cubo.dims,
                        np.array(
                            spec.mecanismos[bloque_por_indice[int(cubo.indice)]],
                            dtype=np.int8,
                        ),
                    )
                )
                for cubo in self._ncubos_causales
            )
            if self._ncubos_causales is not None
            else None
        )
        return nuevo_sistema

    def distribucion_marginal(self):
        distribucion = self._distribucion_marginal(self.ncubos)
        if self._ncubos_causales is None:
            return distribucion
        return np.concatenate(
            [distribucion, self._distribucion_marginal(self._ncubos_causales)]
        )

    def _distribucion_marginal(self, ncubos: tuple[NCube, ...]) -> NDArray[np.float32]:
        distribucion = np.empty(len(ncubos), dtype=np.float32)

        for idx, ncubo in enumerate(ncubos):
            probabilidad = ncubo.data
            if ncubo.dims.size:
                inicial = tuple(self.estado_inicial[j] for j in ncubo.dims)
                probabilidad = ncubo.data[
                    seleccionar_estado(inicial, self.notacion_indexado)
                ]
            if self.distribucion_complementaria:
                probabilidad = 1 - probabilidad
            distribucion[idx] = probabilidad
        return distribucion

    def _new_like(self, *, share_memo: bool = False) -> "System":
        nuevo_sistema = System.__new__(System)
        nuevo_sistema.estado_inicial = self.estado_inicial
        nuevo_sistema.notacion_llegada = self.notacion_llegada
        nuevo_sistema.notacion_indexado = self.notacion_indexado
        nuevo_sistema.tiempo_emd = self.tiempo_emd
        nuevo_sistema.distribucion_complementaria = self.distribucion_complementaria
        nuevo_sistema.memo = self.memo if share_memo else {}
        return nuevo_sistema

    def __str__(self) -> str:
        sub_dims = self.dims_ncubos
        cubos_info = [f"{cubo}" for cubo in self.ncubos]
        return (
            f"\nSystem(indices={self.indices_ncubos}, dims={sub_dims})"
            f"\nInitial state: {self.estado_inicial}"
            f"\nNCubes:\n" + "\n".join(cubos_info)
        )


def _default_system_config() -> dict[str, object]:
    try:
        from src.models.base.application import aplicacion
    except Exception:
        return {
            "notacion_llegada": LITTLE_ENDIAN,
            "notacion_indexado": LITTLE_ENDIAN,
            "tiempo_emd": EMD_EFFECT,
            "distribucion_complementaria": False,
        }

    method2_style = hasattr(aplicacion, "notacion") and not hasattr(
        aplicacion,
        "notacion_indexado",
    )
    notacion = getattr(aplicacion, "notacion", LITTLE_ENDIAN)
    return {
        "notacion_llegada": getattr(aplicacion, "indexado_llegada", notacion),
        "notacion_indexado": getattr(aplicacion, "notacion_indexado", notacion),
        "tiempo_emd": getattr(aplicacion, "tiempo_emd", getattr(aplicacion, "distancia_metrica", EMD_EFFECT)),
        "distribucion_complementaria": method2_style,
    }
