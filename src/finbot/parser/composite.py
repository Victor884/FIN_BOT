from finbot.parser.contracts import FinancialParser, ParseResult


class CompositeFinancialParser:
    def __init__(self, primary: FinancialParser, fallback: FinancialParser) -> None:
        self._primary = primary
        self._fallback = fallback

    def parse(self, text: str) -> ParseResult:
        primary_result = self._primary.parse(text)
        if primary_result.draft is not None and not primary_result.needs_confirmation:
            return primary_result
        return self._fallback.parse(text)
