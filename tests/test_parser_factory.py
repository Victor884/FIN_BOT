import pytest

from finbot.core.errors import ConfigurationError
from finbot.core.settings import Settings
from finbot.parser.composite import CompositeFinancialParser
from finbot.parser.factory import build_financial_parser
from finbot.parser.rules import RuleBasedParser


def test_build_financial_parser_uses_rules_when_ai_disabled() -> None:
    parser = build_financial_parser(Settings(ai_enabled=False))

    assert isinstance(parser, RuleBasedParser)


def test_build_financial_parser_requires_key_when_openai_enabled() -> None:
    with pytest.raises(ConfigurationError):
        build_financial_parser(Settings(ai_enabled=True, ai_provider="openai", openai_api_key=None))


def test_build_financial_parser_uses_composite_when_openai_enabled() -> None:
    parser = build_financial_parser(
        Settings(ai_enabled=True, ai_provider="openai", openai_api_key="test-key")
    )

    assert isinstance(parser, CompositeFinancialParser)
