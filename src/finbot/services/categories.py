from finbot.db.repositories import CategoryRepository


DEFAULT_CATEGORIES = (
    "alimentacao",
    "transporte",
    "moradia",
    "saude",
    "educacao",
    "lazer",
    "vestuario",
    "receita_fixa",
    "renda_extra",
    "investimentos",
)


class CategoryService:
    def __init__(self, repository: CategoryRepository) -> None:
        self._repository = repository

    def add(self, name: str) -> str:
        normalized = _normalize(name)
        if not normalized:
            return "Informe o nome da categoria. Exemplo: /categoria adicionar pet"
        if normalized in DEFAULT_CATEGORIES:
            return f"A categoria {normalized} ja faz parte das categorias padrao."
        record = self._repository.add(normalized)
        return f"Categoria personalizada salva: {record.name}."

    def delete(self, name: str) -> str:
        normalized = _normalize(name)
        if normalized in DEFAULT_CATEGORIES:
            return "Categorias padrao nao podem ser removidas."
        if self._repository.delete_by_name(normalized):
            return f"Categoria personalizada removida: {normalized}."
        return f"Nao encontrei a categoria personalizada {normalized}."

    def list_message(self) -> str:
        custom = [record.name for record in self._repository.list()]
        standard = ", ".join(DEFAULT_CATEGORIES)
        custom_text = ", ".join(custom) if custom else "nenhuma"
        return f"Categorias padrao: {standard}.\nCategorias personalizadas: {custom_text}."

    def ensure(self, name: str | None) -> str | None:
        if not name:
            return None
        normalized = _normalize(name)
        if normalized and normalized not in DEFAULT_CATEGORIES:
            self._repository.add(normalized)
        return normalized or None


def _normalize(value: str) -> str:
    return "_".join(value.strip().lower().split())
