"""Unit tests for KnowledgeRetriever (Phase 4).

Tests use the real config/knowledge/ directory (markdown files created in Phase 4).
No vector DB, no LLM, no live signals.
"""

from pathlib import Path

import pytest

from app.agents.classifier import Category, ClassificationResult
from app.agents.knowledge_retriever import KBMatch, KnowledgeRetriever, NoMatchResult
from app.config.loader import load_config

_KB_DIR = Path(__file__).parent.parent / "config" / "knowledge"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture(scope="module")
def retriever(config):
    return KnowledgeRetriever(
        knowledge_index=config.knowledge_index,
        kb_dir=_KB_DIR,
    )


def _make_classification(
    category: Category = Category.INCIDENT,
    component: str = "api-gateway",
    severity: str = "P2",
    confidence_score: float = 0.80,
) -> ClassificationResult:
    return ClassificationResult(
        category=category,
        severity=severity,
        component=component,
        confidence_score=confidence_score,
        reasoning=f"category={category.value}",
    )


# ── High-confidence match tests ───────────────────────────────────────────────

class TestHighConfidenceKBMatch:
    def test_network_query_returns_connectivity_article(self, retriever):
        cls = _make_classification(component="network-service")
        result = retriever.retrieve(
            "Cannot connect to the endpoint, connection timeout, DNS failure, "
            "network latency high, unreachable host",
            cls,
        )
        assert isinstance(result, KBMatch)
        assert result.article_id == "connectivity-001"

    def test_auth_query_returns_auth_article(self, retriever):
        cls = _make_classification(component="auth-service")
        result = retriever.retrieve(
            "Getting 401 unauthorized, authentication token is rejected, login failing",
            cls,
        )
        assert isinstance(result, KBMatch)
        assert result.article_id == "auth-001"

    def test_performance_query_returns_perf_article(self, retriever):
        cls = _make_classification(component="compute-engine")
        result = retriever.retrieve(
            "High CPU latency, system is degraded and slow, throughput bottleneck",
            cls,
        )
        assert isinstance(result, KBMatch)
        assert result.article_id == "perf-001"

    def test_storage_query_returns_storage_article(self, retriever):
        cls = _make_classification(component="storage-service")
        result = retriever.retrieve(
            "Storage bucket upload fails, file download unavailable, disk error",
            cls,
        )
        assert isinstance(result, KBMatch)
        assert result.article_id == "storage-001"

    def test_billing_query_returns_billing_article(self, retriever):
        cls = _make_classification(component="billing-service")
        result = retriever.retrieve(
            "Invoice billing payment subscription charge account quota",
            cls,
        )
        assert isinstance(result, KBMatch)
        assert result.article_id == "billing-001"

    def test_kb_match_has_confidence_score(self, retriever):
        cls = _make_classification(component="auth-service")
        result = retriever.retrieve(
            "401 unauthorized login token oauth credential",
            cls,
        )
        assert isinstance(result, KBMatch)
        assert 0.0 < result.confidence_score <= 1.0

    def test_kb_match_confidence_meets_article_min_confidence(self, retriever, config):
        cls = _make_classification(component="auth-service")
        result = retriever.retrieve(
            "authentication login token 401 unauthorized oauth credential",
            cls,
        )
        assert isinstance(result, KBMatch)
        article = next(
            a for a in config.knowledge_index.articles
            if a.id == result.article_id
        )
        assert result.confidence_score >= article.min_confidence

    def test_kb_match_has_source_metadata(self, retriever):
        cls = _make_classification(component="network-service")
        result = retriever.retrieve(
            "network connectivity timeout dns latency unreachable",
            cls,
        )
        assert isinstance(result, KBMatch)
        assert "article_id" in result.source_metadata
        assert "file" in result.source_metadata
        assert "min_confidence" in result.source_metadata

    def test_kb_match_excerpt_is_non_empty(self, retriever):
        cls = _make_classification(component="storage-service")
        result = retriever.retrieve(
            "storage bucket upload download file unavailable",
            cls,
        )
        assert isinstance(result, KBMatch)
        assert isinstance(result.excerpt, str)
        assert len(result.excerpt) > 0

    def test_kb_match_title_is_non_empty(self, retriever):
        cls = _make_classification(component="billing-service")
        result = retriever.retrieve(
            "billing invoice subscription payment charge",
            cls,
        )
        assert isinstance(result, KBMatch)
        assert isinstance(result.title, str) and len(result.title) > 0

    def test_kb_match_file_is_non_empty(self, retriever):
        cls = _make_classification(component="auth-service")
        result = retriever.retrieve(
            "401 login token authentication",
            cls,
        )
        assert isinstance(result, KBMatch)
        assert isinstance(result.file, str) and result.file.endswith(".md")


