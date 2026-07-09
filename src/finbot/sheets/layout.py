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
            "Contas",
            (
                "ID",
                "Nome",
                "Tipo",
                "Saldo Inicial",
                "Entradas",
                "Saidas",
                "Transferencias Entrada",
                "Transferencias Saida",
                "Saldo Atual",
                "Status",
            ),
        ),
        SheetDefinition(
            "Cartoes",
            (
                "ID",
                "Nome",
                "Tipo",
                "Conta Vinculada",
                "Limite",
                "Fatura Atual",
                "Dia Fechamento",
                "Dia Vencimento",
                "Status",
            ),
        ),
        SheetDefinition(
            "Categorias",
            ("Categoria", "Tipo Padrao", "Limite Mensal", "Cor", "Ativa"),
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
            "Resumo_Conta",
            ("Conta", "Receitas", "Despesas", "Transferencias Entrada", "Transferencias Saida", "Saldo"),
        ),
        SheetDefinition(
            "Resumo_Categoria",
            ("Categoria", "Tipo", "Total", "% do Total", "Quantidade"),
        ),
        SheetDefinition(
            "Faturas",
            ("Cartao", "Fatura Atual", "Limite", "% Uso", "Fechamento", "Vencimento"),
        ),
        SheetDefinition(
            "Pendentes",
            ("Data", "Valor", "Categoria", "Descricao", "Status"),
        ),
        SheetDefinition(
            "Dashboard",
            ("Indicador", "Valor", "Periodo", "Observacao"),
        ),
        SheetDefinition(
            "Configuracoes",
            ("Chave", "Valor", "Observacao"),
        ),
        SheetDefinition(
            "Logs",
            ("Criado Em", "Nivel", "Origem", "Mensagem"),
        ),
    )


def default_formula_updates() -> tuple[tuple[str, list[list[object]]], ...]:
    return (
        (
            "Resumo_Mensal!A2",
            [
                [
                    '=SORT(UNIQUE(FILTER(Lancamentos!M2:M,Lancamentos!M2:M<>"")))',
                    '=ARRAYFORMULA(IF(A2:A="","",SUMIFS(Lancamentos!F:F,Lancamentos!C:C,"income",Lancamentos!M:M,A2:A)))',
                    '=ARRAYFORMULA(IF(A2:A="","",SUMIFS(Lancamentos!F:F,Lancamentos!C:C,"expense",Lancamentos!M:M,A2:A)))',
                    '=ARRAYFORMULA(IF(A2:A="","",B2:B-C2:C))',
                    '=ARRAYFORMULA(IF(A2:A="","",SUMIFS(Lancamentos!F:F,Lancamentos!L:L,"pending",Lancamentos!M:M,A2:A)))',
                    '=ARRAYFORMULA(IF(A2:A="","",D2:D))',
                    '=ARRAYFORMULA(IF(A2:A="","",IFERROR(D2:D/B2:B,0)))',
                ]
            ],
        ),
        (
            "Resumo_Categoria!A2",
            [
                [
                    '=QUERY(Lancamentos!E:F,"select E, sum(F), count(F) where E is not null group by E label sum(F) \'Total\', count(F) \'Quantidade\'",1)'
                ]
            ],
        ),
        (
            "Resumo_Conta!A2",
            [
                [
                    '=QUERY(Lancamentos!I:F,"select I, sum(F) where I is not null group by I label sum(F) \'Movimentacao\'",1)'
                ]
            ],
        ),
        (
            "Faturas!A2",
            [
                [
                    '=FILTER(Cartoes!B:H,Cartoes!B:B<>"")',
                ]
            ],
        ),
        (
            "Dashboard!A2",
            [
                ["Saldo total", '=SUM(Contas!I2:I)', "Atual", ""],
                ["Receita do mes", '=IFERROR(INDEX(Resumo_Mensal!B2:B,COUNTA(Resumo_Mensal!A2:A)),0)', "Mes atual", ""],
                ["Despesa do mes", '=IFERROR(INDEX(Resumo_Mensal!C2:C,COUNTA(Resumo_Mensal!A2:A)),0)', "Mes atual", ""],
                ["Saldo mensal", '=IFERROR(INDEX(Resumo_Mensal!D2:D,COUNTA(Resumo_Mensal!A2:A)),0)', "Mes atual", ""],
                ["Total faturas", '=SUM(Cartoes!F2:F)', "Atual", ""],
                ["Quantidade lancamentos", '=COUNTA(Lancamentos!A2:A)', "Atual", ""],
            ],
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
