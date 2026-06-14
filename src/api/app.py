from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from src.api.routes import health
from src.services.mcdc_generator import MCDC_MODES, generate_mcdc_report, write_report_artifacts


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
    compile_flags: str = Form(default=""),
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
        report = generate_mcdc_report(
            source_path,
            max_conditions=max_conditions,
            headers=tuple(header_paths),
            include_dirs=(workspace,),
            compile_flags=parse_compile_flags(compile_flags),
            target_function=target_function.strip() or None,
            mcdc_mode=mcdc_mode,
        )
        json_path, harness_path, gap_report_path = write_report_artifacts(report, output_dir)

        return {
            "report": report.to_dict(),
            "artifacts": {
                "mcdc_cases.json": json_path.read_text(encoding="utf-8"),
                "generated_mcdc_tests.c": harness_path.read_text(encoding="utf-8"),
                "gap_report.md": gap_report_path.read_text(encoding="utf-8"),
            },
        }


def parse_compile_flags(raw_flags: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw_flags.replace("\n", " ").split(" ") if part.strip())


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
      grid-template-columns: repeat(4, minmax(140px, 1fr));
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
      </div>
      <pre id="artifact">Upload a C source file to generate cases.</pre>
    </section>
  </main>
  <script>
    const form = document.getElementById("generate-form");
    const submit = document.getElementById("submit");
    const error = document.getElementById("error");
    const artifact = document.getElementById("artifact");
    const state = { artifacts: {}, active: "gap_report.md" };

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
        renderSummary(payload.report);
        renderArtifact(state.active);
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
        state.active = button.dataset.artifact;
        renderArtifact(state.active);
      });
    });

    function renderSummary(report) {
      const decisions = report.decisions || [];
      const cases = decisions.reduce((total, decision) => total + decision.cases.length, 0);
      document.getElementById("score").textContent = `${Math.round((report.score || 0) * 100)}%`;
      document.getElementById("decisions").textContent = decisions.length;
      document.getElementById("cases").textContent = cases;
      document.getElementById("mode").textContent = report.mcdc_mode || "-";
      document.getElementById("coverage").textContent = report.coverage_ready ? "yes" : "no";
    }

    function renderArtifact(name) {
      artifact.textContent = state.artifacts[name] || "No artifact generated yet.";
    }
  </script>
</body>
</html>"""
