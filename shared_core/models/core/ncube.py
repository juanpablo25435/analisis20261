from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, eq=False)
class NCube:
    """N-dimensional cube associated with one node in a TPM."""

    indice: int
    dims: NDArray[np.int8]
    data: np.ndarray

    def __post_init__(self) -> None:
        if self.dims.size and self.data.shape != (2,) * self.dims.size:
            raise ValueError(f"Forma inválida {self.data.shape} para dimensiones {self.dims}")

    def condicionar(
        self,
        indices_condicionados: NDArray[np.int8],
        estado_inicial: NDArray[np.int8],
    ) -> "NCube":
        numero_dims = self.dims.size
        seleccion = [slice(None)] * numero_dims

        for condicion in indices_condicionados:
            level_arr = numero_dims - (condicion + 1)
            seleccion[level_arr] = estado_inicial[condicion]

        nuevas_dims = np.array(
            [dim for dim in self.dims if dim not in indices_condicionados],
            dtype=np.int8,
        )
        return NCube(
            data=self.data[tuple(seleccion)],
            indice=self.indice,
            dims=nuevas_dims,
        )

    def marginalizar(self, ejes: NDArray[np.int8]) -> "NCube":
        return self._marginalizar(tuple(int(eje) for eje in ejes))

    @lru_cache(maxsize=None)
    def _marginalizar(self, ejes: tuple[int, ...]) -> "NCube":
        marginable_axis = np.intersect1d(np.array(ejes, dtype=np.int8), self.dims)
        if not marginable_axis.size:
            return self
        numero_dims = self.dims.size - 1
        ejes_locales = tuple(
            numero_dims - dim_idx
            for dim_idx, axis in enumerate(self.dims)
            if axis in marginable_axis
        )
        new_dims = np.array(
            [dim for dim in self.dims if dim not in marginable_axis],
            dtype=np.int8,
        )
        return NCube(
            data=np.mean(self.data, axis=ejes_locales, keepdims=False),
            dims=new_dims,
            indice=self.indice,
        )

    def __str__(self) -> str:
        dims_str = f"dims={self.dims}"
        forma_str = f"shape={self.data.shape}"
        datos_str = str(self.data).replace("\n", "\n" + " " * 8)
        return (
            f"NCube(index={self.indice}):\n"
            f"    {dims_str}\n"
            f"    {forma_str}\n"
            f"    data=\n        {datos_str}"
        )
