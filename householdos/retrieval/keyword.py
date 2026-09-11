"""Small controlled retrieval layer with provenance and permission filtering."""

from __future__ import annotations

import json
import re
from pathlib import Path

from householdos.domain.capstone import EvidenceBundle, EvidenceItem


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.casefold()))


class KeywordKnowledgeRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def search(
        self,
        query: str,
        domains: list[str],
        allowed_sensitivities: set[str] | None = None,
        limit: int = 4,
    ) -> EvidenceBundle:
        allowed = allowed_sensitivities or {"Public", "Household", "Church admin"}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        query_tokens = _tokens(query)
        candidates: list[EvidenceItem] = []
        for raw in payload:
            if raw["domain"] not in domains or raw["sensitivity"] not in allowed:
                continue
            document_tokens = _tokens(f"{raw['title']} {raw['excerpt']}")
            overlap = len(query_tokens & document_tokens)
            score = overlap / max(1, len(query_tokens))
            if overlap or not query_tokens:
                candidates.append(EvidenceItem(**raw, relevance_score=min(1.0, score)))
        candidates.sort(key=lambda item: (item.relevance_score, item.timestamp), reverse=True)
        selected: list[EvidenceItem] = []
        seen_sources: set[str] = set()
        for item in candidates:
            if item.source_id in seen_sources:
                continue
            selected.append(item)
            seen_sources.add(item.source_id)
            if len(selected) >= min(limit, 4):
                break
        found_domains = {item.domain for item in selected}
        return EvidenceBundle(
            query=query,
            items=selected,
            missing_domains=[domain for domain in domains if domain not in found_domains],
        )

