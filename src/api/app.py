from __future__ import annotations

import base64
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from src.api.routes import health
from src.services.mcdc_generator import (
    ExcelExportMetadata,
    MCDC_MODES,
    generate_mcdc_report,
    safe_excel_filename,
    testcase_table_rows_from_dict,
    write_report_artifacts,
    write_testcase_workbook_rows,
)

ManualValue = int | float | bool | str


app = FastAPI(title="c2testcase", version="0.1.0")


@app.get("/health")
def health_endpoint() -> dict[str, str]:
    return health()


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return render_index_html()


@app.post("/api/generate")
async def generate_cases(
    source: UploadFile = File(...),
    headers: list[UploadFile] | None = File(default=None),
    target_function: str = Form(default=""),
    input_variables: str = Form(default=""),
    output_variables: str = Form(default=""),
    compile_flags: str = Form(default=""),
    excel_format_version: str = Form(default="1.3"),
    excel_architecture: str = Form(default=""),
    excel_scope: str = Form(default=""),
    excel_name: str = Form(default="mcdc_testcases"),
    max_conditions: int = Form(default=12),
    mcdc_mode: str = Form(default="unique-cause"),
) -> dict[str, object]:
    if not source.filename or not source.filename.lower().endswith(".c"):
        raise HTTPException(status_code=400, detail="Upload a .c source file.")
    if max_conditions < 1 or max_conditions > 20:
        raise HTTPException(status_code=400, detail="max_conditions must be between 1 and 20.")
    if mcdc_mode not in MCDC_MODES:
        raise HTTPException(status_code=400, detail=f"mcdc_mode must be one of: {', '.join(MCDC_MODES)}.")

    with TemporaryDirectory(prefix="c2testcase-") as tmp:
        workspace = Path(tmp)
        source_path = workspace / safe_name(source.filename)
        source_path.write_bytes(await source.read())

        header_paths: list[Path] = []
        for header in headers or []:
            if not header.filename:
                continue
            if not header.filename.lower().endswith(".h"):
                raise HTTPException(status_code=400, detail=f"Header must be a .h file: {header.filename}")
            header_path = workspace / safe_name(header.filename)
            header_path.write_bytes(await header.read())
            header_paths.append(header_path)

        output_dir = workspace / "out"
        parsed_input_variables, manual_inputs = parse_variable_setup(input_variables)
        parsed_output_variables, manual_outputs = parse_variable_setup(output_variables)
        report = generate_mcdc_report(
            source_path,
            max_conditions=max_conditions,
            headers=tuple(header_paths),
            include_dirs=(workspace,),
            compile_flags=parse_compile_flags(compile_flags),
            target_function=target_function.strip() or None,
            input_variables=parsed_input_variables,
            manual_inputs=manual_inputs,
            output_variables=parsed_output_variables,
            manual_outputs=manual_outputs,
            mcdc_mode=mcdc_mode,
        )
        excel_metadata = ExcelExportMetadata(
            format_version=excel_format_version.strip() or "1.3",
            architecture=excel_architecture.strip(),
            scope=excel_scope.strip(),
            name=excel_name.strip() or "mcdc_testcases",
        )
        json_path, harness_path, gap_report_path, excel_path = write_report_artifacts(
            report,
            output_dir,
            excel_metadata=excel_metadata,
        )

        return {
            "report": report.to_dict(),
            "artifacts": {
                "mcdc_cases.json": json_path.read_text(encoding="utf-8"),
                "generated_mcdc_tests.c": harness_path.read_text(encoding="utf-8"),
                "gap_report.md": gap_report_path.read_text(encoding="utf-8"),
            },
            "downloads": {
                excel_path.name: base64.b64encode(excel_path.read_bytes()).decode("ascii"),
            },
            "excel_filename": excel_path.name,
        }


@app.post("/api/export-excel")
async def export_excel(payload: dict[str, object] = Body(...)) -> dict[str, str]:
    report = payload.get("report")
    if not isinstance(report, dict):
        raise HTTPException(status_code=400, detail="report is required.")
    metadata = ExcelExportMetadata(
        format_version=str(payload.get("format_version") or "1.3").strip() or "1.3",
        architecture=str(payload.get("architecture") or "").strip(),
        scope=str(payload.get("scope") or "").strip(),
        name=str(payload.get("name") or "mcdc_testcases").strip() or "mcdc_testcases",
    )
    fill_manual_for_btc = bool(payload.get("fill_manual_for_btc"))
    with TemporaryDirectory(prefix="c2testcase-export-") as tmp:
        output_dir = Path(tmp)
        excel_path = output_dir / f"{safe_excel_filename(metadata.name)}.xlsx"
        write_testcase_workbook_rows(
            testcase_table_rows_from_dict(report, fill_manual_for_btc=fill_manual_for_btc),
            excel_path,
            metadata,
        )
        return {
            "filename": excel_path.name,
            "download": base64.b64encode(excel_path.read_bytes()).decode("ascii"),
        }


