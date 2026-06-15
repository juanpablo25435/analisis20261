from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from shared_core.middlewares.slogger import SafeLogger

GEOMIP_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = GEOMIP_ROOT / "results"
INPUT_PATH = RESULTS_DIR / "resultados_Geometric.xlsx"
OUTPUT_PATH = RESULTS_DIR / "phi_comparison.png"
LOGGER = SafeLogger("analyze_results")


def main(input_path: Path = INPUT_PATH, output_path: Path = OUTPUT_PATH) -> None:
    """Load Method2 results and generate the Phi effect/cause comparison chart."""
    df = pd.read_excel(input_path)
    valid_results = _valid_results(df)

    if valid_results.empty:
        raise ValueError("No hay filas válidas para graficar Phi_Efecto y Phi_Causa.")

    _plot_phi_comparison(valid_results, output_path)
    LOGGER.info(f"Gráfico guardado en: {output_path}")


def _valid_results(df: pd.DataFrame) -> pd.DataFrame:
    """Return rows with non-empty partitions and parseable Phi columns."""
    required_columns = ["Iteración", "Partición", "Phi_Efecto", "Phi_Causa"]
    missing_columns = [column for column in required_columns if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(missing_columns)}")

    valid_results = df.dropna(subset=required_columns).copy()
    valid_results["Phi_Efecto"] = _parse_phi(valid_results["Phi_Efecto"])
    valid_results["Phi_Causa"] = _parse_phi(valid_results["Phi_Causa"])
    valid_results = valid_results.dropna(subset=["Phi_Efecto", "Phi_Causa"])
    valid_results = valid_results[
        valid_results["Partición"].astype(str).str.strip().ne("")
    ]
    return valid_results


def _parse_phi(values: pd.Series) -> pd.Series:
    """Parse Phi values that may use a decimal comma into numeric floats."""
    return pd.to_numeric(
        values.astype(str).str.replace(",", ".", regex=False),
        errors="coerce",
    )


def _plot_phi_comparison(df: pd.DataFrame, output_path: Path) -> None:
    """Write a grouped bar chart comparing Phi_Efecto and Phi_Causa."""
    labels = df["Iteración"].astype(str)
    positions = range(len(df))
    bar_width = 0.4

    fig, ax = plt.subplots(figsize=(max(8, len(df) * 1.4), 5))
    ax.bar(
        [position - bar_width / 2 for position in positions],
        df["Phi_Efecto"],
        width=bar_width,
        label="Phi_Efecto",
    )
    ax.bar(
        [position + bar_width / 2 for position in positions],
        df["Phi_Causa"],
        width=bar_width,
        label="Phi_Causa",
    )

    ax.set_title("Comparación de Phi_Efecto y Phi_Causa por subsistema")
    ax.set_xlabel("Iteración / subsistema")
    ax.set_ylabel("Phi")
    ax.set_xticks(list(positions))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
