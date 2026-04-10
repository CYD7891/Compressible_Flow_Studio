from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from cfs.report.plots import plot_isentropic_area_ratio


MODEL_METADATA: dict[str, dict[str, Any]] = {
    "isentropic": {
        "label": "Isentropic Flow",
        "description": (
            "Quasi-one-dimensional ideal-gas relations referenced to stagnation properties."
        ),
        "input_fields": "gamma, M",
        "output_fields": "T/T0, P/P0, rho/rho0, A/A*",
        "columns": ["case_id", "status", "note", "T_T0", "P_P0", "rho_rho0", "A_Astar"],
        "numeric_columns": ["T_T0", "P_P0", "rho_rho0", "A_Astar"],
        "note": (
            "Processed isentropic ratios derived from the supplied Mach number and specific-heat ratio."
        ),
        "empty_message": "No isentropic cases were recorded in this run.",
    },
    "normal_shock": {
        "label": "Normal Shock",
        "description": "One-dimensional shock relations for a supersonic upstream state.",
        "input_fields": "gamma, M1",
        "output_fields": "M2, p2/p1, rho2/rho1, T2/T1, p02/p01",
        "columns": ["case_id", "status", "note", "M2", "p2_p1", "rho2_rho1", "T2_T1", "p02_p01"],
        "numeric_columns": ["M2", "p2_p1", "rho2_rho1", "T2_T1", "p02_p01"],
        "note": "Downstream state and total-pressure loss across a normal shock.",
        "empty_message": "No normal-shock cases were recorded in this run.",
    },
    "oblique_shock": {
        "label": "Oblique Shock",
        "description": "Attached oblique-shock solution for the requested weak or strong branch.",
        "input_fields": "gamma, M1, theta_deg, branch",
        "output_fields": "beta_deg, Mn1, Mn2, M2, p2/p1, rho2/rho1, T2/T1, p02/p01",
        "columns": [
            "case_id",
            "status",
            "branch",
            "note",
            "beta_deg",
            "Mn1",
            "Mn2",
            "M2",
            "p2_p1",
            "rho2_rho1",
            "T2_T1",
            "p02_p01",
        ],
        "numeric_columns": [
            "beta_deg",
            "Mn1",
            "Mn2",
            "M2",
            "p2_p1",
            "rho2_rho1",
            "T2_T1",
            "p02_p01",
        ],
        "note": (
            "Weak/strong branch results including shock angle, normal Mach components, "
            "and downstream state."
        ),
        "empty_message": "No oblique-shock cases were recorded in this run.",
    },
}


@dataclass(frozen=True)
class ReportContext:
    title: str
    subtitle: str
    author: str
    generated_on: str
    inputs_csv: str
    results_csv: str
    objective: str
    abstract: str
    summary_metrics: list[dict[str, str]]
    model_summaries: list[dict[str, Any]]
    introduction_points: list[str]
    methods_points: list[str]
    analysis_points: list[str]
    uncertainty_points: list[str]
    references: list[str]
    assumptions: list[str]
    failure_modes: list[str]
    input_columns: list[str]
    input_numeric_columns: list[str]
    result_columns: list[str]
    input_rows: list[dict[str, Any]]
    result_rows: list[dict[str, Any]]
    result_sections: list[dict[str, Any]]
    conclusions: list[str]
    figure_paths: dict[str, str]
    error_rows: list[dict[str, Any]]
    error_groups: list[dict[str, Any]]
    ok_count: int
    error_count: int


