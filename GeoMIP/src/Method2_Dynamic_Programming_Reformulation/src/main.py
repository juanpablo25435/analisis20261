import os
from pathlib import Path

import yaml

from src.pipeline.batch import BatchConfig, ejecutar_desde_excel


METHOD2_ROOT = Path(__file__).resolve().parents[1]
GEOMIP_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = METHOD2_ROOT / "config.yaml"


def iniciar(config_path: Path | None = None) -> None:
    """Entry point: load YAML configuration and delegate batch execution."""
    config_values = _load_config(config_path or DEFAULT_CONFIG_PATH)
    config = BatchConfig.from_mapping(config_values)
    ruta_entrada = Path(
        os.getenv(
            "GEOMIP_INPUT_XLSX",
            str(GEOMIP_ROOT / "results" / "Pruebas_Metodo2.xlsx"),
        )
    )
    ruta_salida = Path(
        os.getenv(
            "GEOMIP_OUTPUT_XLSX",
            str(GEOMIP_ROOT / "results" / "resultados_Geometric.xlsx"),
        )
    )
    ejecutar_desde_excel(ruta_entrada, ruta_salida, config)


def _load_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as config_file:
        return yaml.safe_load(config_file) or {}
