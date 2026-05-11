from ehs_audit.importer import classify_criticidade, parse_sheet_name


def test_parse_sheet_name():
    assert parse_sheet_name("4.12.08 — Electrical Safety")[0] == "4.12.08"


def test_classify_criticidade_heuristica():
    assert classify_criticidade("Electrical safety lockout required") == "Crítico"
