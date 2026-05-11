from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

from app.agents.classifier import ClassificationResult
from app.config.models import KBArticle, KnowledgeIndexConfig

# Default location of KB markdown files relative to this module.
_DEFAULT_KB_DIR = Path(__file__).parent.parent.parent / "config" / "knowledge"

# Score weights.
_COMPONENT_MATCH_SCORE: float = 0.30
_TAG_MATCH_SCORE: float = 0.10
_TAG_SCORE_CAP: float = 0.50

# Number of characters to extract as the article excerpt.
_EXCERPT_CHARS: int = 400


# ── Public types ──────────────────────────────────────────────────────────────

@dataclass
class KBMatch:
    """A knowledge base article that meets the minimum confidence threshold."""
    article_id: str
    title: str
    file: str
    confidence_score: float
    source_metadata: dict
    excerpt: str


@dataclass
class NoMatchResult:
    """Returned when no article meets its minimum confidence threshold."""
    reason: str
    best_score: float


KnowledgeRetrievalResult = Union[KBMatch, NoMatchResult]


# ── Retriever ─────────────────────────────────────────────────────────────────

class KnowledgeRetriever:
    """
    Deterministic keyword-, tag-, and component-based KB retriever.

    No vector database, no LLM, no live signals.
    Tenant boundaries are respected: KB articles in this prototype are
    authoritative Modelyo runbooks (PUBLIC/INTERNAL scope) — they contain no
    customer-specific data, so no tenant filter is required on the article set.
    Customer ticket history (which IS tenant-scoped) is not included as a
    knowledge source in this prototype (FR-28 / Phase 7 scope).
    """

    def __init__(
        self,
        knowledge_index: KnowledgeIndexConfig,
        kb_dir: Optional[Path] = None,
    ) -> None:
        self._index = knowledge_index
        self._kb_dir = Path(kb_dir) if kb_dir is not None else _DEFAULT_KB_DIR
        self._content_cache: dict[str, str] = {}

    def retrieve(
        self,
        query: str,
        classification: ClassificationResult,
    ) -> KnowledgeRetrievalResult:
        """
        Search the knowledge index and return the best-matching article.

        Returns KBMatch if an article exceeds its min_confidence threshold,
        otherwise NoMatchResult.
        """
        query_lower = query.lower()
        query_tokens = set(re.findall(r"[a-z0-9]+", query_lower))

        best_article: Optional[KBArticle] = None
        best_score: float = 0.0

        for article in self._index.articles:
            score = self._score_article(article, query_lower, query_tokens, classification)
            if score > best_score:
                best_score = score
                best_article = article

        if best_article is None or best_score < best_article.min_confidence:
            threshold = best_article.min_confidence if best_article else 0.0
            return NoMatchResult(
                reason=(
                    f"No article met its minimum confidence threshold "
                    f"(best score {best_score:.2f}, required {threshold:.2f})"
                ),
                best_score=round(best_score, 4),
            )

        content = self._load_article(best_article)
        excerpt = self._extract_excerpt(content, query_tokens)

        return KBMatch(
            article_id=best_article.id,
            title=best_article.title,
            file=best_article.file,
            confidence_score=round(best_score, 4),
            source_metadata={
                "article_id": best_article.id,
                "file": best_article.file,
                "tags": best_article.components,
                "min_confidence": best_article.min_confidence,
            },
            excerpt=excerpt,
        )

    # ── Scoring ───────────────────────────────────────────────────────────────

    def _score_article(
        self,
        article: KBArticle,
        query_lower: str,
        query_tokens: set[str],
        classification: ClassificationResult,
    ) -> float:
        score = 0.0

        # Component match bonus.
        if classification.component in article.components:
            score += _COMPONENT_MATCH_SCORE

        # Tag match: each tag that appears in the query adds to the score.
        tag_score = 0.0
        for tag in article.tags:
            tag_lower = tag.lower()
            # Match whole-word tag or tag as substring of a query token.
            if tag_lower in query_tokens or tag_lower in query_lower:
                tag_score += _TAG_MATCH_SCORE
        score += min(tag_score, _TAG_SCORE_CAP)

        return min(score, 1.0)

    # ── Content loading ───────────────────────────────────────────────────────

    def _load_article(self, article: KBArticle) -> str:
        if article.id not in self._content_cache:
            path = self._kb_dir / article.file
            try:
                self._content_cache[article.id] = path.read_text(encoding="utf-8")
            except OSError:
                self._content_cache[article.id] = f"[Content unavailable: {article.file}]"
        return self._content_cache[article.id]

    def _extract_excerpt(self, content: str, query_tokens: set[str]) -> str:
        """
        Return a short excerpt from the article.

        Prefers a paragraph that contains a query token; falls back to the
        first substantive paragraph if no match is found.
        """
        # Strip markdown headers and code fences for cleaner excerpts.
        lines = [
            ln for ln in content.splitlines()
            if ln.strip() and not ln.strip().startswith("#")
            and not ln.strip().startswith("```")
        ]

        # Try to find the first line that overlaps with query tokens.
        for line in lines:
            line_tokens = set(re.findall(r"[a-z0-9]+", line.lower()))
            if query_tokens & line_tokens:
                # Return from this line onward, up to _EXCERPT_CHARS.
                idx = content.find(line)
                snippet = content[idx: idx + _EXCERPT_CHARS]
                return snippet.strip()

        # Fall back to first _EXCERPT_CHARS of non-header content.
        plain = "\n".join(lines)
        return plain[:_EXCERPT_CHARS].strip()
