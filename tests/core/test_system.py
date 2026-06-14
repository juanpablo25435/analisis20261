import numpy as np
import pytest

from src.models.enums.notation import Notation
from src.models.enums.temporal_emd import TimeEMD
from shared_core.models.core.system import System


@pytest.fixture(autouse=True)
def default_application_settings() -> None:
    # Keep the fixture explicit so these tests exercise the shared model
    # independently from whichever subproject configuration is importable.
    pass


@pytest.fixture
def small_tpm() -> np.ndarray:
    return np.arange(24, dtype=np.float32).reshape((8, 3))


@pytest.fixture
def initial_state() -> np.ndarray:
    return np.array([1, 1, 0], dtype=np.int8)


@pytest.fixture
def system(small_tpm: np.ndarray, initial_state: np.ndarray) -> System:
    return System(
        small_tpm,
        initial_state,
        notacion_llegada=Notation.LIL_ENDIAN.value,
        notacion_indexado=Notation.LIL_ENDIAN.value,
        tiempo_emd=TimeEMD.EMD_EFECTO.value,
        distribucion_complementaria=False,
    )


def test_system_creates_one_ncube_per_tpm_column(
    system: System,
    small_tpm: np.ndarray,
) -> None:
    assert len(system.ncubos) == 3
    np.testing.assert_array_equal(system.indices_ncubos, np.array([0, 1, 2], dtype=np.int8))
    np.testing.assert_array_equal(system.dims_ncubos, np.array([0, 1, 2], dtype=np.int8))

    for column, ncube in enumerate(system.ncubos):
        assert ncube.indice == column
        np.testing.assert_array_equal(ncube.data, small_tpm[:, column].reshape((2, 2, 2)))


def test_system_rejects_initial_state_with_wrong_size(small_tpm: np.ndarray) -> None:
    with pytest.raises(ValueError):
        System(
            small_tpm,
            np.array([1, 0], dtype=np.int8),
            notacion_llegada=Notation.LIL_ENDIAN.value,
            notacion_indexado=Notation.LIL_ENDIAN.value,
            tiempo_emd=TimeEMD.EMD_EFECTO.value,
            distribucion_complementaria=False,
        )


def test_condicionar_removes_conditioned_future_node_and_selects_face(
    system: System,
    small_tpm: np.ndarray,
) -> None:
    conditioned = system.condicionar(np.array([2], dtype=np.int8))

    np.testing.assert_array_equal(conditioned.indices_ncubos, np.array([0, 1], dtype=np.int8))
    np.testing.assert_array_equal(conditioned.dims_ncubos, np.array([0, 1], dtype=np.int8))
    np.testing.assert_array_equal(
        conditioned.ncubos[0].data,
        small_tpm[:, 0].reshape((2, 2, 2))[0, :, :],
    )


def test_substraer_drops_future_node_and_marginalizes_mechanism_dimension(
    system: System,
    small_tpm: np.ndarray,
) -> None:
    subsystem = system.substraer(
        alcance_idx=np.array([0], dtype=np.int8),
        mecanismo_dims=np.array([2], dtype=np.int8),
    )

    np.testing.assert_array_equal(subsystem.indices_ncubos, np.array([1, 2], dtype=np.int8))
    np.testing.assert_array_equal(subsystem.dims_ncubos, np.array([0, 1], dtype=np.int8))
    np.testing.assert_array_equal(
        subsystem.ncubos[0].data,
        small_tpm[:, 1].reshape((2, 2, 2)).mean(axis=0),
    )


def test_distribucion_marginal_selects_initial_state_in_little_endian_order(
    system: System,
    small_tpm: np.ndarray,
) -> None:
    expected = np.array(
        [
            small_tpm[:, column].reshape((2, 2, 2))[0, 1, 1]
            for column in range(3)
        ],
        dtype=np.float32,
    )

    np.testing.assert_array_equal(system.distribucion_marginal(), expected)
