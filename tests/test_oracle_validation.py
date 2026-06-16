"""Oracle validation for the geometric IIT k-partition heuristic.

This module is the Oracle validation required by the technical documentation:
for a small N=3 system, the exact brute-force strategy is treated as the global
optimum oracle and the geometric heuristic must reproduce the same Phi loss and
logical `PartitionSpec` for k=2.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from shared_core.models.core.types import PartitionSpec

REPO_ROOT = Path(__file__).resolve().parents[1]
METHOD2_ROOT = REPO_ROOT / "GeoMIP" / "src" / "Method2_Dynamic_Programming_Reformulation"

INITIAL_STATE = "000"
CONDITIONS = "111"
PURVIEW = "111"
MECHANISM = "111"
K = 2
PHI_TOLERANCE = 1e-12


@dataclass(frozen=True)
class StrategyRun:
    """Observed output from a strategy run, including its selected partition."""

    strategy: str
    phi: float
    spec: PartitionSpec
    partition: str


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


def _known_n3_tpm() -> np.ndarray:
    """Return a deterministic N=3 TPM with a known oracle-aligned k=2 optimum.

    Nodes A and C share the same transition profile while B remains independent,
    so the geometric clustering candidate `(A,C) / (B)` is expected to be the
    same partition selected by exhaustive brute force.
    """
    states = np.array(
        [[int(bit) for bit in f"{state:03b}"] for state in range(8)],
        dtype=np.float32,
    )
    return states[:, [0, 1, 0]].astype(np.float32)


def _capture_selected_spec(strategy) -> dict[str, PartitionSpec]:
    captured: dict[str, PartitionSpec] = {}
    original_formatter: Callable[[PartitionSpec], str] = strategy._formatear_particion

    def recording_formatter(spec: PartitionSpec) -> str:
        captured["spec"] = spec
        return original_formatter(spec)

    strategy._formatear_particion = recording_formatter
    return captured


def _run_oracle_validation() -> tuple[StrategyRun, StrategyRun]:
    """Run brute-force oracle and geometric heuristic on the same N=3 system."""
    with _project_src_import(METHOD2_ROOT):
        from src.controllers.manager import Manager
        from src.controllers.strategies.k_force import KForceSIA
        from src.controllers.strategies.k_geometric import KGeometricSIA
        from src.models.base.application import aplicacion

        tpm = _known_n3_tpm()
        aplicacion.profiler_habilitado = False

        aplicacion.set_distancia_integrada()
        force_strategy = KForceSIA(Manager(estado_inicial=INITIAL_STATE))
        force_capture = _capture_selected_spec(force_strategy)
        force_solution = force_strategy.aplicar_estrategia(
            condiciones=CONDITIONS,
            alcance=PURVIEW,
            mecanismo=MECHANISM,
            tpm=tpm,
            k_max=K,
        )

        aplicacion.set_distancia_integrada()
        geometric_strategy = KGeometricSIA(Manager(estado_inicial=INITIAL_STATE))
        geometric_capture = _capture_selected_spec(geometric_strategy)
        geometric_solution = geometric_strategy.aplicar_estrategia(
            condiciones=CONDITIONS,
            alcance=PURVIEW,
            mecanismo=MECHANISM,
            tpm=tpm,
            k_max=K,
        )

    return (
        _to_strategy_run(force_solution, force_capture),
        _to_strategy_run(geometric_solution, geometric_capture),
    )


def _to_strategy_run(solution, captured: dict[str, PartitionSpec]) -> StrategyRun:
    spec = captured.get("spec")
    assert spec is not None, "The strategy did not select a PartitionSpec."
    return StrategyRun(
        strategy=solution.estrategia,
        phi=float(solution.perdida),
        spec=spec,
        partition=solution.particion,
    )


def _normalize_partition_spec(
    spec: PartitionSpec,
) -> tuple[tuple[tuple[int, ...], tuple[int, ...]], ...]:
    """Normalize block order while preserving each purview/mechanism pairing."""
    return tuple(
        sorted(
            (
                tuple(sorted(int(node) for node in block)),
                tuple(sorted(int(node) for node in mechanism)),
            )
            for block, mechanism in zip(spec.bloques, spec.mecanismos)
        )
    )


def _format_report(force: StrategyRun, geometric: StrategyRun) -> str:
    return "\n".join(
        [
            "Oracle validation report",
            f"Brute-force strategy: {force.strategy}",
            f"Brute-force Phi loss: {force.phi}",
            f"Brute-force PartitionSpec: {_normalize_partition_spec(force.spec)}",
            f"Brute-force formatted partition: {force.partition}",
            f"Geometric strategy: {geometric.strategy}",
            f"Geometric Phi loss: {geometric.phi}",
            f"Geometric PartitionSpec: {_normalize_partition_spec(geometric.spec)}",
            f"Geometric formatted partition: {geometric.partition}",
        ]
    )


def test_geometric_k2_matches_bruteforce_oracle_on_known_n3_system() -> None:
    """Validate the geometric IIT heuristic against the brute-force Oracle.

    This is the required Oracle validation: `KForceSIA` exhaustively evaluates
    all k=2 partitions on a small N=3 system and therefore acts as the global
    optimum reference. `KGeometricSIA` must return the same Phi information loss
    and the same logical `PartitionSpec` structure.
    """
    force, geometric = _run_oracle_validation()
    report = _format_report(force, geometric)

    assert len(force.spec.bloques) == K
    assert len(geometric.spec.bloques) == K
    assert force.phi == pytest.approx(
        geometric.phi,
        rel=PHI_TOLERANCE,
        abs=PHI_TOLERANCE,
    ), report
    assert _normalize_partition_spec(force.spec) == _normalize_partition_spec(
        geometric.spec
    ), report


if __name__ == "__main__":
    oracle_force, oracle_geometric = _run_oracle_validation()
    print(_format_report(oracle_force, oracle_geometric))
    assert oracle_force.phi == pytest.approx(
        oracle_geometric.phi,
        rel=PHI_TOLERANCE,
        abs=PHI_TOLERANCE,
    )
    assert _normalize_partition_spec(oracle_force.spec) == _normalize_partition_spec(
        oracle_geometric.spec
    )
