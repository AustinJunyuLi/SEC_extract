"""Deterministic filing-derived extraction obligations."""

from __future__ import annotations

import hashlib
import inspect
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, replace
from typing import Any

from pipeline.core import Filing


NUMBER_WORDS: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "twenty-five": 25,
    "thirty": 30,
}

MONTH_NUMBERS: dict[str, str] = {
    "january": "01",
    "february": "02",
    "march": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10",
    "november": "11",
    "december": "12",
}

EXACT_NDA_RE = re.compile(
    r"(?P<quote>(?:the\s+company\s+)?(?:entered into|executed|signed)\s+"
    r"(?:confidentiality(?: and standstill)? agreements?|non-disclosure agreements?)\s+"
    r"with\s+(?P<count>\d+|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
    r"nineteen|twenty|twenty-five|thirty)\s+potentially interested\s+"
    r"(?P<type>financial|strategic)\s+(?:buyers?|parties|bidders?))",
    re.IGNORECASE,
)

EXACT_NDA_PARTIES_RE = re.compile(
    r"(?P<quote>confidentiality agreements?\s+entered into by\s+the\s+"
    r"(?P<count>\d+|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
    r"nineteen|twenty|twenty-five|thirty)\s+potentially interested parties)",
    re.IGNORECASE,
)

EXACT_BID_RE = re.compile(
    r"(?P<quote>(?:on\s+(?P<month>[A-Z][a-z]+)\s+(?P<day>\d{1,2}),\s+)?"
    r"(?P<count>\d+|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
    r"nineteen|twenty)\s+of\s+the\s+potentially interested parties\s+"
    r"submitted\s+indications?\s+of\s+interest)",
    re.IGNORECASE,
)

FINAL_ROUND_RE = re.compile(
    r"(?P<quote>allow\s+the\s+"
    r"(?P<count>\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
    r"bidders?\s+[^.]{0,160}?to\s+proceed\s+to\s+the\s+final\s+round)",
    re.IGNORECASE,
)

PETSMART_BUYER_GROUP_NAMES: tuple[str, ...] = (
    "BC Partners",
    "La Caisse",
    "GIC",
    "StepStone",
)
PETSMART_LATE_MEMBER = "Longview"
OBLIGATION_CONTRACT_VERSION_INPUTS = {"version": "obligations_v3"}


@dataclass(frozen=True)
class Obligation:
    obligation_id: str
    kind: str
    severity: str
    source_quote: str
    source_page: int
    expected: dict[str, Any]
    reason: str


@dataclass(frozen=True)
class ObligationCheck:
    obligation: Obligation
    status: str
    matched_rows: list[int]
    reason: str


@dataclass(frozen=True)
class ObligationResult:
    obligations: list[Obligation]
    checks: list[ObligationCheck]

    @property
    def has_hard_unmet(self) -> bool:
        return any(
            check.status == "unmet" and check.obligation.severity == "hard"
            for check in self.checks
        )


def _normalize(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value)).casefold().split())


