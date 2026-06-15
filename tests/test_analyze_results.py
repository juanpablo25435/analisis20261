import importlib.util
from pathlib import Path
from types import ModuleType

import pandas as pd
import pytest


def _load_analyze_results() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "GeoMIP" / "src" / "analyze_results.py"
    spec = importlib.util.spec_from_file_location("analyze_results", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"No se pudo cargar {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_analyze_results_generates_chart_from_simulated_excel(tmp_path: Path) -> None:
    analyze_results = _load_analyze_results()
    input_path = tmp_path / "resultados_Geometric.xlsx"
    output_path = tmp_path / "phi_comparison.png"
    df = pd.DataFrame(
        {
            "Iteración": [1, 2, 3],
            "Partición": ["Alcance=(A); Mecanismo=(a)", "   ", "Alcance=(B); Mecanismo=(b)"],
            "Phi_Efecto": ["0,25", "0,10", None],
            "Phi_Causa": ["0,50", "0,20", "0,30"],
        }
    )
    df.to_excel(input_path, index=False)

    analyze_results.main(input_path=input_path, output_path=output_path)
    valid_results = analyze_results._valid_results(pd.read_excel(input_path))

    assert output_path.exists()
    assert output_path.stat().st_size > 0
    assert len(valid_results) == 1
    assert valid_results.iloc[0]["Phi_Efecto"] == pytest.approx(0.25)
    assert valid_results.iloc[0]["Phi_Causa"] == pytest.approx(0.50)
