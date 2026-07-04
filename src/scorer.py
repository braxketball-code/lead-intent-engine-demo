from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod

from .models import Lead, ScoredLead

TIER_THRESHOLDS = {"hot": 75, "warm": 50, "cool": 25}


def score_to_tier(score: int) -> str:
    if score >= TIER_THRESHOLDS["hot"]:
        return "hot"
    if score >= TIER_THRESHOLDS["warm"]:
        return "warm"
    if score >= TIER_THRESHOLDS["cool"]:
        return "cool"
    return "cold"


def action_for_tier(tier: str, vertical: str) -> str:
    actions = {
        "hot": "Immediate alert → assign agent + send personalized follow-up within 15 min",
        "warm": "Queue for nurture sequence + schedule callback within 24h",
        "cool": "Add to drip campaign; review weekly",
        "cold": "Archive; no active outreach",
    }
    base = actions[tier]
    if vertical == "real_estate" and tier == "hot":
        return base + " + push to CRM with showing scheduler link"
    if vertical == "medical" and tier == "hot":
        return base + " + route to Instantly/GoHighLevel hot-lead pipeline"
    return base


class BaseScorer(ABC):
    @abstractmethod
    def score(self, lead: Lead) -> ScoredLead:
        raise NotImplementedError


class RuleBasedScorer(BaseScorer):
    """Deterministic scorer for demos and offline testing."""

    URGENCY_WORDS = (
        "asap",
        "urgent",
        "this week",
        "60 days",
        "90 days",
        "pre-approved",
        "pre approved",
        "closing",
        "budget approved",
        "fixed price",
        "hiring",
    )
    LOW_INTENT_WORDS = ("curious", "maybe", "someday", "just looking", "how much")

    def score(self, lead: Lead) -> ScoredLead:
        score = 30
        tags: list[str] = []
        reasons: list[str] = []

        if lead.email:
            score += 12
            tags.append("has_email")
        if lead.phone:
            score += 10
            tags.append("has_phone")

        message_lower = lead.message.lower()
        for word in self.URGENCY_WORDS:
            if word in message_lower:
                score += 8
                tags.append("urgency_signal")
                reasons.append(f"Urgency signal: '{word}'")
                break

        for word in self.LOW_INTENT_WORDS:
            if word in message_lower:
                score -= 15
                tags.append("low_intent")
                reasons.append(f"Low-intent phrase: '{word}'")
                break

        meta = lead.metadata
        if meta.get("pre_approved"):
            score += 15
            tags.append("pre_approved")
            reasons.append("Buyer is pre-approved")
        if meta.get("budget_fixed") and meta["budget_fixed"] >= 500:
            score += 12
            reasons.append(f"Fixed budget ${meta['budget_fixed']}")
        if meta.get("budget_max") and meta["budget_max"] >= 400000:
            score += 10
            reasons.append("High purchase budget")
        if meta.get("monthly_ad_budget") and meta["monthly_ad_budget"] >= 2000:
            score += 12
            reasons.append("Meaningful ad spend indicates budget")
        if meta.get("weekly_leads") and meta["weekly_leads"] >= 100:
            score += 10
            reasons.append("High lead volume = strong automation ROI")
        if meta.get("budget_range"):
            score += 14
            reasons.append(f"Approved budget range: {meta['budget_range']}")
        if meta.get("urgency") == "this_week":
            score += 10
            tags.append("this_week")

        if not lead.email and not lead.phone:
            score -= 20
            reasons.append("Missing contact info")

        if len(lead.message) < 20:
            score -= 10
            reasons.append("Very short message")

        score = max(0, min(100, score))
        tier = score_to_tier(score)
        reasoning = "; ".join(reasons) if reasons else "Baseline qualification from contact + message signals"

        return ScoredLead(
            lead=lead,
            score=score,
            tier=tier,
            reasoning=reasoning,
            recommended_action=action_for_tier(tier, lead.vertical),
            tags=sorted(set(tags)),
        )


class LLMScorer(BaseScorer):
    """Optional LLM scorer — uses OpenAI or xAI when API key is set."""

    def __init__(self, provider: str = "openai", model: str | None = None):
        self.provider = provider
        self.model = model or ("grok-3-mini" if provider == "xai" else "gpt-4o-mini")
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client

        if self.provider == "xai":
            from openai import OpenAI

            api_key = os.environ.get("XAI_API_KEY")
            if not api_key:
                raise ValueError("XAI_API_KEY not set")
            self._client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
        else:
            from openai import OpenAI

            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set")
            self._client = OpenAI(api_key=api_key)

        return self._client

    def score(self, lead: Lead) -> ScoredLead:
        prompt = f"""Score this lead 0-100 for sales intent and fit.
Return JSON only: {{"score": int, "tier": "hot|warm|cool|cold", "reasoning": "one sentence", "tags": ["tag1"]}}

Lead:
- ID: {lead.id}
- Vertical: {lead.vertical}
- Source: {lead.source}
- Name: {lead.name}
- Email: {lead.email or "none"}
- Phone: {lead.phone or "none"}
- Message: {lead.message}
- Metadata: {json.dumps(lead.metadata)}
"""
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a lead qualification engine. Respond with valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        raw = response.choices[0].message.content or "{}"
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError(f"LLM returned non-JSON: {raw[:200]}")

        data = json.loads(match.group())
        score = int(data.get("score", 50))
        tier = data.get("tier") or score_to_tier(score)

        return ScoredLead(
            lead=lead,
            score=score,
            tier=tier,
            reasoning=data.get("reasoning", "LLM qualification"),
            recommended_action=action_for_tier(tier, lead.vertical),
            tags=data.get("tags", []),
        )


def get_scorer(mode: str | None = None) -> BaseScorer:
    mode = (mode or os.environ.get("SCORER_MODE", "rules")).lower()
    if mode in ("openai", "gpt"):
        return LLMScorer(provider="openai")
    if mode == "xai":
        return LLMScorer(provider="xai")
    return RuleBasedScorer()
