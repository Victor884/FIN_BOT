import logging
from dataclasses import replace
from time import perf_counter

from finbot.models.transaction import TransactionDraft, TransactionType
from finbot.parser.contracts import FinancialParser, ParseResult


logger = logging.getLogger(__name__)

DEFAULT_AI_CONFIDENCE_THRESHOLD = 0.72


class CompositeFinancialParser:
    def __init__(
        self,
        primary: FinancialParser,
        fallback: FinancialParser,
        confidence_threshold: float = DEFAULT_AI_CONFIDENCE_THRESHOLD,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._confidence_threshold = confidence_threshold

    def parse(self, text: str) -> ParseResult:
        primary_result = self._primary.parse(text)
        confidence_score = calculate_parser_confidence(primary_result)
        if not should_use_ai(primary_result, confidence_score, self._confidence_threshold):
            return primary_result

        try:
            ai_start = perf_counter()
            fallback_result = self._fallback.parse(text)
        except Exception:
            logger.exception("ai_parser_failed")
            return primary_result

        merged = merge_rule_and_ai_result(primary_result, fallback_result)
        return replace(
            merged,
            source="ai",
            ai_duration_ms=round((perf_counter() - ai_start) * 1000),
        )


def parse_with_rules(parser: FinancialParser, message: str) -> ParseResult:
    return parser.parse(message)


def parse_with_ai(parser: FinancialParser, message: str) -> ParseResult:
    return parser.parse(message)


def calculate_parser_confidence(parsed_result: ParseResult) -> float:
    if parsed_result.draft is None:
        return 0.0

    draft = parsed_result.draft
    score = draft.confidence

    if parsed_result.needs_confirmation:
        score -= 0.25
    if parsed_result.missing_fields:
        score -= 0.15 * len(parsed_result.missing_fields)
    if not draft.description or draft.description.startswith("movimentacao "):
        score -= 0.2
    if draft.type in {TransactionType.EXPENSE, TransactionType.INCOME} and not draft.category:
        score -= 0.1
    if draft.type == TransactionType.TRANSFER:
        if not draft.account_from:
            score -= 0.2
        if not draft.account_to:
            score -= 0.2
    if draft.account_from and "AMBIGUOUS:" in draft.account_from:
        score -= 0.25
    if draft.account_to and "AMBIGUOUS:" in draft.account_to:
        score -= 0.25

    return max(0.0, min(1.0, score))


def should_use_ai(
    parsed_result: ParseResult,
    confidence_score: float,
    threshold: float = DEFAULT_AI_CONFIDENCE_THRESHOLD,
) -> bool:
    if parsed_result.draft is None:
        return True
    if parsed_result.needs_confirmation:
        return True
    if parsed_result.missing_fields:
        return True
    return confidence_score < threshold


def merge_rule_and_ai_result(rule_result: ParseResult, ai_result: ParseResult) -> ParseResult:
    if ai_result.draft is None:
        return ai_result if rule_result.draft is None else rule_result
    if rule_result.draft is None:
        return ai_result

    merged_draft = _merge_drafts(rule_result.draft, ai_result.draft)
    return ParseResult(
        draft=merged_draft,
        missing_fields=ai_result.missing_fields,
        needs_confirmation=ai_result.needs_confirmation,
        raw_text=rule_result.raw_text or ai_result.raw_text,
        source="ai",
        ai_duration_ms=ai_result.ai_duration_ms,
    )


def _merge_drafts(rule_draft: TransactionDraft, ai_draft: TransactionDraft) -> TransactionDraft:
    return replace(
        rule_draft,
        type=ai_draft.type or rule_draft.type,
        amount=ai_draft.amount or rule_draft.amount,
        transaction_date=ai_draft.transaction_date or rule_draft.transaction_date,
        description=ai_draft.description or rule_draft.description,
        category=ai_draft.category or rule_draft.category,
        payment_method=ai_draft.payment_method or rule_draft.payment_method,
        account_from=ai_draft.account_from or rule_draft.account_from,
        account_to=ai_draft.account_to or rule_draft.account_to,
        is_recurring=ai_draft.is_recurring or rule_draft.is_recurring,
        status=ai_draft.status or rule_draft.status,
        confidence=max(rule_draft.confidence, ai_draft.confidence),
    )
