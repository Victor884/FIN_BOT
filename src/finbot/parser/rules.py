from finbot.parser.contracts import ParseResult


class RuleBasedParser:
    def parse(self, text: str) -> ParseResult:
        return ParseResult(draft=None, missing_fields=("parser_not_implemented",), raw_text=text)

