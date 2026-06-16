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
    assert "Ccode_interface" in response.text
    assert "testcase-table" in response.text
    assert "ccode-interface" in response.text
    assert ".ccode-grid" in response.text
    assert "overflow: hidden;" in response.text
    assert "height: 100%;" in response.text


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
    assert "coverage_ready" in payload["report"]
    assert "coverage_status" in payload["report"]
    assert "toolchain_details" in payload["report"]
    assert "mcdc_cases.json" in payload["artifacts"]
    assert "generated_mcdc_tests.c" in payload["artifacts"]
    assert "gap_report.md" in payload["artifacts"]
    assert "mcdc_testcases.xlsx" in payload["downloads"]
