from finbot.sheets.layout import build_create_missing_sheets_request, default_sheet_definitions
from finbot.sheets.rows import TRANSACTION_HEADERS


def test_default_sheet_definitions_include_expected_tabs() -> None:
    definitions = default_sheet_definitions()

    assert [definition.title for definition in definitions] == [
        "Lancamentos",
        "Categorias",
        "Contas",
        "Resumo_Mensal",
        "Categorias_Mes",
        "Pendentes",
        "Dashboard",
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
