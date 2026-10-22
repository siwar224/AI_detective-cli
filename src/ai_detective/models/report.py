"""Validated output contract for an investigation report."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ai_detective.models.analysis import DeterministicAnalysis, TimelineEvent

Confidence = Literal["low", "medium", "high"]


class EvidenceReference(BaseModel):
    """A claim linked to an exact source line."""

    line_number: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=500)


class Hypothesis(BaseModel):
    """A possible cause with explicit support and uncertainty."""

    cause: str = Field(min_length=1, max_length=500)
    confidence: Confidence
    supporting_evidence: list[EvidenceReference] = Field(default_factory=list)
    contradicting_evidence: list[EvidenceReference] = Field(default_factory=list)
    recommended_checks: list[str] = Field(default_factory=list, max_length=5)


class InvestigationDraft(BaseModel):
    """Model-produced part of a report; deterministic facts are injected by Python."""

    incident_summary: str = Field(min_length=1, max_length=2000)
    hypotheses: list[Hypothesis] = Field(default_factory=list, max_length=3)
    recommendations: list[str] = Field(default_factory=list, max_length=10)
    limitations: list[str] = Field(default_factory=list, max_length=20)


class InvestigationReport(BaseModel):
    """Final report shared by deterministic and AI-assisted execution."""

    incident_summary: str = Field(min_length=1, max_length=2000)
    statistics: DeterministicAnalysis
    timeline: list[TimelineEvent]
    hypotheses: list[Hypothesis] = Field(default_factory=list, max_length=3)
    recommendations: list[str] = Field(default_factory=list, max_length=10)
    limitations: list[str] = Field(default_factory=list, max_length=20)