def _clean_quote(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def _parse_count(token: str) -> int:
    normalized = token.casefold()
    if normalized.isdigit():
        return int(normalized)
    return NUMBER_WORDS[normalized]


def _month_day(month: str | None, day: str | None) -> str | None:
    if not month or not day:
        return None
    month_number = MONTH_NUMBERS.get(month.casefold())
    if month_number is None:
        return None
    return f"{month_number}-{int(day):02d}"


def _obligation_id(index: int) -> str:
    return f"obl-{index + 1:03d}"


def _sentence_around(text: str, start: int, end: int) -> str:
    left_candidates = [text.rfind(mark, 0, start) for mark in (".", "\n", ";", "\u2022")]
    left = max(left_candidates)
    right_candidates = [
        position for position in (
            text.find(mark, end) for mark in (".", "\n", ";")
        )
        if position != -1
    ]
    right = min(right_candidates) if right_candidates else min(len(text), end + 500)
    return _clean_quote(text[left + 1:right + 1])


def _append_obligation(
    obligations: list[Obligation],
    *,
    kind: str,
    source_quote: str,
    source_page: int,
    expected: dict[str, Any],
    reason: str,
    severity: str = "hard",
) -> None:
    obligations.append(Obligation(
        obligation_id=_obligation_id(len(obligations)),
        kind=kind,
        severity=severity,
        source_quote=source_quote,
        source_page=source_page,
        expected=expected,
        reason=reason,
    ))


def _detect_exact_count_obligations(filing: Filing, obligations: list[Obligation]) -> None:
    for page in filing.pages:
        page_no = page.get("number")
        if not isinstance(page_no, int):
            continue
        text = str(page.get("content", ""))
        for match in EXACT_NDA_RE.finditer(text):
            buyer_type = "f" if match.group("type").casefold() == "financial" else "s"
            _append_obligation(
                obligations,
                kind="exact_count_nda",
                source_quote=_clean_quote(match.group("quote")),
                source_page=page_no,
                expected={"count": _parse_count(match.group("count")), "bidder_type": buyer_type},
                reason="Filing states an exact count of current-process bidder confidentiality agreements.",
            )
        for match in EXACT_NDA_PARTIES_RE.finditer(text):
            _append_obligation(
                obligations,
                kind="exact_count_nda",
                source_quote=_clean_quote(match.group("quote")),
                source_page=page_no,
                expected={"count": _parse_count(match.group("count")), "bidder_type": None},
                reason="Filing states an exact count of current-process bidder confidentiality agreements.",
            )
        for match in EXACT_BID_RE.finditer(text):
            expected: dict[str, Any] = {"count": _parse_count(match.group("count"))}
            month_day = _month_day(match.group("month"), match.group("day"))
            if month_day is not None:
                expected["month_day"] = month_day
            _append_obligation(
                obligations,
                kind="exact_count_bid",
                source_quote=_clean_quote(match.group("quote")),
                source_page=page_no,
                expected=expected,
                reason="Filing states an exact count of parties submitting indications of interest.",
            )
        for match in FINAL_ROUND_RE.finditer(text):
            _append_obligation(
                obligations,
                kind="exact_count_final_round",
                source_quote=_clean_quote(match.group("quote")),
                source_page=page_no,
                expected={"count": _parse_count(match.group("count"))},
                reason="Filing states an exact count of bidders advanced to the final round.",
            )


def _detect_buyer_group_obligations(filing: Filing, obligations: list[Obligation]) -> None:
    buyer_group_seen = False
    for page in filing.pages:
        page_no = page.get("number")
        if not isinstance(page_no, int):
            continue
        text = str(page.get("content", ""))
        normalized = _normalize(text)
        has_core_group = (
            "buyer group" in normalized
            and all(_normalize(name) in normalized for name in PETSMART_BUYER_GROUP_NAMES)
        )
        if has_core_group and not buyer_group_seen:
            start = normalized.find("buyer group")
            quote = _sentence_around(text, max(0, start), max(0, start) + len("buyer group"))
            _append_obligation(
                obligations,
                kind="buyer_group_executed_constituents",
                source_quote=quote,
                source_page=page_no,
                expected={
                    "constituents": list(PETSMART_BUYER_GROUP_NAMES),
                    "bid_note": "Executed",
                },
                reason=(
                    "Filing defines the Buyer Group constituents; extraction must "
                    "atomize executed buyer rows."
                ),
            )
            buyer_group_seen = True
        if (
            PETSMART_LATE_MEMBER.casefold() in normalized
            and "buyer group" in normalized
            and "confidentiality agreement" in normalized
        ):
            start = normalized.find(PETSMART_LATE_MEMBER.casefold())
            quote = _sentence_around(text, max(0, start), max(0, start) + len(PETSMART_LATE_MEMBER))
            _append_obligation(
                obligations,
                kind="late_member_inherited_nda",
                source_quote=quote,
                source_page=page_no,
                expected={
                    "member": PETSMART_LATE_MEMBER,
                    "requires_bid_notes": ["ConsortiumCA", "NDA"],
                },
                reason=(
                    "Late buyer-group member joined an already-NDA-bound group and "
                    "needs both ConsortiumCA and inherited NDA rows."
                ),
            )


def derive_obligations(filing: Filing) -> list[Obligation]:
    obligations: list[Obligation] = []
    _detect_exact_count_obligations(filing, obligations)
    _detect_buyer_group_obligations(filing, obligations)
    return _dedupe_obligations(obligations)


def _dedupe_key(obligation: Obligation) -> tuple[str, str]:
    if obligation.kind == "exact_count_nda":
        return (obligation.kind, str(obligation.expected.get("count")))
    return (
        obligation.kind,
        json.dumps(obligation.expected, sort_keys=True, separators=(",", ":")),
    )


def _prefer_obligation(candidate: Obligation, incumbent: Obligation) -> bool:
    if candidate.kind == "exact_count_nda":
        candidate_type = candidate.expected.get("bidder_type")
        incumbent_type = incumbent.expected.get("bidder_type")
        return candidate_type is not None and incumbent_type is None
    return False


def _dedupe_obligations(obligations: list[Obligation]) -> list[Obligation]:
    chosen: dict[tuple[str, str], Obligation] = {}
    order: list[tuple[str, str]] = []
    for obligation in obligations:
        key = _dedupe_key(obligation)
        if key not in chosen:
            chosen[key] = obligation
            order.append(key)
            continue
        if _prefer_obligation(obligation, chosen[key]):
            chosen[key] = obligation
    return [
        replace(chosen[key], obligation_id=_obligation_id(index))
        for index, key in enumerate(order)
    ]


def _row_id(event: dict[str, Any], fallback: int) -> int:
    bidder_id = event.get("BidderID")
    if isinstance(bidder_id, int) and not isinstance(bidder_id, bool):
        return bidder_id
    return fallback + 1


def _event_labels(event: dict[str, Any], registry: dict[str, Any]) -> set[str]:
    labels = {
        _normalize(event.get("bidder_alias", "")),
        _normalize(event.get("bidder_name", "")),
    }
    bidder_name = event.get("bidder_name")
    entry = registry.get(bidder_name) if isinstance(bidder_name, str) else None
    if isinstance(entry, dict):
        labels.add(_normalize(entry.get("resolved_name", "")))
        for alias in entry.get("aliases_observed") or []:
            labels.add(_normalize(alias))
    return {label for label in labels if label}


def _event_source_pages(event: dict[str, Any]) -> set[int]:
    source_page = event.get("source_page")
    values = source_page if isinstance(source_page, list) else [source_page]
    return {
        value for value in values
        if isinstance(value, int) and not isinstance(value, bool)
    }


def _row_flag_codes(event: dict[str, Any]) -> set[str]:
    flags = event.get("flags")
    if not isinstance(flags, list):
        return set()
    return {
        flag.get("code")
        for flag in flags
        if isinstance(flag, dict) and isinstance(flag.get("code"), str)
    }


def _quote_for_page(event: dict[str, Any], page: int) -> str:
    quote = event.get("source_quote")
    source_page = event.get("source_page")
    if isinstance(quote, list) and isinstance(source_page, list):
        parts = [
            str(item)
            for item, item_page in zip(quote, source_page)
            if item_page == page
        ]
        return _normalize(" ".join(parts))
    if source_page == page:
        return _normalize(quote)
    return ""


def _exact_count_party_unit_key(
    obligation: Obligation,
    event: dict[str, Any],
) -> tuple[Any, ...] | None:
    if "buyer_group_constituent" not in _row_flag_codes(event):
        return None
    return (
        obligation.kind,
        event.get("bid_note"),
        event.get("process_phase"),
        event.get("bid_date_precise"),
        event.get("bid_date_rough"),
        event.get("bid_type"),
        json.dumps(event.get("bid_value"), sort_keys=True, separators=(",", ":")),
        _quote_for_page(event, obligation.source_page),
    )


def _cites_obligation_source(event: dict[str, Any], obligation: Obligation) -> bool:
    return obligation.source_page in _event_source_pages(event)


def _matches_obligation_date(event: dict[str, Any], obligation: Obligation) -> bool:
    month_day = obligation.expected.get("month_day")
    if not isinstance(month_day, str):
        return True
    precise = event.get("bid_date_precise")
    return isinstance(precise, str) and precise.endswith(f"-{month_day}")


def _matches_name(event: dict[str, Any], name: str, registry: dict[str, Any]) -> bool:
    needle = _normalize(name)
    return any(needle in label or label in needle for label in _event_labels(event, registry))


def _matched_rows(
    obligation: Obligation,
    events: list[dict[str, Any]],
    deal: dict[str, Any],
) -> list[int]:
    registry = deal.get("bidder_registry") if isinstance(deal, dict) else {}
    if not isinstance(registry, dict):
        registry = {}
    matches: list[int] = []
    exact_count_party_units: set[tuple[Any, ...]] = set()
    for index, event in enumerate(events):
        if obligation.kind == "exact_count_nda":
            if event.get("role") != "bidder" or event.get("bid_note") != "NDA":
                continue
            if not _cites_obligation_source(event, obligation):
                continue
            expected_type = obligation.expected.get("bidder_type")
            if expected_type is not None and event.get("bidder_type") != expected_type:
                continue
            unit_key = _exact_count_party_unit_key(obligation, event)
            if unit_key is not None:
                if unit_key in exact_count_party_units:
                    continue
                exact_count_party_units.add(unit_key)
            matches.append(_row_id(event, index))
        elif obligation.kind == "exact_count_bid":
            if not _cites_obligation_source(event, obligation):
                continue
            if not _matches_obligation_date(event, obligation):
                continue
            if event.get("role") == "bidder" and event.get("bid_note") == "Bid":
                unit_key = _exact_count_party_unit_key(obligation, event)
                if unit_key is not None:
                    if unit_key in exact_count_party_units:
                        continue
                    exact_count_party_units.add(unit_key)
                matches.append(_row_id(event, index))
        elif obligation.kind == "exact_count_final_round":
            if not _cites_obligation_source(event, obligation):
                continue
            if (
                event.get("role") == "bidder"
                and event.get("bid_note") == "Bid"
                and event.get("invited_to_formal_round") is True
            ):
                matches.append(_row_id(event, index))
        elif obligation.kind == "buyer_group_executed_constituents":
            constituents = obligation.expected.get("constituents") or []
            if event.get("bid_note") != "Executed":
                continue
            if any(_matches_name(event, constituent, registry) for constituent in constituents):
                matches.append(_row_id(event, index))
        elif obligation.kind == "late_member_inherited_nda":
            member = obligation.expected.get("member")
            if isinstance(member, str) and _matches_name(event, member, registry):
                if event.get("bid_note") in set(obligation.expected.get("requires_bid_notes") or []):
                    matches.append(_row_id(event, index))
    return matches


def _check_satisfied(obligation: Obligation, matched_rows: list[int]) -> tuple[str, str]:
    expected_count = obligation.expected.get("count")
    if isinstance(expected_count, int):
        status = "satisfied" if len(matched_rows) == expected_count else "unmet"
        return status, f"expected exactly {expected_count} matching rows but found {len(matched_rows)}"
    if obligation.kind == "buyer_group_executed_constituents":
        expected_constituents = obligation.expected.get("constituents") or []
        status = "satisfied" if len(set(matched_rows)) >= len(expected_constituents) else "unmet"
        return (
            status,
            f"expected executed rows for {len(expected_constituents)} Buyer Group constituents but found {len(set(matched_rows))}",
        )
    if obligation.kind == "late_member_inherited_nda":
        required = obligation.expected.get("requires_bid_notes") or []
        status = "satisfied" if len(set(matched_rows)) >= len(required) else "unmet"
        return (
            status,
            f"expected Longview rows for {required} but found {len(set(matched_rows))}",
        )
    status = "satisfied" if matched_rows else "unmet"
    return status, "required filing predicate satisfied" if matched_rows else "required filing predicate is unmet"


def check_obligations(raw_extraction: dict[str, Any], filing: Filing) -> ObligationResult:
    obligations = derive_obligations(filing)
    events = [
        event for event in raw_extraction.get("events", [])
        if isinstance(event, dict)
    ]
    deal = raw_extraction.get("deal") if isinstance(raw_extraction.get("deal"), dict) else {}
    checks: list[ObligationCheck] = []
    for obligation in obligations:
        matched_rows = _matched_rows(obligation, events, deal)
        status, reason = _check_satisfied(obligation, matched_rows)
        checks.append(ObligationCheck(obligation, status, matched_rows, reason))
    return ObligationResult(obligations, checks)


def flags_for_unmet(result: ObligationResult) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    for check in result.checks:
        if check.status != "unmet" or check.obligation.severity != "hard":
            continue
        flags.append({
            "code": f"unmet_{check.obligation.kind}",
            "severity": "hard",
            "reason": (
                f"Obligation {check.obligation.obligation_id} {check.obligation.kind} "
                f"{check.reason}; source page {check.obligation.source_page}."
            ),
            "deal_level": True,
            "obligation_id": check.obligation.obligation_id,
            "source_page": check.obligation.source_page,
        })
    return flags


def obligation_result_payload(result: ObligationResult) -> dict[str, Any]:
    return {
        "obligations": [asdict(obligation) for obligation in result.obligations],
        "checks": [
            {
                "obligation": asdict(check.obligation),
                "status": check.status,
                "matched_rows": check.matched_rows,
                "reason": check.reason,
            }
            for check in result.checks
        ],
        "hard_unmet_count": sum(
            1 for check in result.checks
            if check.status == "unmet" and check.obligation.severity == "hard"
        ),
    }


def obligation_contract_version() -> str:
    payload = (
        repr(OBLIGATION_CONTRACT_VERSION_INPUTS)
        + inspect.getsource(derive_obligations)
        + inspect.getsource(check_obligations)
        + inspect.getsource(flags_for_unmet)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