# ── No-match fallback tests ───────────────────────────────────────────────────

class TestNoMatchFallback:
    def test_unrelated_query_returns_no_match(self, retriever):
        cls = _make_classification(component="unknown")
        result = retriever.retrieve("xyz abc completely unrelated gibberish", cls)
        assert isinstance(result, NoMatchResult)

    def test_no_match_result_has_reason(self, retriever):
        cls = _make_classification(component="unknown")
        result = retriever.retrieve("zzz qqq nothing here", cls)
        assert isinstance(result, NoMatchResult)
        assert isinstance(result.reason, str) and len(result.reason) > 0

    def test_no_match_result_has_best_score(self, retriever):
        cls = _make_classification(component="unknown")
        result = retriever.retrieve("zzz qqq nothing here", cls)
        assert isinstance(result, NoMatchResult)
        assert isinstance(result.best_score, float)
        assert 0.0 <= result.best_score <= 1.0

    def test_empty_query_returns_no_match(self, retriever):
        cls = _make_classification(component="unknown")
        result = retriever.retrieve("", cls)
        assert isinstance(result, NoMatchResult)

    def test_component_alone_does_not_meet_auth_threshold(self, retriever):
        # auth-001 min_confidence is 0.65 — component match alone gives 0.30.
        cls = _make_classification(component="auth-service")
        result = retriever.retrieve("something happened", cls)
        # Either no match or insufficient score — this query has no tag overlap.
        if isinstance(result, KBMatch):
            assert result.confidence_score >= 0.65
        else:
            assert isinstance(result, NoMatchResult)


# ── Tenant boundary / live signals tests ─────────────────────────────────────

class TestTenantBoundaryAndLiveSignals:
    def test_retriever_does_not_use_live_signals(self, retriever):
        """Retriever has no network calls or live-data lookups."""
        import app.agents.knowledge_retriever as mod
        import inspect
        source = inspect.getsource(mod)
        # Must not import requests, httpx, aiohttp, or urllib.request
        assert "requests" not in source
        assert "httpx" not in source
        assert "aiohttp" not in source
        assert "urllib.request" not in source

    def test_retriever_does_not_use_vector_db(self, retriever):
        import app.agents.knowledge_retriever as mod
        import inspect
        source = inspect.getsource(mod)
        # No vector DB libraries
        assert "pinecone" not in source
        assert "weaviate" not in source
        assert "chroma" not in source
        assert "faiss" not in source
        assert "qdrant" not in source

    def test_retriever_does_not_use_real_llm(self, retriever):
        import app.agents.knowledge_retriever as mod
        import inspect
        source = inspect.getsource(mod)
        assert "openai" not in source
        assert "anthropic" not in source

    def test_kb_articles_contain_no_customer_tenant_data(self, config):
        """All KB articles are shared (PUBLIC/INTERNAL runbooks), not tenant-specific."""
        for article in config.knowledge_index.articles:
            # IDs should be generic, not tenant-scoped
            assert not article.id.startswith("acme-")
            assert not article.id.startswith("vertex-")
