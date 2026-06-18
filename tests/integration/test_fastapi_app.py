import base64
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient

from src.api.app import app


def test_web_app_health() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_web_app_exposes_table_and_excel_controls() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Testcase_table" in response.text
    assert "Export Excel" in response.text
    assert "Export CSV" in response.text
    assert "Ccode_interface" in response.text
    assert "Excel Format Version" in response.text
    assert "Excel Architecture" in response.text
    assert "Excel Scope" in response.text
    assert "Excel Name" in response.text
    assert "BTC fill MANUAL: off" in response.text
    assert "btc_fill_toggle" in response.text
    assert "fill_manual_for_btc" in response.text
    assert "state.btcFillManual" in response.text
    assert "parameter_columns" in response.text
    assert "Parameters" in response.text
    assert '<input id="excel_format_version" type="text">' in response.text
    assert '<input id="excel_architecture" type="text">' in response.text
    assert '<input id="excel_scope" type="text">' in response.text
    assert '<input id="excel_name" type="text">' in response.text
    assert "#99ccff" in response.text
    assert "testcase-table" in response.text
    assert "excel-export-panel" in response.text
    assert "excel_export_submit" in response.text
    assert "csv_export_submit" in response.text
    assert "/api/export-csv" in response.text
    assert "Note: this export gets data from Testcase_table." in response.text
    assert "export-action" in response.text
    assert 'state.active = "excel_export"' in response.text
    assert "ccode-interface" in response.text
    assert ".ccode-grid" in response.text
    assert "overflow: hidden;" in response.text
    assert "height: 100%;" in response.text
    assert "report.testcase_table?.rows?.length" in response.text
    assert "graphTraceDetails" in response.text
    assert "Graph trace: root input" in response.text
    assert "setupLabel" in response.text
    assert "manual required" in response.text
    assert "targets /" in response.text


