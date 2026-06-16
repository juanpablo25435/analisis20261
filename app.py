from __future__ import annotations

import contextlib
import html
import os
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

try:
    import plotly.express as px
except (ImportError, ModuleNotFoundError):
    px = None


REPO_ROOT = Path(__file__).resolve().parent
QNODES_ROOT = REPO_ROOT / "QNodes"
METHOD2_ROOT = REPO_ROOT / "GeoMIP" / "src" / "Method2_Dynamic_Programming_Reformulation"
GEOMIP_RESULTS_DIR = REPO_ROOT / "GeoMIP" / "results"
QNODES_RESULTS_DIR = REPO_ROOT / "QNodes" / "results"
UPLOADS_DIR = REPO_ROOT / ".streamlit_uploads"

GEOMIP_INPUT_DEFAULT = GEOMIP_RESULTS_DIR / "Pruebas_Metodo2.xlsx"
GEOMIP_OUTPUT_DEFAULT = GEOMIP_RESULTS_DIR / "resultados_Geometric.xlsx"
QNODES_OUTPUT_DEFAULT = QNODES_RESULTS_DIR / "resultados_QNodes.csv"
PHI_COMPARISON_PNG = GEOMIP_RESULTS_DIR / "phi_comparison.png"

APP_LOGGER_TAG = "kgeomip_streamlit"
GEOMIP_LOG_TAGS = ("Geometric_batch_pipeline", "K-Geometric_strategy", "method2_manager")
QNODES_LOG_TAGS = ("Q-Nodes_strategy", "qnodes_main", "qnodes_manager")

ENGINE_QNODES = "Método 1: QNodes (Optimización Submodular)"
ENGINE_GEOMIP = "Método 2: GeoMIP (Aglomeración Geométrica)"
SOURCE_EXCEL = "Cargar desde Excel Completo"
SOURCE_CSV = "Subir Matriz TPM Personalizada (.csv)"


@dataclass(frozen=True)
class PipelineRequest:
    engine: str
    data_source: str
    sheet_index: int
    column: str
    skiprows: int
    start: int
    count: int
    timeout_seconds: int
    default_k_max: int
    estado_inicio: str
    condiciones: str
    alcance: str
    mecanismo: str
    sample_page: str
    profiling_enabled: bool
    excel_path: Path | None
    tpm_path: Path | None
    output_path: Path


@dataclass(frozen=True)
class PipelineOutcome:
    result_path: Path
    stopped: bool = False
    rows_processed: int = 0


@dataclass
class PipelineJob:
    request: PipelineRequest
    stop_event: threading.Event
    thread: threading.Thread | None = None
    started_at: float = field(default_factory=time.time)
    outcome: PipelineOutcome | None = None
    error: str | None = None
    traceback_text: str | None = None
    message: str = "Preparando ejecución..."
    done: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)


