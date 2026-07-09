from finbot.ai.openai_parser import OpenAIFinancialParser
from finbot.core.settings import Settings
from finbot.parser.composite import CompositeFinancialParser
from finbot.parser.contracts import FinancialParser
from finbot.parser.rules import RuleBasedParser


def build_financial_parser(settings: Settings) -> FinancialParser:
    rule_parser = RuleBasedParser()
    if not settings.ai_enabled:
        return rule_parser

    if settings.ai_provider != "openai":
        return rule_parser

    return CompositeFinancialParser(
        primary=rule_parser,
        fallback=OpenAIFinancialParser.from_settings(settings),
    )
