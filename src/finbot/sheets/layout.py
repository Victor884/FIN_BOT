from dataclasses import dataclass
from typing import Any

from finbot.sheets.rows import TRANSACTION_HEADERS


@dataclass(frozen=True)
class SheetDefinition:
    title: str
    headers: tuple[str, ...]
    frozen_rows: int = 1


def default_sheet_definitions() -> tuple[SheetDefinition, ...]:
    return (
        SheetDefinition("Lancamentos", TRANSACTION_HEADERS),
        SheetDefinition(
            "Categorias",
            ("Categoria", "Tipo Padrao", "Limite Mensal", "Cor", "Ativa"),
        ),
        SheetDefinition(
            "Contas",
            ("Conta", "Tipo", "Instituicao", "Saldo Inicial", "Ativa"),
        ),
        SheetDefinition(
            "Resumo_Mensal",
            (
                "Mes",
                "Receitas",
                "Despesas",
                "Saldo",
                "Pendentes",
                "Economia",
                "% Economia",
            ),
        ),
        SheetDefinition(
            "Categorias_Mes",
            ("Mes", "Categoria", "Total", "% do Orcamento", "Limite", "Diferenca"),
        ),
        SheetDefinition(
            "Pendentes",
            ("Data", "Valor", "Categoria", "Descricao", "Status"),
        ),
        SheetDefinition(
            "Dashboard",
            ("Indicador", "Valor", "Periodo", "Observacao"),
        ),
    )


def build_create_missing_sheets_request(
    sheet_definitions: tuple[SheetDefinition, ...],
) -> dict[str, list[dict[str, Any]]]:
    return {
        "requests": [
            {
                "addSheet": {
                    "properties": {
                        "title": definition.title,
                        "gridProperties": {"frozenRowCount": definition.frozen_rows},
                    }
                }
            }
            for definition in sheet_definitions
        ]
    }
