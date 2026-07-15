"""SCM-inspired, deterministic incident priority policy.

This module encodes auditable policy assumptions. It does not estimate causal
effects: confirmed incident evidence is transformed into operational bands,
while review candidates remain visible but cannot increase priority.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime, timezone
from math import isfinite
from uuid import UUID

from civicpulse.config import PriorityPolicy
from civicpulse.domain import (
    ClusteringStatus,
    Complaint,
    Incident,
    PriorityAssessment,
    PriorityLevel,
    PrioritySignal,
    PriorityStatus,
    SensitiveLocation,
    StrictModel,
)
from civicpulse.geo import haversine_metres
from pydantic import Field


class SafetySignal(StrictModel):
    name: str = Field(min_length=1)
    complaint_ids: tuple[UUID, ...] = Field(min_length=1)
    matched_terms: tuple[str, ...] = Field(min_length=1)
    reasons: tuple[str, ...] = Field(min_length=1)


SAFETY_TERMS: dict[str, tuple[str, ...]] = {
    "active_flooding": ("banjir", "flood", "flooding", "flooded", "air naik", "flash flood"),
    "accident_injury": (
        "accident",
        "kemalangan",
        "injury",
        "cedera",
        "motor hampir jatuh",
    ),
    "blocked_road": (
        "blocked road",
        "jalan blocked",
        "jalan terhalang",
        "road obstruction",
        "tutup jalan",
    ),
    "exposed_electrical_hazard": (
        "exposed wire",
        "wayar terdedah",
        "kabel terdedah",
        "live wire",
    ),
}
_NEGATION_WORDS = {"no", "not", "tak", "tiada", "tidak", "tanpa"}
_FLOODING_RESOLUTION_WORDS = {"ended", "receded", "resolved", "subsided", "surut"}
_FLOODING_CLEAR_WORDS = {"clear", "cleared"}
_FLOODING_HISTORICAL_WORDS = {"previously", "was", "were"}


def _term_matches(text: str, term: str) -> bool:
    pattern = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)")
    for match in pattern.finditer(text):
        prefix = text[: match.start()].split()
        if not prefix or not any(word in _NEGATION_WORDS for word in prefix[-2:]):
            return True
    return False


def _flooding_term_matches(text: str, term: str) -> bool:
    """Match an active flooding occurrence after excluding explicit inactive context."""
    pattern = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)")
    for match in pattern.finditer(text):
        prefix = re.findall(r"\w+", text[: match.start()])
        suffix = re.findall(r"\w+", text[match.end() :])
        if any(word in _NEGATION_WORDS for word in prefix[-2:]):
            continue
        if suffix[:2] == ["with", "complaints"]:
            continue
        if any(word in _FLOODING_RESOLUTION_WORDS for word in suffix[:3]):
            continue
        historical = any(word in _FLOODING_HISTORICAL_WORDS for word in prefix[-2:]) or (
            "last" in suffix[:3] or "yesterday" in suffix[:3]
        )
        if historical and any(word in _FLOODING_CLEAR_WORDS for word in suffix[:6]):
            continue
        return True
    return False


def detect_safety_signals(
    complaints: Sequence[Complaint], _policy: PriorityPolicy
) -> tuple[SafetySignal, ...]:
    """Detect deduplicated safety signals from confirmed complaint evidence."""
    signals: list[SafetySignal] = []
    for signal_name, terms in SAFETY_TERMS.items():
        matched_complaints: list[Complaint] = []
        matched_terms: set[str] = set()
        for complaint in complaints:
            text = complaint.normalized_text
            term_matches = (
                _flooding_term_matches if signal_name == "active_flooding" else _term_matches
            )
            complaint_terms = {term for term in terms if term_matches(text, term)}
            if complaint_terms:
                matched_complaints.append(complaint)
                matched_terms.update(complaint_terms)
        if matched_complaints:
            signals.append(
                SafetySignal(
                    name=signal_name,
                    complaint_ids=tuple(sorted((item.id for item in matched_complaints), key=str)),
                    matched_terms=tuple(sorted(matched_terms)),
                    reasons=(
                        f"{signal_name} detected in {len(matched_complaints)} confirmed complaint(s)",
                    ),
                )
            )
    return tuple(signals)


def _signal(
    name: str,
    value: str,
    normalized_value: float | None,
    triggered: bool,
    reasons: tuple[str, ...] = (),
) -> PrioritySignal:
    if normalized_value is not None and not isfinite(normalized_value):
        raise ValueError("priority signal normalized value must be finite")
    return PrioritySignal(
        name=name,
        value=value,
        normalized_value=normalized_value,
        triggered=triggered,
        reasons=reasons,
    )


def _highest_level(levels: list[PriorityLevel]) -> PriorityLevel:
    rank = {
        PriorityLevel.LOW: 0,
        PriorityLevel.MEDIUM: 1,
        PriorityLevel.HIGH: 2,
        PriorityLevel.CRITICAL: 3,
    }
    return max(levels, key=lambda level: rank[level], default=PriorityLevel.LOW)


def assess_priority(
    incident: Incident,
    complaints: Sequence[Complaint],
    sensitive_locations: Sequence[SensitiveLocation],
    policy: PriorityPolicy,
    now: datetime,
) -> PriorityAssessment:
    """Assign a deterministic operational band from confirmed evidence only."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must include a timezone")
    complaint_by_id = {complaint.id: complaint for complaint in complaints}
    if len(complaint_by_id) != len(complaints):
        raise ValueError("duplicate complaint IDs are not allowed")
    if not set(incident.complaint_ids).issubset(complaint_by_id):
        raise ValueError("incident references a complaint missing from evidence")
    confirmed = tuple(complaint_by_id[complaint_id] for complaint_id in incident.complaint_ids)
    pending_count = len(set(incident.review_candidate_ids))
    safety_signals = detect_safety_signals(confirmed, policy)
    sensitive_matches = {
        location.id
        for complaint in confirmed
        for location in sensitive_locations
        if haversine_metres(
            complaint.latitude,
            complaint.longitude,
            location.latitude,
            location.longitude,
        )
        <= policy.sensitive_location_radius_metres
    }
    unresolved_hours = max(
        0.0,
        (now.astimezone(timezone.utc) - incident.earliest_reported_at.astimezone(timezone.utc)).total_seconds()
        / 3600,
    )
    photo_count = sum(complaint.photo_path is not None for complaint in confirmed)
    evidence_completeness = photo_count / len(confirmed) if confirmed else 0.0
    report_count = incident.report_count
    safety_names = {signal.name for signal in safety_signals}
    has_hospital = any(
        location.id in sensitive_matches and location.kind.casefold() == "hospital"
        for location in sensitive_locations
    )
    signals = (
        _signal(
            "confirmed_report_count",
            str(report_count),
            min(report_count / policy.critical_report_count, 1.0),
            report_count >= policy.medium_report_count,
            ("review candidates are excluded",),
        ),
        _signal(
            "pending_candidate_count",
            str(pending_count),
            float(pending_count),
            False,
            ("candidate evidence is not scored",),
        ),
        _signal(
            "unresolved_hours",
            f"{unresolved_hours:.1f}",
            min(unresolved_hours / policy.critical_unresolved_hours, 1.0),
            unresolved_hours >= policy.high_unresolved_hours,
        ),
        _signal(
            "safety_signal_count",
            str(len(safety_signals)),
            min(float(len(safety_signals)), 1.0),
            bool(safety_signals),
            tuple(signal.name for signal in safety_signals),
        ),
        _signal(
            "sensitive_location_count",
            str(len(sensitive_matches)),
            min(float(len(sensitive_matches)), 1.0),
            bool(sensitive_matches),
        ),
        _signal(
            "evidence_completeness",
            f"{evidence_completeness:.2f}",
            evidence_completeness,
            evidence_completeness >= policy.evidence_completeness_threshold,
            (f"{photo_count}/{report_count} confirmed reports include photos",),
        ),
    )

    if incident.status is ClusteringStatus.CONFLICT:
        conflict_reasons = incident.conflict_reasons or ("confirmed graph has a contradiction",)
        return PriorityAssessment(
            level=PriorityLevel.REVIEW_REQUIRED,
            status=PriorityStatus.REVIEW_REQUIRED,
            points=0,
            confirmed_report_count=report_count,
            pending_candidate_count=pending_count,
            triggered_rules=("clustering_conflict_requires_review",),
            signals=signals,
            reasons=("clustering conflict prevents normal priority assignment", *conflict_reasons),
            policy_version=policy.policy_version,
        )

    levels: list[PriorityLevel] = []
    rules: list[str] = []
    reasons: list[str] = []
    if report_count >= policy.critical_report_count:
        levels.append(PriorityLevel.CRITICAL)
        rules.append("critical_confirmed_report_volume")
        reasons.append(f"{report_count} confirmed reports reached the critical volume threshold")
    elif report_count >= policy.high_report_count:
        levels.append(PriorityLevel.HIGH)
        rules.append("high_confirmed_report_volume")
        reasons.append(f"{report_count} confirmed reports reached the high volume threshold")
    elif report_count >= policy.medium_report_count:
        levels.append(PriorityLevel.MEDIUM)
        rules.append("multi_report_incident")
        reasons.append(f"{report_count} confirmed reports indicate a multi-report incident")

    if unresolved_hours >= policy.critical_unresolved_hours:
        levels.append(PriorityLevel.CRITICAL)
        rules.append("critical_persistence")
        reasons.append(f"incident unresolved for {unresolved_hours:.1f} hours")
    elif unresolved_hours >= policy.high_unresolved_hours:
        levels.append(PriorityLevel.HIGH)
        rules.append("high_persistence")
        reasons.append(f"incident unresolved for {unresolved_hours:.1f} hours")

    if safety_names & set(policy.critical_safety_signals):
        levels.append(PriorityLevel.CRITICAL)
        rules.append("critical_safety_signal")
        reasons.append(f"critical safety signal: {', '.join(sorted(safety_names & set(policy.critical_safety_signals)))}")
    elif safety_names & set(policy.high_safety_signals):
        levels.append(PriorityLevel.HIGH)
        rules.append("high_safety_signal")
        reasons.append(f"safety signal: {', '.join(sorted(safety_names & set(policy.high_safety_signals)))}")
    if "active_flooding" in safety_names and has_hospital:
        levels.append(PriorityLevel.CRITICAL)
        rules.append("flooding_near_hospital")
        reasons.append("active flooding signal is within the configured hospital exposure radius")
    if sensitive_matches:
        levels.append(PriorityLevel.HIGH)
        rules.append("sensitive_location_exposure")
        reasons.append(f"confirmed incident is near {len(sensitive_matches)} sensitive location(s)")
    if not levels:
        rules.append("default_low_priority")
        reasons.append("no configured escalation rule was triggered")

    level = _highest_level(levels)
    points = {PriorityLevel.LOW: 0, PriorityLevel.MEDIUM: 1, PriorityLevel.HIGH: 2, PriorityLevel.CRITICAL: 3}[level]
    if pending_count:
        reasons.append(f"{pending_count} review candidate(s) pending; excluded from priority")
    if evidence_completeness >= policy.evidence_completeness_threshold:
        reasons.append(f"evidence completeness is {evidence_completeness:.2f}; this is informational only")
    return PriorityAssessment(
        level=level,
        status=PriorityStatus.SCORED,
        points=points,
        confirmed_report_count=report_count,
        pending_candidate_count=pending_count,
        triggered_rules=tuple(rules),
        signals=signals,
        reasons=tuple(reasons),
        policy_version=policy.policy_version,
    )
