from finbot.sheets.layout import (
    build_create_missing_sheets_request,
    default_formula_updates,
    default_sheet_definitions,
)
from finbot.sheets.rows import TRANSACTION_HEADERS


def test_default_sheet_definitions_include_expected_tabs() -> None:
    definitions = default_sheet_definitions()

    assert [definition.title for definition in definitions] == [
        "Lancamentos",
        "Contas",
        "Cartoes",
        "Categorias",
        "Resumo_Mensal",
        "Resumo_Conta",
        "Resumo_Categoria",
        "Faturas",
        "Pendentes",
        "Dashboard",
        "Configuracoes",
        "Logs",
    ]
    assert definitions[0].headers == TRANSACTION_HEADERS


def test_build_create_missing_sheets_request() -> None:
    definitions = default_sheet_definitions()

    request = build_create_missing_sheets_request(definitions)

    assert request["requests"][0] == {
        "addSheet": {
            "properties": {
                "title": "Lancamentos",
                "gridProperties": {"frozenRowCount": 1},
            }
        }
    }
    assert len(request["requests"]) == len(definitions)


def test_default_formula_updates_include_dashboard_and_summaries() -> None:
    formulas = default_formula_updates()

    ranges = [range_name for range_name, _ in formulas]

    assert "Resumo_Mensal!A2" in ranges
    assert "Resumo_Categoria!A2" in ranges
    assert "Dashboard!A2" in ranges
    assert any("SUMIFS" in str(values) for _, values in formulas)
    assert any("QUERY" in str(values) for _, values in formulas)