def test_web_app_generates_mcdc_artifacts() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/generate",
        data={
            "target_function": "logic",
            "input_variables": "a, b, flag, expected=PASS, IN_gear=D",
            "output_variables": "VF24blatgfd_s=-24.5, VS15lat_grev=-2.5",
            "compile_flags": "-DUNIT_TEST",
            "max_conditions": "12",
            "mcdc_mode": "masking",
        },
        files={
            "source": (
                "logic.c",
                b"int logic(int a,int b,int flag){ if ((a > 0 && b < 10) || flag) return 1; return 0; }",
                "text/x-c",
            ),
            "headers": ("logic.h", b"int logic(int a, int b, int flag);\n", "text/x-c"),
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["report"]["score"] == 1.0
    assert payload["report"]["source_text"].startswith("int logic")
    assert payload["report"]["mcdc_mode"] == "masking"
    assert payload["report"]["input_variables"] == ["a", "b", "flag", "expected", "IN_gear"]
    assert payload["report"]["manual_inputs"] == {"expected": "PASS", "IN_gear": "D"}
    assert payload["report"]["output_variables"] == ["VF24blatgfd_s", "VS15lat_grev"]
    assert payload["report"]["manual_outputs"] == {"VF24blatgfd_s": -24.5, "VS15lat_grev": -2.5}
    assert payload["report"]["mcdc_complete"] is True
    assert payload["report"]["interface_graph"]["nodes"]
    assert payload["report"]["interface_graph"]["edges"]
    assert payload["report"]["interface_graph"]["condition_traces"]
    assert payload["report"]["testcase_table"]["target_rows"] == len(payload["report"]["testcase_table"]["rows"])
    assert payload["report"]["testcase_table"]["concrete_rows"] == len(payload["report"]["testcase_table"]["rows"])
    assert payload["report"]["testcase_table"]["input_columns"] == ["a", "b", "flag", "expected", "IN_gear"]
    assert payload["report"]["testcase_table"]["output_columns"] == ["VF24blatgfd_s", "VS15lat_grev"]
    assert payload["report"]["testcase_table"]["mcdc_complete"] is True
    assert payload["report"]["testcase_table"]["rows"][0]["inputs"].keys() == {
        "a",
        "b",
        "flag",
        "expected",
        "IN_gear",
    }
    assert payload["report"]["testcase_table"]["rows"][0]["setup_status"] == "concrete"
    assert "coverage_ready" in payload["report"]
    assert "coverage_status" in payload["report"]
    assert "toolchain_details" in payload["report"]
    assert "mcdc_cases.json" in payload["artifacts"]
    assert "generated_mcdc_tests.c" in payload["artifacts"]
    assert "gap_report.md" in payload["artifacts"]
    assert "mcdc_testcases.xlsx" in payload["downloads"]


def test_web_app_exports_excel_with_user_metadata() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/generate",
        data={
            "target_function": "logic",
            "excel_format_version": "1.3",
            "excel_architecture": "Example Architecture [C-Code]",
            "excel_scope": "logic.c:1:logic",
            "excel_name": "SIL_SV_ATG_1",
            "max_conditions": "12",
            "mcdc_mode": "masking",
        },
        files={
            "source": (
                "logic.c",
                b"int logic(int a,int b){ if (a > 0 && b > 0) return 1; return 0; }",
                "text/x-c",
            ),
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["excel_filename"] == "SIL_SV_ATG_1.xlsx"
    assert "SIL_SV_ATG_1.xlsx" in payload["downloads"]

    export_response = client.post(
        "/api/export-excel",
        json={
            "report": payload["report"],
            "format_version": "1.3",
            "architecture": "Example Architecture [C-Code]",
            "scope": "logic.c:1:logic",
            "name": "SIL_SV_ATG_2",
        },
    )
    export_payload = export_response.json()

    assert export_response.status_code == 200
    assert export_payload["filename"] == "SIL_SV_ATG_2.xlsx"
    with ZipFile(BytesIO(base64.b64decode(export_payload["download"]))) as workbook:
        workbook_xml = workbook.read("xl/workbook.xml").decode()
        sheet_xml = workbook.read("xl/worksheets/sheet1.xml").decode()
    assert 'name="SIL_SV_ATG_2"' in workbook_xml
    assert "Format Version" in sheet_xml
    assert "Example Architecture [C-Code]" in sheet_xml
    assert "logic.c:1:logic" in sheet_xml
    assert "SIL_SV_ATG_2" in sheet_xml
    assert "Step" in sheet_xml
    assert "Inputs" in sheet_xml
    assert "Outputs" in sheet_xml
    assert sheet_xml.count("Comment") == 1


def test_web_app_exports_excel_with_btc_manual_fill() -> None:
    client = TestClient(app)

    export_response = client.post(
        "/api/export-excel",
        json={
            "report": {
                "testcase_table": {
                    "input_columns": ["a", "b", "missing"],
                    "output_columns": ["y"],
                    "rows": [
                        {"inputs": {"a": "MANUAL", "b": 5, "missing": "MANUAL"}, "outputs": {"y": "MANUAL"}},
                        {"inputs": {"a": -2, "b": "MANUAL", "missing": "MANUAL"}, "outputs": {"y": 1}},
                    ],
                }
            },
            "name": "BTC_READY",
            "fill_manual_for_btc": True,
        },
    )
    export_payload = export_response.json()

    assert export_response.status_code == 200
    assert export_payload["filename"] == "BTC_READY.xlsx"
    with ZipFile(BytesIO(base64.b64decode(export_payload["download"]))) as workbook:
        sheet_xml = workbook.read("xl/worksheets/sheet1.xml").decode()
    assert "MANUAL" not in sheet_xml
    assert "-2" in sheet_xml
    assert "<v>0</v>" in sheet_xml


def test_web_app_exports_csv_from_testcase_table() -> None:
    client = TestClient(app)

    export_response = client.post(
        "/api/export-csv",
        json={
            "report": {
                "testcase_table": {
                    "input_columns": ["a", "missing"],
                    "parameter_columns": ["cal"],
                    "output_columns": ["y"],
                    "input_column_keys": ["a", "missing"],
                    "parameter_column_keys": ["cal[0]"],
                    "output_column_keys": ["y"],
                    "rows": [
                        {
                            "inputs": {"a": "MANUAL", "missing": "MANUAL"},
                            "parameters": {"cal[0]": 2},
                            "outputs": {"y": "MANUAL"},
                        }
                    ],
                }
            },
            "format_version": "2.5",
            "architecture": "CSV Architecture [C-Code]",
            "scope": "logic.c:1:logic",
            "name": "CSV_READY",
            "fill_manual_for_btc": True,
        },
    )
    export_payload = export_response.json()

    assert export_response.status_code == 200
    assert export_payload["filename"] == "CSV_READY.csv"
    csv_text = base64.b64decode(export_payload["download"]).decode("utf-8-sig")
    assert "Format Version,2.5,,,," in csv_text
    assert "Architecture,CSV Architecture [C-Code],,,," in csv_text
    assert "Scope,logic.c:1:logic,,,," in csv_text
    assert "Name,CSV_READY,,,," in csv_text
    assert "Mode,Inputs,Inputs,Parameters,Outputs," in csv_text
    assert "Step,a,missing,cal,y,Comment" in csv_text
    assert "0,0,0,2,0," in csv_text
    assert "MANUAL" not in csv_text
