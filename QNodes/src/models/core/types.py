from dataclasses import dataclass
from typing import Iterable


def _normalizar_bloque(bloque: Iterable[int]) -> tuple[int, ...]:
    return tuple(sorted({int(nodo) for nodo in bloque}))


def _normalizar_bloques(
    bloques: Iterable[Iterable[int]],
) -> tuple[tuple[int, ...], ...]:
    return tuple(_normalizar_bloque(bloque) for bloque in bloques)


def _validar_bloques_disjuntos(
    nombre: str,
    bloques: tuple[tuple[int, ...], ...],
) -> None:
    nodos = [nodo for bloque in bloques for nodo in bloque]
    if len(nodos) != len(set(nodos)):
        raise ValueError(f"PartitionSpec contiene nodos repetidos en {nombre}.")


@dataclass(frozen=True)
class PartitionSpec:
    """
    Especificación inmutable de una partición k-vías.

    `bloques` representa los bloques del alcance/futuro. Cuando no se proveen
    `mecanismos`, se asume la misma partición para el mecanismo/presente.
    """

    bloques: tuple[tuple[int, ...], ...]
    mecanismos: tuple[tuple[int, ...], ...] = ()

    def __post_init__(self) -> None:
        bloques = _normalizar_bloques(self.bloques)
        mecanismos = (
            _normalizar_bloques(self.mecanismos) if self.mecanismos else bloques
        )

        if not bloques:
            raise ValueError("PartitionSpec requiere al menos un bloque.")
        if len(bloques) != len(mecanismos):
            raise ValueError(
                "PartitionSpec requiere igual cantidad de bloques y mecanismos."
            )

        _validar_bloques_disjuntos("bloques", bloques)
        _validar_bloques_disjuntos("mecanismos", mecanismos)

        object.__setattr__(self, "bloques", bloques)
        object.__setattr__(self, "mecanismos", mecanismos)

    @classmethod
    def from_bipartition(
        cls,
        alcance: Iterable[int],
        mecanismo: Iterable[int],
        indices_ncubos: Iterable[int],
        dims_ncubos: Iterable[int],
    ) -> "PartitionSpec":
        bloque_alcance = _normalizar_bloque(alcance)
        bloque_mecanismo = _normalizar_bloque(mecanismo)
        alcance_set = set(bloque_alcance)
        mecanismo_set = set(bloque_mecanismo)

        return cls(
            bloques=(
                bloque_alcance,
                tuple(
                    int(indice)
                    for indice in indices_ncubos
                    if int(indice) not in alcance_set
                ),
            ),
            mecanismos=(
                bloque_mecanismo,
                tuple(
                    int(dim) for dim in dims_ncubos if int(dim) not in mecanismo_set
                ),
            ),
        )
