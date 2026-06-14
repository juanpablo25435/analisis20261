import numpy as np
import pytest

from shared_core.models.core.ncube import NCube


@pytest.fixture
def cube_data() -> np.ndarray:
    return np.arange(8, dtype=np.float32).reshape((2, 2, 2))


@pytest.fixture
def ncube(cube_data: np.ndarray) -> NCube:
    return NCube(indice=1, dims=np.array([0, 1, 2], dtype=np.int8), data=cube_data)


def test_ncube_rejects_shape_that_does_not_match_dimensions() -> None:
    with pytest.raises(ValueError, match="Forma inválida"):
        NCube(
            indice=0,
            dims=np.array([0, 1, 2], dtype=np.int8),
            data=np.zeros((2, 2), dtype=np.float32),
        )


def test_condicionar_selects_configured_face_and_removes_dimension(
    ncube: NCube,
    cube_data: np.ndarray,
) -> None:
    conditioned = ncube.condicionar(
        indices_condicionados=np.array([2], dtype=np.int8),
        estado_inicial=np.array([1, 0, 0], dtype=np.int8),
    )

    assert conditioned.indice == ncube.indice
    np.testing.assert_array_equal(conditioned.dims, np.array([0, 1], dtype=np.int8))
    np.testing.assert_array_equal(conditioned.data, cube_data[0, :, :])


def test_marginalizar_averages_requested_dimension(
    ncube: NCube,
    cube_data: np.ndarray,
) -> None:
    marginalized = ncube.marginalizar(np.array([1], dtype=np.int8))

    np.testing.assert_array_equal(marginalized.dims, np.array([0, 2], dtype=np.int8))
    np.testing.assert_array_equal(marginalized.data, cube_data.mean(axis=1))


def test_marginalizar_returns_same_cube_when_dimension_is_absent(ncube: NCube) -> None:
    assert ncube.marginalizar(np.array([9], dtype=np.int8)) is ncube