def main() -> None:
    st.set_page_config(
        page_title="KGeoMIP Analytics Framework",
        page_icon="⚔️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_styles()
    _init_state()

    st.title("KGeoMIP Analytics Framework")
    st.caption("Orquestador visual unificado para QNodes y GeoMIP")

    with st.sidebar:
        st.header("Control del Motor")
        engine = st.radio(
            "Motor matemático",
            [ENGINE_QNODES, ENGINE_GEOMIP],
            index=1,
        )
        data_source = st.radio(
            "Origen de datos",
            [SOURCE_EXCEL, SOURCE_CSV],
            index=0,
        )
        st.divider()
        st.metric("Framework", "IIT / MIP")
        st.caption("Streamlit + pipelines Python existentes")

    tab_config, tab_monitor, tab_dashboard, tab_arena = st.tabs(
        [
            "⚙️ Configuración Dinámica",
            "🚀 Monitor de Ejecución y Resiliencia",
            "📊 Dashboard de Resultados",
            "⚔️ Arena Comparativa",
        ]
    )

    request_to_run: PipelineRequest | None = None
    with tab_config:
        request_to_run = _render_configuration(engine, data_source)

    with tab_monitor:
        _render_monitor(request_to_run)

    with tab_dashboard:
        _render_dashboard()

    with tab_arena:
        _render_arena()


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container { padding-top: 2rem; }
        div.stButton > button:first-child {
            min-height: 3.1rem;
            border-radius: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.01em;
        }
        .kpi-card {
            border: 1px solid rgba(128, 128, 128, 0.22);
            border-radius: 0.85rem;
            padding: 1rem;
            background: rgba(128, 128, 128, 0.06);
        }
        .log-console {
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 0.84rem;
            line-height: 1.42;
            max-height: 520px;
            overflow-y: auto;
            border: 1px solid rgba(128, 128, 128, 0.28);
            border-radius: 0.75rem;
            padding: 0.85rem;
            background: rgba(0, 0, 0, 0.18);
        }
        .log-critical { color: #2ecc71; font-weight: 700; }
        .log-error { color: #ff6b6b; font-weight: 700; }
        .log-muted { color: #a8b3c7; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _init_state() -> None:
    st.session_state.setdefault("last_result_path", None)
    st.session_state.setdefault("last_engine", ENGINE_GEOMIP)
    st.session_state.setdefault("last_status", "Sin ejecuciones en esta sesión.")
    st.session_state.setdefault("ejecutando", False)
    st.session_state.setdefault("stop_requested", False)
    st.session_state.setdefault("pipeline_job", None)
    st.session_state.setdefault("pipeline_request", None)
    st.session_state.setdefault("pipeline_started_at", None)


def _render_configuration(engine: str, data_source: str) -> PipelineRequest | None:
    st.subheader("Parámetros de entrada")
    st.write(
        "Configura el origen de datos y los parámetros del motor. "
        "La ejecución se monitorea en la pestaña de resiliencia."
    )

    excel_upload = None
    tpm_upload = None
    excel_path_text = str(GEOMIP_INPUT_DEFAULT)

    if data_source == SOURCE_EXCEL:
        left, mid, right = st.columns(3)
        with left:
            sheet_index = st.number_input("sheet_index", min_value=0, value=8, step=1)
            skiprows = st.number_input("skiprows", min_value=0, value=3, step=1)
        with mid:
            column = st.text_input("column", value="B", max_chars=8)
            start = st.number_input("start", min_value=0, value=0, step=1)
        with right:
            count = st.number_input("count", min_value=1, value=50, step=1)
            timeout_seconds = st.number_input(
                "timeout_seconds por subsistema",
                min_value=5,
                value=3600,
                step=5,
            )

        excel_path_text = st.text_input(
            "Ruta del Excel completo",
            value=str(GEOMIP_INPUT_DEFAULT),
            help="Puedes usar la ruta por defecto o subir un Excel temporal.",
        )
        excel_upload = st.file_uploader(
            "Opcional: subir Excel completo",
            type=["xlsx", "xls"],
            accept_multiple_files=False,
        )
    else:
        sheet_index, column, skiprows, start, count, timeout_seconds = 8, "B", 3, 0, 1, 3600
        tpm_upload = st.file_uploader(
            "Matriz TPM personalizada (.csv)",
            type=["csv"],
            accept_multiple_files=False,
        )
        if tpm_upload is not None:
            _preview_uploaded_csv(tpm_upload)

    st.divider()
    st.subheader("Parámetros del motor")

    if engine == ENGINE_GEOMIP:
        default_k_max = st.slider("DEFAULT_K_MAX", min_value=2, max_value=5, value=5)
        estado_inicio = st.text_input("estado_inicio", value="000")
        condiciones_default = "1" * max(1, len(estado_inicio))
        condiciones = st.text_input("condiciones", value=condiciones_default)

        if data_source == SOURCE_CSV:
            alcance = st.text_input("alcance", value=condiciones_default)
            mecanismo = st.text_input("mecanismo", value=condiciones_default)
        else:
            alcance = condiciones_default
            mecanismo = condiciones_default
            st.info(
                "GeoMIP en modo Excel toma alcance y mecanismo desde cada fila "
                "del libro de subsistemas."
            )
        sample_page = "A"
        profiling_enabled = True
        output_path = GEOMIP_OUTPUT_DEFAULT
    else:
        default_k_max = 2
        left, right = st.columns(2)
        with left:
            estado_inicio = st.text_input("estado_inicial", value="1000")
            condiciones = st.text_input("condiciones", value="1110")
            sample_page = st.text_input("página de muestra", value="A", max_chars=2)
        with right:
            alcance = st.text_input("alcance", value="1110")
            mecanismo = st.text_input("mecanismo", value="1110")
            profiling_enabled = st.checkbox("activar profiling QNodes", value=False)
        output_path = QNODES_OUTPUT_DEFAULT
        st.caption(
            "QNodes expone el caso de análisis como estado, condiciones, alcance "
            "y mecanismo; el algoritmo submodular no usa DEFAULT_K_MAX."
        )

    st.divider()
    launch = st.button(
        "▶️ Lanzar Pipeline por Lotes",
        type="primary",
        use_container_width=True,
    )

    if not launch:
        return None

    if st.session_state.get("ejecutando"):
        st.warning("Ya hay un pipeline en ejecución. Detenlo o espera a que termine.")
        return None

    try:
        excel_path = (
            _save_uploaded_file(excel_upload, "excel")
            if excel_upload is not None
            else Path(excel_path_text).expanduser()
        )
        tpm_path = _save_uploaded_file(tpm_upload, "tpm") if tpm_upload is not None else None
    except OSError as error:
        st.error(f"No se pudo preparar el archivo de entrada: {error}")
        return None

    if data_source == SOURCE_CSV and tpm_path is None:
        st.error("Sube una matriz TPM CSV antes de lanzar el pipeline.")
        return None

    request = PipelineRequest(
        engine=engine,
        data_source=data_source,
        sheet_index=int(sheet_index),
        column=column.strip() or "B",
        skiprows=int(skiprows),
        start=int(start),
        count=int(count),
        timeout_seconds=int(timeout_seconds),
        default_k_max=int(default_k_max),
        estado_inicio=estado_inicio.strip(),
        condiciones=condiciones.strip(),
        alcance=alcance.strip(),
        mecanismo=mecanismo.strip(),
        sample_page=(sample_page.strip() or "A").upper(),
        profiling_enabled=bool(profiling_enabled),
        excel_path=excel_path if data_source == SOURCE_EXCEL else None,
        tpm_path=tpm_path,
        output_path=output_path,
    )

    st.session_state["last_status"] = "Ejecución solicitada."
    return request


def _render_monitor(request: PipelineRequest | None) -> None:
    st.subheader("Consola viva y tolerancia a fallos")
    st.write(
        "El monitor lee los archivos `SafeLogger` y resalta eventos críticos "
        "en verde y errores de validación en rojo."
    )

    if request is not None:
        _start_pipeline_job(request)

    active_request = st.session_state.get("pipeline_request")
    log_tags = _log_tags_for_engine(
        active_request.engine if active_request is not None else st.session_state["last_engine"]
    )

    stop_col, status_col = st.columns([1, 2])
    with stop_col:
        stop_clicked = st.button(
            "🛑 Detener Inmediatamente",
            type="secondary",
            use_container_width=True,
            disabled=not st.session_state.get("ejecutando"),
        )
    if stop_clicked:
        _request_pipeline_stop()

    job = st.session_state.get("pipeline_job")
    if job is not None and _job_is_done(job):
        _finish_pipeline_job(job)
        st.rerun()

    progress = st.progress(0, text="Esperando lanzamiento del pipeline...")
    status_box = st.empty()
    log_box = st.empty()

    if st.session_state.get("ejecutando"):
        started_at = st.session_state.get("pipeline_started_at") or time.time()
        elapsed = time.time() - started_at
        estimated = max(12.0, (active_request.count if active_request else 1) * 2.5)
        progress.progress(
            min(0.95, elapsed / estimated),
            text=f"Procesando... {elapsed:0.1f}s transcurridos",
        )
        if st.session_state.get("stop_requested"):
            status_box.warning("Detención solicitada. Se cerrará al terminar la iteración actual.")
        else:
            status_box.info("Pipeline en ejecución. Puedes observar el log en vivo abajo.")
        job_message = _job_message(job)
        if job_message:
            st.write(job_message)
        with status_col:
            st.caption(st.session_state["last_status"])
        _render_logs(log_box, log_tags)
        time.sleep(0.8)
        st.rerun()
        return

    progress.progress(1.0 if st.session_state.get("last_result_path") else 0, text="Pipeline inactivo.")
    status_box.info(st.session_state["last_status"])
    with status_col:
        st.caption("Estado: inactivo")
    _render_logs(log_box, log_tags)


def _start_pipeline_job(request: PipelineRequest) -> None:
    if st.session_state.get("ejecutando"):
        st.warning("Ya existe un pipeline activo; no se iniciará otro.")
        return

    stop_event = threading.Event()
    job = PipelineJob(request=request, stop_event=stop_event)
    worker_thread = threading.Thread(
        target=_pipeline_worker,
        args=(job,),
        name=f"kgeomip-worker-{int(time.time())}",
        daemon=True,
    )
    job.thread = worker_thread

    st.session_state["pipeline_job"] = job
    st.session_state["pipeline_request"] = request
    st.session_state["pipeline_started_at"] = job.started_at
    st.session_state["ejecutando"] = True
    st.session_state["stop_requested"] = False
    st.session_state["last_engine"] = request.engine
    st.session_state["last_status"] = f"Ejecutando {request.engine}."
    worker_thread.start()


def _request_pipeline_stop() -> None:
    job = st.session_state.get("pipeline_job")
    if job is not None:
        job.stop_event.set()
        _set_job_message(job, "Corte de emergencia solicitado por el usuario.")
    st.session_state["stop_requested"] = True
    st.session_state["last_status"] = "Detención solicitada por el usuario."
    st.rerun()


def _finish_pipeline_job(job: PipelineJob) -> None:
    outcome: PipelineOutcome | None
    error: str | None
    traceback_text: str | None
    with job.lock:
        outcome = job.outcome
        error = job.error
        traceback_text = job.traceback_text

    try:
        if error is not None:
            if traceback_text:
                _log_error(_safe_logger(APP_LOGGER_TAG), traceback_text)
            raise RuntimeError(error)
        if outcome is None:
            raise RuntimeError("El hilo terminó sin devolver resultado.")
    except Exception as error:
        st.session_state["last_status"] = f"Error: {error}"
        st.error(f"La ejecución falló: {error}")
    else:
        st.session_state["last_result_path"] = str(outcome.result_path)
        if outcome.stopped:
            st.session_state["last_status"] = (
                f"Ejecución detenida. Filas guardadas: {outcome.rows_processed}. "
                f"Resultado parcial: {outcome.result_path}"
            )
            st.warning(st.session_state["last_status"])
        else:
            st.session_state["last_status"] = (
                f"Última ejecución completada: {outcome.result_path} "
                f"({outcome.rows_processed} filas)."
            )
            st.success(f"Resultados disponibles en `{outcome.result_path}`")
    finally:
        st.session_state["ejecutando"] = False
        st.session_state["stop_requested"] = False
        st.session_state["pipeline_job"] = None
        st.session_state["pipeline_request"] = None
        st.session_state["pipeline_started_at"] = None


def _pipeline_worker(job: PipelineJob) -> None:
    try:
        outcome = _run_pipeline(
            job.request,
            job.stop_event,
            progress_callback=lambda msg: _set_job_message(job, msg),
        )
    except Exception as error:
        with job.lock:
            job.error = str(error)
            job.traceback_text = traceback.format_exc()
            job.done = True
            job.message = f"Error: {error}"
    else:
        with job.lock:
            job.outcome = outcome
            job.done = True
            job.message = (
                "Ejecución detenida y resultados parciales guardados."
                if outcome.stopped
                else "Ejecución completada."
            )


def _job_is_done(job: PipelineJob) -> bool:
    with job.lock:
        return job.done


def _job_message(job: PipelineJob | None) -> str:
    if job is None:
        return ""
    with job.lock:
        return job.message


def _set_job_message(job: PipelineJob, message: str) -> None:
    with job.lock:
        job.message = message


def _render_dashboard() -> None:
    st.subheader("Resultados interactivos")
    result_paths = _discover_result_files()
    default_path = st.session_state.get("last_result_path")

    if not result_paths:
        st.info("Aún no hay archivos de resultados. Ejecuta un pipeline para poblar el dashboard.")
        return

    selected_index = 0
    if default_path:
        for idx, path in enumerate(result_paths):
            if str(path) == default_path:
                selected_index = idx
                break

    selected_path = st.selectbox(
        "Archivo de resultados",
        result_paths,
        index=selected_index,
        format_func=lambda path: str(path.relative_to(REPO_ROOT)),
    )

    try:
        df = _load_result_table(selected_path)
    except (OSError, ValueError) as error:
        st.error(f"No se pudo cargar el resultado: {error}")
        return

    if df.empty:
        st.warning("El archivo existe, pero no contiene filas para visualizar.")
        return

    df = _coerce_phi_columns(df)
    filtered = _render_result_filters(df)

    left, mid, right = st.columns(3)
    left.metric("Filas", len(filtered))
    phi_columns = _phi_columns(filtered)
    if phi_columns:
        primary_phi = phi_columns[0]
        mid.metric(f"Promedio {primary_phi}", f"{filtered[primary_phi].mean():.5f}")
        right.metric(f"Máximo {primary_phi}", f"{filtered[primary_phi].max():.5f}")
    else:
        mid.metric("Columnas", len(filtered.columns))
        right.metric("Phi", "No detectado")

    st.dataframe(filtered, use_container_width=True, hide_index=True)
    _render_phi_visuals(filtered, selected_path)


def _render_result_filters(df: pd.DataFrame) -> pd.DataFrame:
    filtered = df.copy()
    filter_columns = [
        column
        for column in ("Partición", "Alcance", "Mecanismo", "Estado")
        if column in filtered.columns
    ]
    query = st.text_input(
        "Filtrar subsistemas / particiones",
        value="",
        placeholder="Ej: 1110, A, partición...",
    )
    if query and filter_columns:
        mask = pd.Series(False, index=filtered.index)
        for column in filter_columns:
            mask |= filtered[column].astype(str).str.contains(query, case=False, na=False)
        filtered = filtered[mask]

    phi_columns = _phi_columns(filtered)
    if phi_columns:
        phi_column = st.selectbox("Columna Phi para filtro", phi_columns)
        min_phi = float(filtered[phi_column].min())
        max_phi = float(filtered[phi_column].max())
        if min_phi < max_phi:
            phi_range = st.slider(
                "Rango Phi",
                min_value=min_phi,
                max_value=max_phi,
                value=(min_phi, max_phi),
            )
            filtered = filtered[
                filtered[phi_column].between(phi_range[0], phi_range[1], inclusive="both")
            ]
    return filtered


def _render_phi_visuals(df: pd.DataFrame, result_path: Path) -> None:
    st.subheader("Visualización de Phi")
    phi_columns = _phi_columns(df)
    if not phi_columns:
        st.info("No se detectaron columnas Phi numéricas para graficar.")
        return

    if px is not None:
        plot_df = df.reset_index(names="Índice")
        metadata_columns = (
            "Índice",
            "Iteración",
            "Métrica",
            "Método",
            "N",
            "Partición",
            "Subsistema",
            "Estado",
            "Condiciones",
            "Alcance",
            "Mecanismo",
            "Tiempo de ejecución (s)",
        )
        if "Phi" in plot_df.columns and len(phi_columns) == 1:
            chart_df = plot_df.dropna(subset=["Phi"]).copy()
            y_axis = "Phi"
            color_axis = "Métrica" if "Métrica" in chart_df.columns else None
        else:
            id_vars = [
                column
                for column in metadata_columns
                if column in plot_df.columns and column not in phi_columns
            ]
            chart_df = plot_df.melt(
                id_vars=id_vars,
                value_vars=phi_columns,
                var_name="Métrica",
                value_name="Valor_Phi",
            ).dropna(subset=["Valor_Phi"])
            y_axis = "Valor_Phi"
            color_axis = "Métrica"

        x_axis = "Iteración" if "Iteración" in chart_df.columns else "Índice"
        hover_data = [
            column
            for column in metadata_columns
            if column in chart_df.columns and column not in {x_axis, color_axis}
        ]
        fig = px.scatter(
            chart_df,
            x=x_axis,
            y=y_axis,
            color=color_axis,
            hover_data=hover_data if hover_data else None,
            labels={y_axis: "Phi"},
            title="Dispersión interactiva de Phi por subsistema",
        )
        fig.update_layout(legend_title_text="", margin=dict(l=10, r=10, t=55, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.line_chart(df[phi_columns])

    if PHI_COMPARISON_PNG.exists() and result_path.suffix.lower() in {".xlsx", ".xls"}:
        st.image(str(PHI_COMPARISON_PNG), caption="Gráfico de asimetría Phi_Efecto vs Phi_Causa")


def _render_arena() -> None:
    st.subheader("QNodes vs GeoMIP")
    st.write(
        "Compara tiempos de ejecución por tamaño de red `N` usando los históricos "
        "disponibles en los directorios de resultados."
    )

    comparison = _build_comparison_frame()
    if comparison.empty:
        st.info(
            "No hay suficientes resultados con tiempos de ejecución para comparar. "
            "Ejecuta al menos un pipeline de QNodes o GeoMIP."
        )
        return

    st.dataframe(comparison, use_container_width=True, hide_index=True)

    if px is not None:
        fig = px.bar(
            comparison,
            x="N",
            y="Tiempo de Ejecución (segundos)",
            color="Método",
            barmode="group",
            text_auto=".3f",
            title="Tiempo de Ejecución (segundos) QNodes vs GeoMIP",
        )
        fig.update_layout(margin=dict(l=10, r=10, t=55, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        pivot = comparison.pivot_table(
            index="N",
            columns="Método",
            values="Tiempo de Ejecución (segundos)",
            aggfunc="mean",
        )
        st.bar_chart(pivot)


def _run_pipeline(
    request: PipelineRequest,
    stop_event: threading.Event,
    progress_callback=None,
) -> PipelineOutcome:
    logger = _safe_logger(APP_LOGGER_TAG)
    _log_critical(logger, f"Inicio pipeline: {request.engine} | fuente={request.data_source}")
    try:
        if request.engine == ENGINE_QNODES:
            outcome = _run_qnodes(request, stop_event, progress_callback=progress_callback)
        elif request.engine == ENGINE_GEOMIP and request.data_source == SOURCE_EXCEL:
            outcome = _run_geomip_excel(request, stop_event, progress_callback=progress_callback)
        elif request.engine == ENGINE_GEOMIP:
            outcome = _run_geomip_single_csv(request, stop_event, progress_callback=progress_callback)
        else:
            raise ValueError(f"Motor no reconocido: {request.engine}")
    except Exception as error:
        _log_error(logger, "Error de validación estructural o ejecución.", error)
        _log_error(logger, traceback.format_exc())
        raise

    if outcome.stopped:
        _log_critical(logger, f"Pipeline detenido por el usuario: {outcome.result_path}")
    else:
        _log_critical(logger, f"Pipeline completado correctamente: {outcome.result_path}")
    return outcome


def _notify_progress(progress_callback, message: str) -> None:
    if progress_callback is not None:
        progress_callback(message)


def _iteration_prefix(current: int, total: int) -> str:
    width = max(2, len(str(max(total, 1))))
    return f"[Iteración {current:0{width}d}/{total:0{width}d}]"


def _progress_message(
    current: int,
    total: int,
    subsystem: object,
    n_bits: int,
) -> str:
    return f"{_iteration_prefix(current, total)} - Procesando subsistema: {subsystem} (N={n_bits})"


def _abort_message(current: int, total: int) -> str:
    width = max(2, len(str(max(total, 1))))
    return (
        "[SISTEMA] - Ejecución abortada por el usuario en la iteración "
        f"{current:0{width}d}/{total:0{width}d}. "
        "Salvando datos parciales..."
    )


def _run_geomip_excel(
    request: PipelineRequest,
    stop_event: threading.Event,
    progress_callback=None,
) -> PipelineOutcome:
    if request.excel_path is None:
        raise ValueError("GeoMIP en modo Excel requiere una ruta de Excel.")

    request.output_path.parent.mkdir(parents=True, exist_ok=True)
    result_columns = [
        "Iteración",
        "Alcance",
        "Mecanismo",
        "Partición",
        "Phi_Efecto",
        "Phi_Causa",
        "Phi_Integrado",
        "Tiempo de ejecución (s)",
        "N",
        "Método",
    ]
    resultados: list[dict[str, Any]] = []
    stopped = False

    with _project_import_context(METHOD2_ROOT):
        from src.controllers.manager import Manager
        from src.pipeline.batch import (
            BATCH_LOGGER_TAG,
            _ejecutar_iteracion_con_timeout,
            convertir_a_binario,
            inferir_estado_inicial,
            resolver_tpm_path,
        )

        from shared_core.middlewares.slogger import SafeLogger

        logger = SafeLogger(BATCH_LOGGER_TAG)
        df = pd.read_excel(
            request.excel_path,
            sheet_name=request.sheet_index,
            usecols=request.column,
            skiprows=request.skiprows,
            names=["Subsistema"],
        )
        filas = df["Subsistema"].dropna().tolist()
        filas = filas[request.start : request.start + request.count]
        total_iterations = len(filas)

        estado_inicio = request.estado_inicio or inferir_estado_inicial()
        condiciones = request.condiciones or ("1" * len(estado_inicio))
        tpm = np.genfromtxt(resolver_tpm_path(estado_inicio), delimiter=",")
        _notify_progress(
            progress_callback,
            f"GeoMIP procesando N={len(estado_inicio)} con TPM shape={tpm.shape}.",
        )

        for display_index, fila in enumerate(filas, start=1):
            row_index = request.start + display_index
            if stop_event.is_set():
                stopped = True
                message = _abort_message(display_index, total_iterations)
                logger.info("Corte de emergencia activado por el usuario. Abortando pipeline...")
                logger.critic(message, f"iteracion_excel={row_index}")
                _notify_progress(progress_callback, message)
                break

            partes = str(fila).split("|")
            if len(partes) != 2:
                message = f"{_iteration_prefix(display_index, total_iterations)} - Fila inválida; se omite."
                logger.error(message, f"iteracion_excel={row_index}", fila)
                _notify_progress(progress_callback, message)
                continue

            message = _progress_message(display_index, total_iterations, fila, len(estado_inicio))
            logger.critic(message, f"k_max={request.default_k_max}", f"iteracion_excel={row_index}")
            _notify_progress(progress_callback, message)
            alcance = convertir_a_binario(partes[0][: len(partes[0]) - 3], n_bits=len(estado_inicio))
            mecanismo = convertir_a_binario(partes[1][: len(partes[1]) - 1], n_bits=len(estado_inicio))
            config_sistema = Manager(estado_inicial=estado_inicio)
            resultado = _ejecutar_iteracion_con_timeout(
                config_sistema=config_sistema,
                condiciones=condiciones,
                alcance=alcance,
                mecanismo=mecanismo,
                tpm=tpm,
                subsistema_id=row_index,
                timeout_seconds=request.timeout_seconds,
                k_max=request.default_k_max,
                logger=logger,
            )
            resultados.append(
                {
                    "Iteración": row_index,
                    "Alcance": alcance,
                    "Mecanismo": mecanismo,
                    "Partición": resultado["particion"],
                    "Phi_Efecto": resultado["phi_efecto"],
                    "Phi_Causa": resultado["phi_causa"],
                    "Phi_Integrado": resultado["phi_integrado"],
                    "Tiempo de ejecución (s)": resultado["tiempo"],
                    "N": len(estado_inicio),
                    "Método": "GeoMIP",
                }
            )
            pd.DataFrame(resultados, columns=result_columns).to_excel(
                request.output_path,
                index=False,
            )

    if not resultados:
        pd.DataFrame(columns=result_columns).to_excel(request.output_path, index=False)
    return PipelineOutcome(request.output_path, stopped=stopped, rows_processed=len(resultados))


def _run_geomip_single_csv(
    request: PipelineRequest,
    stop_event: threading.Event,
    progress_callback=None,
) -> PipelineOutcome:
    if request.tpm_path is None:
        raise ValueError("GeoMIP en modo CSV requiere una TPM personalizada.")

    request.output_path.parent.mkdir(parents=True, exist_ok=True)
    if stop_event.is_set():
        pd.DataFrame().to_excel(request.output_path, index=False)
        return PipelineOutcome(request.output_path, stopped=True, rows_processed=0)

    with _project_import_context(METHOD2_ROOT):
        from src.controllers.manager import Manager
        from src.controllers.strategies.k_geometric import KGeometricSIA
        from src.models.base.application import aplicacion
        from src.pipeline.batch import _separar_phi_integrado

        tpm = _read_tpm_csv(request.tpm_path)
        tpm = _prepare_tpm_for_state(tpm, request.estado_inicio)
        _notify_progress(
            progress_callback,
            f"GeoMIP procesando N={len(request.estado_inicio)} con TPM shape={tpm.shape}.",
        )
        aplicacion.set_distancia_integrada()
        config_sistema = Manager(estado_inicial=request.estado_inicio)
        solution = KGeometricSIA(config_sistema).aplicar_estrategia(
            request.condiciones,
            request.alcance,
            request.mecanismo,
            tpm=tpm,
            k_max=request.default_k_max,
        )
        phi_efecto, phi_causa, phi_integrado = _separar_phi_integrado(solution)

    result = pd.DataFrame(
        [
            {
                "Iteración": 1,
                "Estado": request.estado_inicio,
                "Condiciones": request.condiciones,
                "Alcance": request.alcance,
                "Mecanismo": request.mecanismo,
                "Partición": solution.particion,
                "Phi_Efecto": phi_efecto,
                "Phi_Causa": phi_causa,
                "Phi_Integrado": phi_integrado,
                "Tiempo de ejecución (s)": solution.tiempo_ejecucion,
                "N": len(request.estado_inicio),
                "Método": "GeoMIP",
            }
        ]
    )
    result.to_excel(request.output_path, index=False)
    return PipelineOutcome(request.output_path, stopped=stop_event.is_set(), rows_processed=len(result))


def _run_qnodes(
    request: PipelineRequest,
    stop_event: threading.Event,
    progress_callback=None,
) -> PipelineOutcome:
    request.output_path.parent.mkdir(parents=True, exist_ok=True)
    _validate_qnodes_masks(request)
    rows = _qnodes_rows(request)
    result_columns = [
        "Iteración",
        "Estado",
        "Condiciones",
        "Alcance",
        "Mecanismo",
        "Partición",
        "Phi",
        "Tiempo de ejecución (s)",
        "N",
        "Método",
    ]
    results: list[dict[str, Any]] = []
    stopped = False

    with _project_import_context(QNODES_ROOT):
        from src.controllers.manager import Manager
        from src.models.base.application import aplicacion
        from src.strategies.q_nodes import QNodes

        from shared_core.middlewares.slogger import SafeLogger

        logger = SafeLogger("qnodes_main")
        if request.profiling_enabled:
            aplicacion.activar_profiling()
        else:
            aplicacion.desactivar_profiling()
        aplicacion.set_pagina_red_muestra(request.sample_page)

        if request.tpm_path is not None:
            tpm = _read_tpm_csv(request.tpm_path)
        else:
            manager = Manager(request.estado_inicio)
            tpm = manager.cargar_red()

        tpm = _prepare_tpm_for_state(tpm, request.estado_inicio)
        audit_message = (
            f"QNodes procesando N={len(request.estado_inicio)} real, "
            f"TPM shape={tpm.shape}, estado={request.estado_inicio}, "
            f"alcance={request.alcance}, mecanismo={request.mecanismo}."
        )
        logger.critic(audit_message)
        _notify_progress(progress_callback, audit_message)

        total_iterations = len(rows)
        for display_index, (iteration, estado, condiciones, alcance, mecanismo) in enumerate(
            rows,
            start=1,
        ):
            if stop_event.is_set():
                stopped = True
                message = _abort_message(display_index, total_iterations)
                logger.info("Corte de emergencia activado por el usuario. Abortando pipeline...")
                logger.critic(message, f"iteracion={iteration}")
                _notify_progress(progress_callback, message)
                break

            subsystem = f"{alcance}_{{t+1}}|{mecanismo}_{{t}}"
            message = _progress_message(display_index, total_iterations, subsystem, len(estado))
            logger.critic(message, f"iteracion={iteration}", f"tpm_shape={tpm.shape}")
            _notify_progress(progress_callback, message)
            analyzer = QNodes(tpm, stop_event=stop_event)
            try:
                solution = analyzer.aplicar_estrategia(
                    estado,
                    condiciones,
                    alcance,
                    mecanismo,
                )
            except InterruptedError:
                stopped = True
                message = _abort_message(display_index, total_iterations)
                logger.critic(
                    message,
                    f"iteracion={iteration}",
                )
                _notify_progress(progress_callback, message)
                break
            results.append(
                {
                    "Iteración": iteration,
                    "Estado": estado,
                    "Condiciones": condiciones,
                    "Alcance": alcance,
                    "Mecanismo": mecanismo,
                    "Partición": solution.particion,
                    "Phi": solution.perdida,
                    "Tiempo de ejecución (s)": solution.tiempo_ejecucion,
                    "N": len(estado),
                    "Método": "QNodes",
                }
            )
            pd.DataFrame(results, columns=result_columns).to_csv(
                request.output_path,
                index=False,
            )

    if not results:
        pd.DataFrame(columns=result_columns).to_csv(request.output_path, index=False)
    return PipelineOutcome(request.output_path, stopped=stopped, rows_processed=len(results))


def _qnodes_rows(request: PipelineRequest) -> list[tuple[int, str, str, str, str]]:
    if request.data_source == SOURCE_CSV:
        return [
            (
                1,
                request.estado_inicio,
                request.condiciones,
                request.alcance,
                request.mecanismo,
            )
        ]

    if request.excel_path is None:
        raise ValueError("QNodes en modo Excel requiere una ruta de Excel.")

    df = pd.read_excel(
        request.excel_path,
        sheet_name=request.sheet_index,
        usecols=request.column,
        skiprows=request.skiprows,
        names=["Subsistema"],
    )
    filas = df["Subsistema"].dropna().tolist()
    filas = filas[request.start : request.start + request.count]

    rows: list[tuple[int, str, str, str, str]] = []
    for row_index, value in enumerate(filas, start=request.start + 1):
        alcance, mecanismo = _parse_subsystem_cell(value, len(request.estado_inicio))
        rows.append(
            (
                row_index,
                request.estado_inicio,
                request.condiciones,
                alcance,
                mecanismo,
            )
        )
    if not rows:
        raise ValueError("No se encontraron subsistemas válidos en el Excel.")
    return rows


def _parse_subsystem_cell(value: object, n_bits: int) -> tuple[str, str]:
    parts = str(value).split("|")
    if len(parts) != 2:
        raise ValueError(f"Fila de subsistema inválida: {value}")
    alcance = _labels_to_binary(parts[0][:-3], n_bits=n_bits)
    mecanismo = _labels_to_binary(parts[1][:-1], n_bits=n_bits)
    return alcance, mecanismo


def _labels_to_binary(text: str, n_bits: int) -> str:
    positions = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:n_bits]
    bits = ["0"] * n_bits
    for letter in str(text).upper():
        if letter in positions:
            bits[positions.index(letter)] = "1"
    return "".join(bits)


def _read_tpm_csv(path: Path) -> np.ndarray:
    tpm = np.genfromtxt(path, delimiter=",")
    if tpm.ndim != 2:
        raise ValueError("La TPM debe ser una matriz bidimensional.")
    return tpm


def _prepare_tpm_for_state(tpm: np.ndarray, estado_inicio: str) -> np.ndarray:
    n_bits = len(estado_inicio)
    expected_rows = 1 << n_bits
    if tpm.shape[0] < expected_rows or tpm.shape[1] < n_bits:
        raise ValueError(
            "La TPM cargada es menor que la dimensión solicitada: "
            f"shape={tpm.shape}, esperado mínimo=({expected_rows}, {n_bits})"
        )
    sliced = tpm[:expected_rows, :n_bits]
    _validate_tpm_against_state(sliced, estado_inicio)
    return sliced


def _validate_qnodes_masks(request: PipelineRequest) -> None:
    expected = len(request.estado_inicio)
    masks = {
        "estado_inicio": request.estado_inicio,
        "condiciones": request.condiciones,
        "alcance": request.alcance,
        "mecanismo": request.mecanismo,
    }
    for name, value in masks.items():
        if len(value) != expected:
            raise ValueError(
                f"{name} debe tener longitud N={expected}; recibido {len(value)} ({value!r})."
            )
        if set(value) - {"0", "1"}:
            raise ValueError(f"{name} solo debe contener bits 0/1; recibido {value!r}.")


def _validate_tpm_against_state(tpm: np.ndarray, estado_inicio: str) -> None:
    expected_rows = 1 << len(estado_inicio)
    if tpm.shape[1] != len(estado_inicio):
        raise ValueError(
            "La cantidad de columnas de la TPM no coincide con estado_inicio: "
            f"{tpm.shape[1]} != {len(estado_inicio)}"
        )
    if tpm.shape[0] != expected_rows:
        raise ValueError(
            "La cantidad de filas de la TPM no coincide con 2^N: "
            f"{tpm.shape[0]} != {expected_rows}"
        )


@contextlib.contextmanager
def _project_import_context(project_root: Path):
    old_cwd = Path.cwd()
    old_path = list(sys.path)
    _purge_src_modules()
    sys.path.insert(0, str(REPO_ROOT))
    sys.path.insert(0, str(project_root))
    os.chdir(project_root)
    try:
        yield
    finally:
        os.chdir(old_cwd)
        sys.path = old_path
        _purge_src_modules()


def _purge_src_modules() -> None:
    for module_name in list(sys.modules):
        if module_name == "src" or module_name.startswith("src."):
            del sys.modules[module_name]


def _safe_logger(name: str):
    try:
        from shared_core.middlewares.slogger import SafeLogger

        return SafeLogger(name)
    except (ImportError, ModuleNotFoundError, OSError, RuntimeError):
        return None


def _log_critical(logger: Any, *parts: object) -> None:
    if logger is not None:
        logger.critic(*parts)


def _log_error(logger: Any, *parts: object) -> None:
    if logger is not None:
        logger.error(*parts)


def _save_uploaded_file(uploaded_file, prefix: str) -> Path:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = Path(uploaded_file.name).name
    timestamp = int(time.time() * 1000)
    target = UPLOADS_DIR / f"{prefix}_{timestamp}_{safe_name}"
    target.write_bytes(uploaded_file.getbuffer())
    return target


def _preview_uploaded_csv(uploaded_file) -> None:
    try:
        uploaded_file.seek(0)
        preview = pd.read_csv(uploaded_file, header=None, nrows=5)
        uploaded_file.seek(0)
        st.caption("Vista previa de la TPM")
        st.dataframe(preview, use_container_width=True, hide_index=True)
    except (pd.errors.ParserError, UnicodeDecodeError, ValueError) as error:
        st.warning(f"No se pudo previsualizar el CSV: {error}")


def _log_tags_for_engine(engine: str) -> tuple[str, ...]:
    if engine == ENGINE_QNODES:
        return (APP_LOGGER_TAG, *QNODES_LOG_TAGS)
    return (APP_LOGGER_TAG, *GEOMIP_LOG_TAGS)


def _render_logs(container, tags: tuple[str, ...]) -> None:
    log_text = _collect_logs(tags)
    if not log_text:
        container.info("Aún no hay eventos de SafeLogger para esta ejecución.")
        return

    lines = log_text.splitlines()[-180:]
    rendered = "\n".join(_format_log_line(line) for line in lines)
    container.markdown(
        f"<div class='log-console'>{rendered}</div>",
        unsafe_allow_html=True,
    )


def _collect_logs(tags: tuple[str, ...]) -> str:
    chunks: list[str] = []
    logs_dir = REPO_ROOT / ".logs"
    for tag in tags:
        path = logs_dir / f"last_{tag}.log"
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if text.strip():
            chunks.append(f"--- {path.name} ---\n{text}")
    return "\n".join(chunks)


def _format_log_line(line: str) -> str:
    escaped = html.escape(line)
    if "CRITICAL" in line:
        return f"<div class='log-critical'>{escaped}</div>"
    if "ERROR" in line:
        return f"<div class='log-error'>{escaped}</div>"
    return f"<div class='log-muted'>{escaped}</div>"


def _discover_result_files() -> list[Path]:
    candidates: list[Path] = []
    for directory in (GEOMIP_RESULTS_DIR, QNODES_RESULTS_DIR, REPO_ROOT / "results"):
        if not directory.exists():
            continue
        candidates.extend(directory.glob("*.xlsx"))
        candidates.extend(directory.glob("*.csv"))
    return sorted(
        {path.resolve() for path in candidates if path.is_file()},
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _load_result_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Formato no soportado: {path.suffix}")


def _coerce_phi_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for column in df.columns:
        normalized = column.lower()
        if "phi" in normalized or column == "Phi":
            df[column] = pd.to_numeric(
                df[column].astype(str).str.replace(",", ".", regex=False),
                errors="coerce",
            )
    if "Tiempo de ejecución (s)" in df.columns:
        df["Tiempo de ejecución (s)"] = pd.to_numeric(
            df["Tiempo de ejecución (s)"].astype(str).str.replace(",", ".", regex=False),
            errors="coerce",
        )
    return df


def _phi_columns(df: pd.DataFrame) -> list[str]:
    return [
        column
        for column in df.columns
        if ("phi" in column.lower() or column == "Phi")
        and pd.api.types.is_numeric_dtype(df[column])
        and df[column].notna().any()
    ]


def _build_comparison_frame() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in _discover_result_files():
        try:
            df = _coerce_phi_columns(_load_result_table(path))
        except (OSError, ValueError, pd.errors.ParserError):
            continue
        if "Tiempo de ejecución (s)" not in df.columns:
            continue

        method = _infer_method(path, df)
        for _, row in df.dropna(subset=["Tiempo de ejecución (s)"]).iterrows():
            n_value = _infer_n(row)
            if n_value is None:
                continue
            rows.append(
                {
                    "Método": method,
                    "N": int(n_value),
                    "Tiempo de Ejecución (segundos)": float(row["Tiempo de ejecución (s)"]),
                    "Archivo": str(path.relative_to(REPO_ROOT)),
                }
            )

    if not rows:
        return pd.DataFrame()

    comparison = pd.DataFrame(rows)
    return (
        comparison.groupby(["Método", "N"], as_index=False)
        .agg({"Tiempo de Ejecución (segundos)": "mean"})
        .sort_values(["N", "Método"])
    )


def _infer_method(path: Path, df: pd.DataFrame) -> str:
    if "Método" in df.columns and df["Método"].notna().any():
        return str(df["Método"].dropna().iloc[0])
    name = path.name.lower()
    if "qnodes" in name or "q_nodes" in name:
        return "QNodes"
    return "GeoMIP"


def _infer_n(row: pd.Series) -> int | None:
    if "N" in row and pd.notna(row["N"]):
        return int(row["N"])
    for column in ("Estado", "Alcance", "Mecanismo"):
        if column in row and pd.notna(row[column]):
            value = str(row[column]).strip()
            if value and set(value) <= {"0", "1"}:
                return len(value)
    return None


if __name__ == "__main__":
    main()