def ordered_union_keys(rows: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    columns: list[str] = []

    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                columns.append(key)

    return columns


def normalize_rows(rows: list[dict[str, Any]], columns: list[str]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        normalized.append({col: row.get(col, "") for col in columns})
    return normalized


def _safe_float(value: Any) -> float | None:
    if value in ("", None):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_value(value: float) -> str:
    return f"{value:.4f}"


def _format_range(values: list[float]) -> str | None:
    if not values:
        return None

    low = min(values)
    high = max(values)
    if abs(low - high) < 1e-12:
        return _format_value(low)
    return f"{_format_value(low)} to {_format_value(high)}"


def _numeric_values(rows: list[dict[str, Any]], column: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = _safe_float(row.get(column))
        if value is not None:
            values.append(value)
    return values


def _ok_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("status") == "OK"]


def _human_join(items: list[str]) -> str:
    if not items:
        return "no configured model families"
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _infer_numeric_columns(columns: list[str], rows: list[dict[str, Any]]) -> list[str]:
    numeric_columns: list[str] = []

    for column in columns:
        values = [row.get(column, "") for row in rows if row.get(column, "") not in ("", None)]
        if values and all(_safe_float(value) is not None for value in values):
            numeric_columns.append(column)

    return numeric_columns


def build_model_summaries(result_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []

    for model_name, meta in MODEL_METADATA.items():
        rows = [row for row in result_rows if row.get("model") == model_name]
        ok_count = sum(1 for row in rows if row.get("status") == "OK")
        error_count = sum(1 for row in rows if row.get("status") == "ERROR")
        summaries.append(
            {
                "model": model_name,
                "label": meta["label"],
                "description": meta["description"],
                "input_fields": meta["input_fields"],
                "output_fields": meta["output_fields"],
                "count": len(rows),
                "ok_count": ok_count,
                "error_count": error_count,
            }
        )

    return summaries


def build_summary_metrics(
    *,
    total_cases: int,
    ok_count: int,
    error_count: int,
    model_summaries: list[dict[str, Any]],
) -> list[dict[str, str]]:
    active_models = [summary["label"] for summary in model_summaries if summary["count"]]
    success_rate = "n/a" if total_cases == 0 else f"{(100.0 * ok_count / total_cases):.0f}%"

    return [
        {
            "label": "Input cases",
            "value": str(total_cases),
            "note": "Configured rows read from the source CSV.",
        },
        {
            "label": "Successful cases",
            "value": str(ok_count),
            "note": "Validated and computed without recorded error.",
        },
        {
            "label": "Flagged cases",
            "value": str(error_count),
            "note": "Rows retained with validation or computation issues.",
        },
        {
            "label": "Success rate",
            "value": success_rate,
            "note": _human_join(active_models).capitalize(),
        },
    ]


def build_objective(model_summaries: list[dict[str, Any]], total_cases: int) -> str:
    active_models = [summary["label"].lower() for summary in model_summaries if summary["count"]]
    if active_models:
        model_phrase = _human_join(active_models)
        return (
            f"The objective of this computational investigation was to evaluate {total_cases} configured "
            f"compressible-flow case(s) spanning {model_phrase} and to present the resulting data in a "
            "traceable, reproducible report."
        )

    return (
        f"The objective of this computational investigation was to evaluate {total_cases} configured "
        "compressible-flow case(s) and to present the resulting data in a traceable, reproducible report."
    )


def build_abstract(
    *,
    objective: str,
    inputs_csv: str,
    results_csv: str,
    ok_count: int,
    error_count: int,
    total_cases: int,
) -> str:
    findings = (
        f"{ok_count} of {total_cases} case(s) completed successfully"
        if total_cases
        else "no cases were supplied for computation"
    )
    if error_count:
        findings += f", while {error_count} case(s) were retained as explicit error records"
    findings += "."

    return (
        f"{objective} Input definitions were read from {inputs_csv} and processed by Compressible "
        f"Flow Studio into {results_csv} using deterministic ideal-gas, constant-gamma relations. "
        f"{findings} The report separates source data, processed results, interpretive discussion, "
        "and uncertainty treatment so conclusions remain tied to the governing assumptions and the "
        "quality of the supplied inputs."
    )


def build_introduction_points(
    *,
    model_summaries: list[dict[str, Any]],
    total_cases: int,
) -> list[str]:
    active_models = [summary["label"].lower() for summary in model_summaries if summary["count"]]
    model_phrase = _human_join(active_models) if active_models else "the configured case set"

    return [
        (
            f"This document records a computational investigation of {total_cases} configured case(s) "
            f"covering {model_phrase}."
        ),
        (
            "The theoretical basis is the standard ideal-gas compressible-flow framework: "
            "isentropic stagnation-property relations, normal-shock jump conditions, and attached "
            "oblique-shock relations for branch-specific wedge deflection cases."
        ),
        (
            "No explicit hypothesis, laboratory apparatus log, or measurement-uncertainty table was "
            "supplied with the input data. Accordingly, the purpose of the present report is to document "
            "the requested cases, the governing assumptions, the computed outputs, and any validation "
            "failures in a professional engineering format."
        ),
    ]


def build_methods_points(
    *,
    inputs_csv: str,
    results_csv: str,
    input_columns: list[str],
) -> list[str]:
    columns_text = ", ".join(input_columns) if input_columns else "no columns"

    return [
        (
            f"Source case definitions were read from {inputs_csv} using the columns "
            f"{columns_text}. Blank cells indicate variables that are not required for a given model."
        ),
        (
            "Each row was classified by model and validated before calculation. Missing required "
            "fields, invalid numeric values, unsupported models, and out-of-regime requests were "
            "captured as ERROR records rather than silently discarded."
        ),
        (
            f"Processed outputs were written to {results_csv}. Unless otherwise noted, reported "
            "quantities are dimensionless ratios; beta_deg and theta_deg are expressed in degrees."
        ),
        (
            "The included figure plots the isentropic area ratio A/A* as a function of Mach number "
            "for gamma = 1.4 and is provided as analytical context for interpreting the tabulated data."
        ),
    ]


def build_result_sections(result_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    table_number = 2

    for model_name in ("isentropic", "normal_shock", "oblique_shock"):
        meta = MODEL_METADATA[model_name]
        rows = [row for row in result_rows if row.get("model") == model_name]
        sections.append(
            {
                "section_id": f"results-{model_name}",
                "title": f"{meta['label']} Results",
                "caption": (
                    f"Table {table_number}. Processed {meta['label'].lower()} results. "
                    "Values are taken directly from the generated results table for traceability."
                ),
                "note": meta["note"],
                "columns": meta["columns"],
                "numeric_columns": meta["numeric_columns"],
                "rows": rows,
                "empty_message": meta["empty_message"],
            }
        )
        table_number += 1

    unsupported_rows = [
        row for row in result_rows if row.get("model") not in MODEL_METADATA
    ]
    if unsupported_rows:
        sections.append(
            {
                "section_id": "results-unsupported",
                "title": "Unsupported / Other Results",
                "caption": (
                    f"Table {table_number}. Rows that could not be matched to a supported model family."
                ),
                "note": "These records are preserved so unsupported requests remain visible in the run log.",
                "columns": ["case_id", "model", "status", "note"],
                "numeric_columns": [],
                "rows": unsupported_rows,
                "empty_message": "No unsupported model rows were recorded in this run.",
            }
        )

    return sections


def build_error_groups(error_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter((row.get("model", ""), row.get("note", "")) for row in error_rows)
    groups = [
        {"model": model or "unspecified", "note": note or "Unspecified error", "count": count}
        for (model, note), count in counts.items()
    ]
    groups.sort(key=lambda item: (-item["count"], item["model"], item["note"]))
    return groups


def build_analysis_points(
    *,
    result_rows: list[dict[str, Any]],
    error_groups: list[dict[str, Any]],
) -> list[str]:
    points: list[str] = []

    iso_rows = _ok_rows([row for row in result_rows if row.get("model") == "isentropic"])
    if iso_rows:
        tt0_range = _format_range(_numeric_values(iso_rows, "T_T0"))
        pp0_range = _format_range(_numeric_values(iso_rows, "P_P0"))
        area_range = _format_range(_numeric_values(iso_rows, "A_Astar"))
        points.append(
            "Successful isentropic cases produced "
            f"T/T0 values of {tt0_range or 'n/a'}, "
            f"P/P0 values of {pp0_range or 'n/a'}, "
            f"and A/A* values of {area_range or 'n/a'}."
        )

    ns_rows = _ok_rows([row for row in result_rows if row.get("model") == "normal_shock"])
    if ns_rows:
        m2_values = _numeric_values(ns_rows, "M2")
        p02_values = _numeric_values(ns_rows, "p02_p01")
        message = (
            "Successful normal-shock cases yielded "
            f"downstream Mach numbers of {_format_range(m2_values) or 'n/a'} "
            f"and p02/p01 values of {_format_range(p02_values) or 'n/a'}."
        )
        if p02_values and all(value < 1.0 for value in p02_values):
            message += " In every successful normal-shock case, p02/p01 remained below unity."
        points.append(message)

    os_rows = _ok_rows([row for row in result_rows if row.get("model") == "oblique_shock"])
    if os_rows:
        beta_values = _numeric_values(os_rows, "beta_deg")
        m2_values = _numeric_values(os_rows, "M2")
        p02_values = _numeric_values(os_rows, "p02_p01")
        branch_names = sorted({row.get("branch", "") for row in os_rows if row.get("branch")})
        branch_text = _human_join(branch_names) if branch_names else "configured"
        points.append(
            f"Successful oblique-shock cases on the {branch_text} branch produced beta values of "
            f"{_format_range(beta_values) or 'n/a'} deg, downstream Mach numbers of "
            f"{_format_range(m2_values) or 'n/a'}, and p02/p01 values of "
            f"{_format_range(p02_values) or 'n/a'}."
        )

    if error_groups:
        group_text = "; ".join(
            f"{group['count']} x {group['model']}: {group['note']}" for group in error_groups[:4]
        )
        points.append(
            "Validation and computation screening identified flagged rows. "
            f"The most prominent recorded causes were: {group_text}."
        )
    else:
        points.append(
            "No validation or computation failures were recorded in this run, so the full configured "
            "data set is available for interpretation."
        )

    return points


def build_uncertainty_points(error_count: int) -> list[str]:
    points = [
        (
            "This document reports deterministic solver output rather than repeated laboratory "
            "measurements; therefore no random scatter, standard deviation, or confidence interval can "
            "be estimated unless uncertainty information is provided in the input data."
        ),
        (
            "Systematic uncertainty is dominated by model-form assumptions: ideal-gas behavior, "
            "constant gamma, inviscid and adiabatic flow, quasi-one-dimensional isentropic relations, "
            "and attached-shock theory where applicable."
        ),
        (
            "Tabulated values are shown to 12 decimal places to preserve computational traceability. "
            "Displayed precision should not be interpreted as equivalent physical certainty."
        ),
    ]

    if error_count:
        points.append(
            f"{error_count} case(s) were retained as explicit ERROR records. This prevents silent "
            "data loss and makes the impact of invalid inputs or out-of-regime requests visible in the "
            "final report."
        )
    else:
        points.append(
            "No explicit ERROR rows were produced in this run; conclusions are nevertheless bounded "
            "by the governing assumptions and model validity limits."
        )

    return points


def build_conclusions(
    *,
    result_rows: list[dict[str, Any]],
    ok_count: int,
    error_count: int,
) -> list[str]:
    total_cases = len(result_rows)
    conclusions = [
        (
            f"The reporting objective was achieved for {ok_count} of {total_cases} configured case(s), "
            "with each successful computation documented in the processed-data tables."
        )
    ]

    if error_count:
        conclusions.append(
            f"{error_count} case(s) did not satisfy validation or model-applicability requirements and "
            "were excluded from technical interpretation, but they remain documented for transparency."
        )

    iso_rows = _ok_rows([row for row in result_rows if row.get("model") == "isentropic"])
    if iso_rows:
        conclusions.append(
            "The isentropic subset preserved consistent stagnation-property ratios and area-ratio output "
            "within the ranges reported in the results section."
        )

    ns_rows = _ok_rows([row for row in result_rows if row.get("model") == "normal_shock"])
    if ns_rows:
        conclusions.append(
            "The normal-shock subset showed downstream deceleration to subsonic conditions together with "
            "total-pressure loss, consistent with the governing shock relations."
        )

    os_rows = _ok_rows([row for row in result_rows if row.get("model") == "oblique_shock"])
    if os_rows:
        conclusions.append(
            "The oblique-shock subset produced branch-dependent shock angles and downstream states that "
            "remain interpretable only within the attached-shock regime represented by the model."
        )

    conclusions.append(
        "Overall validity is restricted to the ideal-gas, constant-gamma compressible-flow framework "
        "implemented by Compressible Flow Studio and should not be extended to real-gas, viscous, or "
        "detached-shock regimes without a different model."
    )

    return conclusions


def render_report_html(
    *,
    title: str,
    inputs_csv: str,
    results_csv: str,
    assumptions: list[str],
    failure_modes: list[str],
    input_rows: list[dict[str, Any]],
    result_rows: list[dict[str, Any]],
    output_dir: Path,
) -> str:
    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    tmpl = env.get_template("report.html.j2")

    input_columns = ordered_union_keys(input_rows)
    result_columns = ordered_union_keys(result_rows)

    normalized_input_rows = normalize_rows(input_rows, input_columns)
    normalized_result_rows = normalize_rows(result_rows, result_columns)

    error_rows = [row for row in normalized_result_rows if row.get("status") == "ERROR"]
    ok_count = sum(1 for row in normalized_result_rows if row.get("status") == "OK")
    error_count = len(error_rows)
    model_summaries = build_model_summaries(normalized_result_rows)
    objective = build_objective(model_summaries, len(normalized_input_rows))
    error_groups = build_error_groups(error_rows)

    assets_dir = output_dir / "assets"
    area_plot_path = assets_dir / "isentropic_area_ratio.png"
    plot_isentropic_area_ratio(area_plot_path, gamma=1.4)

    figure_paths = {
        "isentropic_area_ratio": (Path("assets") / "isentropic_area_ratio.png").as_posix()
    }

    generated_at = datetime.now().astimezone()

    ctx = ReportContext(
        title=title,
        subtitle="Structured technical report for batch compressible-flow evaluation",
        author="Compressible Flow Studio",
        generated_on=f"{generated_at.strftime('%B')} {generated_at.day}, {generated_at.year}",
        inputs_csv=inputs_csv,
        results_csv=results_csv,
        objective=objective,
        abstract=build_abstract(
            objective=objective,
            inputs_csv=inputs_csv,
            results_csv=results_csv,
            ok_count=ok_count,
            error_count=error_count,
            total_cases=len(normalized_input_rows),
        ),
        summary_metrics=build_summary_metrics(
            total_cases=len(normalized_input_rows),
            ok_count=ok_count,
            error_count=error_count,
            model_summaries=model_summaries,
        ),
        model_summaries=model_summaries,
        introduction_points=build_introduction_points(
            model_summaries=model_summaries,
            total_cases=len(normalized_input_rows),
        ),
        methods_points=build_methods_points(
            inputs_csv=inputs_csv,
            results_csv=results_csv,
            input_columns=input_columns,
        ),
        analysis_points=build_analysis_points(
            result_rows=normalized_result_rows,
            error_groups=error_groups,
        ),
        uncertainty_points=build_uncertainty_points(error_count),
        references=[
            "Anderson, J. D. Modern Compressible Flow: With Historical Perspective.",
            "NACA Report 1135. Equations, Tables, and Charts for Compressible Flow.",
            f"Compressible Flow Studio generated inputs {inputs_csv} and outputs {results_csv} for this run.",
        ],
        assumptions=assumptions,
        failure_modes=failure_modes,
        input_columns=input_columns,
        input_numeric_columns=_infer_numeric_columns(input_columns, normalized_input_rows),
        result_columns=result_columns,
        input_rows=normalized_input_rows,
        result_rows=normalized_result_rows,
        result_sections=build_result_sections(normalized_result_rows),
        conclusions=build_conclusions(
            result_rows=normalized_result_rows,
            ok_count=ok_count,
            error_count=error_count,
        ),
        figure_paths=figure_paths,
        error_rows=error_rows,
        error_groups=error_groups,
        ok_count=ok_count,
        error_count=error_count,
    )
    return tmpl.render(ctx=ctx)