def parse_compile_flags(raw_flags: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw_flags.replace("\n", " ").split(" ") if part.strip())


def parse_variable_setup(raw_variables: str) -> tuple[tuple[str, ...], dict[str, ManualValue]]:
    variables: list[str] = []
    defaults: dict[str, ManualValue] = {}
    for raw_part in raw_variables.replace("\n", ",").split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "=" in part:
            name, value = part.split("=", 1)
            name = name.strip()
            if name:
                variables.append(name)
                defaults[name] = parse_manual_input_value(value.strip())
            continue
        variables.append(part)
    return tuple(dict.fromkeys(variables)), defaults


parse_input_variables = parse_variable_setup


def parse_manual_input_value(value: str) -> ManualValue:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if value.lstrip("-").isdigit():
        return int(value)
    try:
        return float(value)
    except ValueError:
        pass
    return value


def safe_name(filename: str) -> str:
    return Path(filename).name.replace("/", "_").replace("\\", "_")


def render_index_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>c2testcase</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #1d2433;
      --muted: #5d6678;
      --line: #d9dee8;
      --panel: #ffffff;
      --surface: #f4f7fb;
      --accent: #0f766e;
      --accent-strong: #115e59;
      --warn: #9a3412;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background: var(--surface);
      font-family: Arial, Helvetica, sans-serif;
      font-size: 15px;
      letter-spacing: 0;
    }
    header {
      background: #263241;
      color: white;
      padding: 18px 24px;
      border-bottom: 4px solid var(--accent);
    }
    header h1 {
      margin: 0;
      font-size: 22px;
      font-weight: 700;
      letter-spacing: 0;
    }
    main {
      display: grid;
      grid-template-columns: minmax(280px, 390px) minmax(0, 1fr);
      min-height: calc(100vh - 66px);
    }
    aside, section {
      padding: 20px;
    }
    aside {
      background: var(--panel);
      border-right: 1px solid var(--line);
    }
    label {
      display: block;
      margin: 14px 0 6px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }
    input, textarea, select, button {
      width: 100%;
      font: inherit;
    }
    input[type="file"], input[type="text"], input[type="number"], textarea, select {
      border: 1px solid var(--line);
      background: white;
      color: var(--ink);
      padding: 9px 10px;
      border-radius: 6px;
    }
    textarea {
      resize: vertical;
      min-height: 74px;
    }
    button {
      margin-top: 16px;
      border: 0;
      background: var(--accent);
      color: white;
      padding: 10px 12px;
      border-radius: 6px;
      font-weight: 700;
      cursor: pointer;
    }
    button:hover { background: var(--accent-strong); }
    button:disabled { opacity: .62; cursor: wait; }
    .summary {
      display: grid;
      grid-template-columns: repeat(5, minmax(120px, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }
    .metric {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 12px;
      min-height: 74px;
    }
    .metric span {
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      margin-bottom: 8px;
    }
    .metric strong {
      display: block;
      font-size: 22px;
      overflow-wrap: anywhere;
    }
    .tabs {
      display: flex;
      gap: 6px;
      margin: 10px 0;
      flex-wrap: wrap;
    }
    .tab {
      width: auto;
      margin: 0;
      background: #e8edf5;
      color: var(--ink);
      padding: 8px 10px;
      border: 1px solid var(--line);
    }
    .tab.active {
      background: #263241;
      color: white;
      border-color: #263241;
    }
    .report-tools {
      display: flex;
      gap: 8px;
      margin: 0 0 10px;
      flex-wrap: wrap;
    }
    .btc-toggle {
      width: auto;
      margin: 0;
      background: #e8edf5;
      color: var(--ink);
      padding: 8px 10px;
      border: 1px solid var(--line);
    }
    .btc-toggle.active {
      background: #99ccff;
      color: #1f2937;
      border-color: #6699cc;
    }
    .btc-toggle:hover {
      background: #d7e2f2;
    }
    .btc-toggle.active:hover {
      background: #7fb5e8;
    }
    pre {
      margin: 0;
      min-height: 420px;
      max-height: calc(100vh - 240px);
      overflow: auto;
      background: #111827;
      color: #e5e7eb;
      border-radius: 6px;
      padding: 14px;
      line-height: 1.45;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    .table-wrap {
      display: none;
      min-height: 420px;
      max-height: calc(100vh - 240px);
      overflow: auto;
      background: white;
      border: 1px solid var(--line);
      border-radius: 6px;
    }
    .export-panel {
      display: none;
      min-height: 420px;
      max-height: calc(100vh - 240px);
      overflow: auto;
      background: white;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 18px;
    }
    .export-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(180px, 1fr));
      gap: 0 14px;
      max-width: 860px;
    }
    .export-note {
      margin: 0 0 14px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }
    .export-action {
      width: auto;
      min-width: 150px;
      background: #99ccff;
      color: #1f2937;
      border: 1px solid #6699cc;
    }
    .export-action:hover {
      background: #7fb5e8;
    }
    .export-status {
      margin-top: 12px;
      min-height: 20px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }
    .ccode-wrap {
      display: none;
      height: calc(100vh - 240px);
      min-height: 420px;
      overflow: hidden;
      background: white;
      border: 1px solid var(--line);
      border-radius: 6px;
    }
    .ccode-grid {
      display: grid;
      grid-template-columns: minmax(460px, 1.25fr) minmax(320px, .75fr);
      height: 100%;
      min-height: 0;
    }
    .code-pane {
      overflow: auto;
      border-right: 1px solid var(--line);
      background: #f9fbfe;
      font-family: Consolas, "Courier New", monospace;
      font-size: 13px;
      line-height: 1.5;
      min-height: 0;
    }
    .code-line {
      display: grid;
      grid-template-columns: 54px minmax(0, 1fr) auto;
      gap: 10px;
      padding: 2px 10px 2px 0;
      border-left: 4px solid transparent;
      white-space: pre;
    }
    .code-line.covered {
      background: #ecfdf5;
      border-left-color: var(--accent);
      cursor: pointer;
    }
    .code-line.active {
      background: #d9f99d;
      border-left-color: #4d7c0f;
    }
    .line-no {
      color: var(--muted);
      text-align: right;
      user-select: none;
    }
    .line-hit {
      color: var(--accent-strong);
      font-family: Arial, Helvetica, sans-serif;
      font-size: 12px;
      font-weight: 700;
    }
    .source-code {
      overflow-wrap: normal;
    }
    .decision-pane {
      padding: 14px;
      overflow: auto;
      background: white;
      min-height: 0;
    }
    .decision-title {
      margin: 0 0 8px;
      font-size: 16px;
    }
    .decision-meta {
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 12px;
    }
    .case-card {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      margin-bottom: 10px;
      background: #ffffff;
    }
    .case-card strong {
      display: block;
      margin-bottom: 6px;
    }
    .case-detail {
      margin: 4px 0;
      color: var(--ink);
      font-size: 13px;
      line-height: 1.4;
      overflow-wrap: anywhere;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 860px;
      background: white;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      border-right: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
      white-space: nowrap;
    }
    th {
      position: sticky;
      top: 0;
      background: #263241;
      color: white;
      font-size: 12px;
      z-index: 1;
    }
    td.notes, td.truths {
      white-space: normal;
      min-width: 220px;
    }
    .error {
      color: var(--warn);
      font-weight: 700;
      margin-top: 12px;
      min-height: 20px;
    }
    .empty {
      border: 1px dashed var(--line);
      background: white;
      border-radius: 6px;
      padding: 18px;
      color: var(--muted);
    }
    @media (max-width: 820px) {
      main { grid-template-columns: 1fr; }
      aside { border-right: 0; border-bottom: 1px solid var(--line); }
      .summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      pre { max-height: 520px; }
      .table-wrap { max-height: 520px; }
      .export-panel { max-height: 520px; }
      .export-grid { grid-template-columns: 1fr; }
      .ccode-wrap { height: 520px; max-height: 520px; }
      .ccode-grid { grid-template-columns: 1fr; }
      .code-pane { border-right: 0; border-bottom: 1px solid var(--line); min-height: 240px; }
      .decision-pane { min-height: 260px; }
    }
  </style>
</head>
<body>
  <header><h1>c2testcase</h1></header>
  <main>
    <aside>
      <form id="generate-form">
        <label for="source">C source</label>
        <input id="source" name="source" type="file" accept=".c" required>
        <label for="headers">Headers</label>
        <input id="headers" name="headers" type="file" accept=".h" multiple>
        <label for="target_function">Target function</label>
        <input id="target_function" name="target_function" type="text" placeholder="logic">
        <label for="input_variables">Manual input setup</label>
        <input id="input_variables" name="input_variables" type="text" placeholder="a, b, IN_gear=D, IN_ignition=1">
        <label for="output_variables">Manual output setup</label>
        <input id="output_variables" name="output_variables" type="text" placeholder="VF24blatgfd_s=-24.5, VS15lat_grev=-2.5">
        <label for="compile_flags">Compile flags</label>
        <textarea id="compile_flags" name="compile_flags" placeholder="-DUNIT_TEST"></textarea>
        <label for="max_conditions">Max conditions</label>
        <input id="max_conditions" name="max_conditions" type="number" min="1" max="20" value="12">
        <label for="mcdc_mode">MC/DC mode</label>
        <select id="mcdc_mode" name="mcdc_mode">
          <option value="unique-cause">Unique-Cause</option>
          <option value="masking">Masking</option>
          <option value="multicondition">Multicondition</option>
        </select>
        <button id="submit" type="submit">Generate MC/DC cases</button>
        <div id="error" class="error"></div>
      </form>
    </aside>
    <section>
      <div class="summary">
        <div class="metric"><span>Score</span><strong id="score">-</strong></div>
        <div class="metric"><span>Decisions</span><strong id="decisions">-</strong></div>
        <div class="metric"><span>Cases</span><strong id="cases">-</strong></div>
        <div class="metric"><span>Mode</span><strong id="mode">-</strong></div>
        <div class="metric"><span>Coverage Ready</span><strong id="coverage">-</strong></div>
      </div>
      <div class="tabs">
        <button class="tab active" type="button" data-artifact="gap_report.md">Gap report</button>
        <button class="tab" type="button" data-artifact="mcdc_cases.json">JSON</button>
        <button class="tab" type="button" data-artifact="generated_mcdc_tests.c">Harness</button>
        <button class="tab" type="button" data-view="testcase_table">Testcase_table</button>
        <button class="tab" type="button" data-download="excel">Export Excel</button>
        <button class="tab" type="button" data-view="ccode_interface">Ccode_interface</button>
      </div>
      <div class="report-tools">
        <button id="btc_fill_toggle" class="btc-toggle" type="button" aria-pressed="false">BTC fill MANUAL: off</button>
      </div>
      <pre id="artifact">Upload a C source file to generate cases.</pre>
      <div id="testcase-table" class="table-wrap"></div>
      <div id="excel-export-panel" class="export-panel">
        <p class="export-note">Note: this export gets data from Testcase_table.</p>
        <div class="export-grid">
          <div>
            <label for="excel_format_version">Excel Format Version</label>
            <input id="excel_format_version" type="text">
          </div>
          <div>
            <label for="excel_architecture">Excel Architecture</label>
            <input id="excel_architecture" type="text">
          </div>
          <div>
            <label for="excel_scope">Excel Scope</label>
            <input id="excel_scope" type="text">
          </div>
          <div>
            <label for="excel_name">Excel Name</label>
            <input id="excel_name" type="text">
          </div>
        </div>
        <button id="excel_export_submit" class="export-action" type="button">Export</button>
        <div id="excel_export_status" class="export-status"></div>
      </div>
      <div id="ccode-interface" class="ccode-wrap"></div>
    </section>
  </main>
  <script>
    const form = document.getElementById("generate-form");
    const submit = document.getElementById("submit");
    const error = document.getElementById("error");
    const artifact = document.getElementById("artifact");
    const testcaseTable = document.getElementById("testcase-table");
    const excelExportPanel = document.getElementById("excel-export-panel");
    const excelExportSubmit = document.getElementById("excel_export_submit");
    const excelExportStatus = document.getElementById("excel_export_status");
    const btcFillToggle = document.getElementById("btc_fill_toggle");
    const ccodeInterface = document.getElementById("ccode-interface");
    const state = {
      artifacts: {},
      downloads: {},
      excelFilename: "mcdc_testcases.xlsx",
      report: null,
      active: "gap_report.md",
      btcFillManual: false,
    };

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      error.textContent = "";
      submit.disabled = true;
      artifact.textContent = "Running...";
      try {
        const body = new FormData(form);
        const response = await fetch("/api/generate", { method: "POST", body });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || "Generation failed");
        state.artifacts = payload.artifacts;
        state.downloads = payload.downloads || {};
        state.excelFilename = payload.excel_filename || "mcdc_testcases.xlsx";
        state.report = payload.report;
        renderSummary(payload.report);
        if (state.active === "testcase_table") {
          renderTestcaseTable();
        } else if (state.active === "excel_export") {
          renderExcelExportPanel();
        } else if (state.active === "ccode_interface") {
          renderCcodeInterface();
        } else {
          renderArtifact(state.active);
        }
      } catch (err) {
        error.textContent = err.message;
        artifact.textContent = "";
      } finally {
        submit.disabled = false;
      }
    });

    document.querySelectorAll(".tab").forEach((button) => {
      button.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach((tab) => tab.classList.remove("active"));
        button.classList.add("active");
        if (button.dataset.download === "excel") {
          state.active = "excel_export";
          renderExcelExportPanel();
        } else if (button.dataset.view === "testcase_table") {
          state.active = "testcase_table";
          renderTestcaseTable();
        } else if (button.dataset.view === "ccode_interface") {
          state.active = "ccode_interface";
          renderCcodeInterface();
        } else {
          state.active = button.dataset.artifact;
          renderArtifact(state.active);
        }
      });
    });

    excelExportSubmit.addEventListener("click", exportExcel);
    btcFillToggle.addEventListener("click", () => {
      state.btcFillManual = !state.btcFillManual;
      renderBtcFillToggle();
      if (state.active === "testcase_table") {
        renderTestcaseTable();
      } else if (state.active === "excel_export") {
        renderExcelExportPanel();
      } else if (state.active === "ccode_interface") {
        renderCcodeInterface();
      }
    });
    renderBtcFillToggle();

    function renderBtcFillToggle() {
      btcFillToggle.classList.toggle("active", state.btcFillManual);
      btcFillToggle.setAttribute("aria-pressed", String(state.btcFillManual));
      btcFillToggle.textContent = state.btcFillManual ? "BTC fill MANUAL: on" : "BTC fill MANUAL: off";
    }

    function renderSummary(report) {
      const decisions = report.decisions || [];
      const targetRows = report.testcase_table?.target_rows ?? report.testcase_table?.rows?.length
        ?? decisions.reduce((total, decision) => total + decision.cases.length, 0);
      const concreteRows = report.testcase_table?.concrete_rows;
      document.getElementById("score").textContent = `${Math.round((report.score || 0) * 100)}%`;
      document.getElementById("decisions").textContent = decisions.length;
      document.getElementById("cases").textContent = concreteRows == null || concreteRows === targetRows
        ? targetRows
        : `${targetRows} targets / ${concreteRows} concrete`;
      document.getElementById("mode").textContent = report.mcdc_mode || "-";
      document.getElementById("coverage").textContent = report.coverage_ready ? "yes" : "no";
    }

    function renderArtifact(name) {
      artifact.style.display = "block";
      testcaseTable.style.display = "none";
      excelExportPanel.style.display = "none";
      ccodeInterface.style.display = "none";
      artifact.textContent = state.artifacts[name] || "No artifact generated yet.";
    }

    function renderTestcaseTable() {
      artifact.style.display = "none";
      testcaseTable.style.display = "block";
      excelExportPanel.style.display = "none";
      ccodeInterface.style.display = "none";
      testcaseTable.replaceChildren();
      if (!state.report) {
        testcaseTable.append(emptyNode("No generated testcases yet."));
        return;
      }
      const rows = testcaseRows(state.report);
      if (rows.length === 0) {
        testcaseTable.append(emptyNode("No generated testcases."));
        return;
      }
      const variables = state.report.testcase_table?.input_columns?.length
        ? state.report.testcase_table.input_columns
        : [...new Set([...(state.report.input_variables || []), ...[...new Set(rows.flatMap((row) => Object.keys(row.inputs || {})))].sort()])];
      const variableKeys = state.report.testcase_table?.input_column_keys?.length
        ? state.report.testcase_table.input_column_keys
        : variables;
      const parameterVariables = state.report.testcase_table?.parameter_columns || [];
      const parameterKeys = state.report.testcase_table?.parameter_column_keys?.length
        ? state.report.testcase_table.parameter_column_keys
        : parameterVariables;
      const outputVariables = state.report.testcase_table?.output_columns?.length
        ? state.report.testcase_table.output_columns
        : (state.report.output_variables || []).length
        ? state.report.output_variables
        : ["Decision_Result"];
      const outputKeys = state.report.testcase_table?.output_column_keys?.length
        ? state.report.testcase_table.output_column_keys
        : outputVariables;
      const btcFallbacks = manualValueFallbacks(rows, variableKeys, parameterKeys, outputKeys);
      rows.sort((left, right) => compareTestcaseRows(left, right, variableKeys));
      const headers = [
        "Step",
        "Setup",
        ...variables,
        ...parameterVariables,
        ...outputVariables,
      ];
      const table = document.createElement("table");
      const thead = table.createTHead();
      const groupRow = thead.insertRow();
      [
        "Mode",
        "Setup",
        ...variables.map(() => "Inputs"),
        ...parameterVariables.map(() => "Parameters"),
        ...outputVariables.map(() => "Outputs"),
      ].forEach((label) => {
        const th = document.createElement("th");
        th.textContent = label;
        groupRow.append(th);
      });
      const headerRow = thead.insertRow();
      headers.forEach((label) => {
        const th = document.createElement("th");
        th.textContent = label;
        headerRow.append(th);
      });
      const tbody = table.createTBody();
      rows.forEach((row, index) => {
        const tr = tbody.insertRow();
        const assignments = variableKeys.map((key) =>
          btcCellValue(row.inputs?.[key] ?? state.report.manual_inputs?.[key] ?? "MANUAL", btcFallbacks.inputs[key])
        );
        const parameters = parameterKeys.map((key) =>
          btcCellValue(row.parameters?.[key] ?? "MANUAL", btcFallbacks.parameters[key])
        );
        const outputs = outputKeys.map((key, index) =>
          btcCellValue(
            row.outputs?.[key] ?? (outputVariables[index] === "Decision_Result" ? row.decisionResult : state.report.manual_outputs?.[key] ?? "MANUAL"),
            btcFallbacks.outputs[key]
          )
        );
        const values = [
          index,
          setupLabel(row.setupStatus),
          ...assignments,
          ...parameters,
          ...outputs,
        ];
        values.forEach((value, columnIndex) => {
          const td = tr.insertCell();
          td.textContent = String(value);
        });
      });
      testcaseTable.append(table);
    }

    function renderExcelExportPanel() {
      artifact.style.display = "none";
      testcaseTable.style.display = "none";
      excelExportPanel.style.display = "block";
      ccodeInterface.style.display = "none";
      excelExportSubmit.disabled = !state.report;
      excelExportStatus.textContent = state.report
        ? (state.btcFillManual ? "BTC fill is on: MANUAL cells export as per-column minimal values or 0." : "")
        : "Generate cases before exporting Excel.";
    }

    function renderCcodeInterface() {
      artifact.style.display = "none";
      testcaseTable.style.display = "none";
      excelExportPanel.style.display = "none";
      ccodeInterface.style.display = "block";
      ccodeInterface.replaceChildren();
      if (!state.report) {
        ccodeInterface.append(emptyNode("No C source loaded yet."));
        return;
      }
      const lines = (state.report.source_text || "").split(/\\r?\\n/);
      if (!lines.length || (lines.length === 1 && lines[0] === "")) {
        ccodeInterface.append(emptyNode("No C source text available in this report."));
        return;
      }
      const decisionsByLine = new Map();
      (state.report.decisions || []).forEach((decision) => {
        const existing = decisionsByLine.get(decision.line) || [];
        existing.push(decision);
        decisionsByLine.set(decision.line, existing);
      });
      const rowsByDecision = new Map();
      testcaseRows(state.report).forEach((row) => {
        const existing = rowsByDecision.get(row.decisionId) || [];
        existing.push(row);
        rowsByDecision.set(row.decisionId, existing);
      });

      const grid = document.createElement("div");
      grid.className = "ccode-grid";
      const codePane = document.createElement("div");
      codePane.className = "code-pane";
      const decisionPane = document.createElement("div");
      decisionPane.className = "decision-pane";
      grid.append(codePane, decisionPane);
      ccodeInterface.append(grid);

      const showLine = (lineNumber) => {
        codePane.querySelectorAll(".code-line").forEach((node) => node.classList.remove("active"));
        const active = codePane.querySelector(`[data-line="${lineNumber}"]`);
        if (active) active.classList.add("active");
        decisionPane.replaceChildren();
        const decisions = decisionsByLine.get(lineNumber) || [];
        if (!decisions.length) {
          decisionPane.append(emptyNode("Select a highlighted decision line to inspect generated testcases."));
          return;
        }
        decisions.forEach((decision) => {
          decisionPane.append(renderDecisionDetail(decision, rowsByDecision.get(decision.id) || []));
        });
      };

      lines.forEach((text, index) => {
        const lineNumber = index + 1;
        const decisions = decisionsByLine.get(lineNumber) || [];
        const line = document.createElement("div");
        line.className = `code-line${decisions.length ? " covered" : ""}`;
        line.dataset.line = String(lineNumber);
        const number = document.createElement("span");
        number.className = "line-no";
        number.textContent = String(lineNumber);
        const code = document.createElement("span");
        code.className = "source-code";
        code.textContent = text || " ";
        const hit = document.createElement("span");
        hit.className = "line-hit";
        const testcaseCount = decisions.reduce((total, decision) => total + (rowsByDecision.get(decision.id) || []).length, 0);
        hit.textContent = testcaseCount ? `${testcaseCount} cases` : "";
        line.append(number, code, hit);
        if (decisions.length) {
          line.addEventListener("click", () => showLine(lineNumber));
        }
        codePane.append(line);
      });
      const firstDecisionLine = [...decisionsByLine.keys()][0];
      showLine(firstDecisionLine || 0);
    }

    function renderDecisionDetail(decision, rows) {
      const fragment = document.createDocumentFragment();
      const title = document.createElement("h2");
      title.className = "decision-title";
      title.textContent = `${decision.id} line ${decision.line}`;
      const meta = document.createElement("div");
      meta.className = "decision-meta";
      meta.textContent = `${Math.round((decision.score || 0) * 100)}% generated MC/DC, ${rows.length} testcase steps`;
      const expression = document.createElement("div");
      expression.className = "case-detail";
      expression.textContent = `Decision: ${decision.expression}`;
      fragment.append(title, meta, expression);

      rows.forEach((row) => {
        const card = document.createElement("div");
        card.className = "case-card";
        const heading = document.createElement("strong");
        heading.textContent = `Step ${row.step}: ${row.decisionResult ? "decision true" : "decision false"}`;
        card.append(heading);
        card.append(detailLine(`Setup: ${setupLabel(row.setupStatus)}`));
        card.append(detailLine(`Reason: ${formatReason(decision, row)}`));
        card.append(detailLine(`Inputs: ${formatMap(row.inputs)}`));
        card.append(detailLine(`Parameters: ${formatMap(row.parameters)}`));
        card.append(detailLine(`Outputs: ${formatMap(row.outputs)}`));
        card.append(detailLine(`Condition values: ${formatConditionValues(decision, row)}`));
        graphTraceDetails(decision, row).forEach((line) => card.append(detailLine(line)));
        if (row.setupNotes?.length) {
          card.append(detailLine(`Setup notes: ${row.setupNotes.join("; ")}`));
        }
        if (row.notes?.length) {
          card.append(detailLine(`Notes: ${row.notes.join("; ")}`));
        }
        fragment.append(card);
      });
      if (!rows.length) {
        fragment.append(emptyNode("No generated testcase rows cover this decision line."));
      }
      return fragment;
    }

    function detailLine(text) {
      const node = document.createElement("div");
      node.className = "case-detail";
      node.textContent = text;
      return node;
    }

    function formatReason(decision, row) {
      if (!row.covers?.length) {
        return "selected as a generated decision row; no independent condition coverage was attributed";
      }
      return row.covers
        .map((index) => `covers condition ${index} (${decision.conditions?.[index] || "unknown"})`)
        .join("; ");
    }

    function formatMap(values) {
      const entries = Object.entries(values || {});
      if (!entries.length) return "none";
      return entries.map(([name, value]) => `${name}=${value}`).join(", ");
    }

    function manualValueFallbacks(rows, inputColumns, parameterColumns, outputColumns) {
      const fallbacks = {
        inputs: Object.fromEntries(inputColumns.map((name) => [name, 0])),
        parameters: Object.fromEntries(parameterColumns.map((name) => [name, 0])),
        outputs: Object.fromEntries(outputColumns.map((name) => [name, 0])),
      };
      const collected = {
        inputs: Object.fromEntries(inputColumns.map((name) => [name, []])),
        parameters: Object.fromEntries(parameterColumns.map((name) => [name, []])),
        outputs: Object.fromEntries(outputColumns.map((name) => [name, []])),
      };
      rows.forEach((row) => {
        inputColumns.forEach((name) => {
          const value = numericBtcValue(row.inputs?.[name] ?? state.report.manual_inputs?.[name]);
          if (value !== null) collected.inputs[name].push(value);
        });
        parameterColumns.forEach((name) => {
          const value = numericBtcValue(row.parameters?.[name]);
          if (value !== null) collected.parameters[name].push(value);
        });
        outputColumns.forEach((name) => {
          const value = numericBtcValue(
            row.outputs?.[name] ?? (name === "Decision_Result" ? row.decisionResult : state.report.manual_outputs?.[name])
          );
          if (value !== null) collected.outputs[name].push(value);
        });
      });
      inputColumns.forEach((name) => {
        if (collected.inputs[name].length) fallbacks.inputs[name] = Math.min(...collected.inputs[name]);
      });
      parameterColumns.forEach((name) => {
        if (collected.parameters[name].length) fallbacks.parameters[name] = Math.min(...collected.parameters[name]);
      });
      outputColumns.forEach((name) => {
        if (collected.outputs[name].length) fallbacks.outputs[name] = Math.min(...collected.outputs[name]);
      });
      return fallbacks;
    }

    function btcCellValue(value, fallback) {
      if (state.btcFillManual && value === "MANUAL") return fallback ?? 0;
      return value;
    }

    function numericBtcValue(value) {
      if (value === "MANUAL" || value === undefined || value === null || value === "") return null;
      if (value === true) return 1;
      if (value === false) return 0;
      if (typeof value === "number" && Number.isFinite(value)) return value;
      if (typeof value === "string") {
        const parsed = Number(value.trim());
        return Number.isFinite(parsed) ? parsed : null;
      }
      return null;
    }

    function setupLabel(status) {
      if (status === "manual_required") return "manual required";
      if (status === "partial") return "partial";
      return "concrete";
    }

    function formatConditionValues(decision, row) {
      return (decision.conditions || [])
        .map((condition, index) => `${condition}=${row.values?.[index]}`)
        .join(", ");
    }

    function graphTraceDetails(decision, row) {
      const graph = state.report?.interface_graph?.condition_traces || {};
      return (row.covers || [])
        .map((index) => {
          const trace = graph[`${decision.id}:${index}`];
          if (!trace) return "";
          const roots = (trace.roots || []).join(", ") || "none";
          const chain = (trace.chain || []).join(" -> ") || "none";
          const outputs = trace.output_roots?.length ? `; output roots: ${trace.output_roots.join(", ")}` : "";
          const value = row.values?.[index];
          return `Graph trace: root input ${roots}; chain ${chain}; testcase value ${value}${outputs}`;
        })
        .filter(Boolean);
    }

    function testcaseRows(report) {
      if (report.testcase_table?.rows) {
        return report.testcase_table.rows.map((row) => ({
          decisionId: row.decision_id,
          line: row.line,
          decisionResult: row.decision_result,
          covers: row.covers || [],
          values: row.mcdc_condition_values || [],
          inputs: row.inputs || {},
          parameters: row.parameters || {},
          outputs: row.outputs || {},
          setupStatus: row.setup_status || "concrete",
          setupNotes: row.setup_notes || [],
          notes: row.notes || [],
        }));
      }
      return (report.decisions || []).flatMap((decision) =>
        (decision.cases || []).map((row) => ({
          decisionId: decision.id,
          line: decision.line,
          decisionResult: row.decision_result,
          covers: row.covers || [],
          values: row.values || [],
          inputs: row.assignments || {},
          parameters: {},
          outputs: {},
          setupStatus: row.assignments && Object.keys(row.assignments).length ? "concrete" : "manual_required",
          setupNotes: row.notes || [],
          notes: row.notes || [],
        }))
      );
    }

    function compareTestcaseRows(left, right, variables) {
      if (left.decisionResult !== right.decisionResult) {
        return left.decisionResult ? -1 : 1;
      }
      for (const variable of variables) {
        const leftValue = String(left.inputs?.[variable] ?? "");
        const rightValue = String(right.inputs?.[variable] ?? "");
        const compared = leftValue.localeCompare(rightValue, undefined, { numeric: true });
        if (compared !== 0) return compared;
      }
      return 0;
    }

    function emptyNode(text) {
      const node = document.createElement("div");
      node.className = "empty";
      node.textContent = text;
      return node;
    }

    async function downloadArtifact(name) {
      if (name === "excel") {
        await exportExcel();
        return;
      }
      const filename = name;
      const encoded = state.downloads[filename];
      if (!encoded) {
        artifact.style.display = "block";
        testcaseTable.style.display = "none";
        excelExportPanel.style.display = "none";
        ccodeInterface.style.display = "none";
        artifact.textContent = "Generate cases before downloading Excel.";
        return;
      }
      const bytes = Uint8Array.from(atob(encoded), (char) => char.charCodeAt(0));
      const blob = new Blob([bytes], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      link.click();
      URL.revokeObjectURL(link.href);
      artifact.textContent = `Downloaded ${filename}.`;
    }

    async function exportExcel() {
      if (!state.report) {
        artifact.style.display = "block";
        testcaseTable.style.display = "none";
        excelExportPanel.style.display = "none";
        ccodeInterface.style.display = "none";
        artifact.textContent = "Generate cases before exporting Excel.";
        return;
      }
      const response = await fetch("/api/export-excel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          report: state.report,
          format_version: document.getElementById("excel_format_version").value,
          architecture: document.getElementById("excel_architecture").value,
          scope: document.getElementById("excel_scope").value,
          name: document.getElementById("excel_name").value,
          fill_manual_for_btc: state.btcFillManual,
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        artifact.style.display = "block";
        testcaseTable.style.display = "none";
        excelExportPanel.style.display = "none";
        ccodeInterface.style.display = "none";
        artifact.textContent = payload.detail || "Excel export failed.";
        return;
      }
      state.excelFilename = payload.filename;
      state.downloads[payload.filename] = payload.download;
      const bytes = Uint8Array.from(atob(payload.download), (char) => char.charCodeAt(0));
      const blob = new Blob([bytes], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = payload.filename;
      link.click();
      URL.revokeObjectURL(link.href);
      excelExportStatus.textContent = `Downloaded ${payload.filename}.`;
    }
  </script>
</body>
</html>"""
