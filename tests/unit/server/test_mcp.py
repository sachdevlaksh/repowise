"""Unit tests for WikiCode MCP server tools.

Tests all 16 MCP tools using an in-memory SQLite database with pre-populated
test data, mirroring the conftest pattern from the REST API tests.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from wikicode.core.persistence.database import init_db
from wikicode.core.persistence.embedder import MockEmbedder
from wikicode.core.persistence.models import (
    DeadCodeFinding,
    GitMetadata,
    GraphEdge,
    GraphNode,
    Page,
    Repository,
    WikiSymbol,
)
from wikicode.core.persistence.search import FullTextSearch
from wikicode.core.persistence.vector_store import InMemoryVectorStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 3, 19, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    await init_db(eng)
    yield eng
    await eng.dispose()


@pytest.fixture
async def factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture
async def session(factory):
    async with factory() as s:
        yield s
        await s.commit()


@pytest.fixture
async def fts(engine):
    f = FullTextSearch(engine)
    await f.ensure_index()
    return f


@pytest.fixture
async def vector_store():
    embedder = MockEmbedder()
    vs = InMemoryVectorStore(embedder=embedder)
    yield vs
    await vs.close()


@pytest.fixture
async def repo_id(session: AsyncSession) -> str:
    """Create a test repository and return its ID."""
    repo = Repository(
        id="repo1",
        name="test-repo",
        url="https://github.com/example/test-repo",
        local_path="/tmp/test-repo",
        default_branch="main",
        settings_json="{}",
        created_at=_NOW,
        updated_at=_NOW,
    )
    session.add(repo)
    await session.flush()
    return repo.id


@pytest.fixture
async def populated_db(session: AsyncSession, repo_id: str) -> str:
    """Populate the database with test data for all MCP tools."""
    rid = repo_id

    # ---- Pages ----
    pages = [
        Page(
            id="repo_overview:test-repo",
            repository_id=rid,
            page_type="repo_overview",
            title="Test Repo Overview",
            content="# Test Repo\n\nA comprehensive test repository.",
            target_path="test-repo",
            source_hash="abc123",
            model_name="mock",
            provider_name="mock",
            generation_level=6,
            confidence=1.0,
            freshness_status="fresh",
            metadata_json="{}",
            created_at=_NOW,
            updated_at=_NOW,
        ),
        Page(
            id="architecture_diagram:test-repo",
            repository_id=rid,
            page_type="architecture_diagram",
            title="Architecture Diagram",
            content="graph TD\n    A[Main] --> B[Auth]\n    A --> C[DB]",
            target_path="test-repo",
            source_hash="abc124",
            model_name="mock",
            provider_name="mock",
            generation_level=6,
            confidence=1.0,
            freshness_status="fresh",
            metadata_json="{}",
            created_at=_NOW,
            updated_at=_NOW,
        ),
        Page(
            id="module_page:src/auth",
            repository_id=rid,
            page_type="module_page",
            title="Auth Module",
            content="# Auth Module\n\nHandles authentication and authorization.",
            target_path="src/auth",
            source_hash="mod1",
            model_name="mock",
            provider_name="mock",
            generation_level=4,
            confidence=0.95,
            freshness_status="fresh",
            metadata_json="{}",
            created_at=_NOW,
            updated_at=_NOW,
        ),
        Page(
            id="module_page:src/db",
            repository_id=rid,
            page_type="module_page",
            title="Database Module",
            content="# Database Module\n\nDatabase access and ORM layer.",
            target_path="src/db",
            source_hash="mod2",
            model_name="mock",
            provider_name="mock",
            generation_level=4,
            confidence=0.90,
            freshness_status="fresh",
            metadata_json="{}",
            created_at=_NOW,
            updated_at=_NOW,
        ),
        Page(
            id="file_page:src/auth/service.py",
            repository_id=rid,
            page_type="file_page",
            title="Auth Service",
            content="# AuthService\n\nMain authentication service class.",
            target_path="src/auth/service.py",
            source_hash="file1",
            model_name="mock",
            provider_name="mock",
            generation_level=2,
            confidence=0.85,
            freshness_status="fresh",
            metadata_json="{}",
            created_at=_NOW,
            updated_at=_NOW,
        ),
        Page(
            id="file_page:src/auth/middleware.py",
            repository_id=rid,
            page_type="file_page",
            title="Auth Middleware",
            content="# Auth Middleware\n\nRequest authentication middleware.",
            target_path="src/auth/middleware.py",
            source_hash="file2",
            model_name="mock",
            provider_name="mock",
            generation_level=2,
            confidence=0.50,
            freshness_status="stale",
            metadata_json="{}",
            created_at=_NOW,
            updated_at=_NOW,
        ),
        Page(
            id="file_page:src/db/models.py",
            repository_id=rid,
            page_type="file_page",
            title="DB Models",
            content="# Database Models\n\nSQLAlchemy ORM models.",
            target_path="src/db/models.py",
            source_hash="file3",
            model_name="mock",
            provider_name="mock",
            generation_level=2,
            confidence=0.40,
            freshness_status="stale",
            metadata_json="{}",
            created_at=_NOW,
            updated_at=_NOW,
        ),
    ]
    for p in pages:
        session.add(p)

    # ---- Symbols ----
    symbols = [
        WikiSymbol(
            id="sym1",
            repository_id=rid,
            file_path="src/auth/service.py",
            symbol_id="src/auth/service.py::AuthService",
            name="AuthService",
            qualified_name="auth.service.AuthService",
            kind="class",
            signature="class AuthService",
            start_line=10,
            end_line=100,
            docstring="Main authentication service.",
            visibility="public",
            is_async=False,
            complexity_estimate=15,
            language="python",
            parent_name=None,
            created_at=_NOW,
            updated_at=_NOW,
        ),
        WikiSymbol(
            id="sym2",
            repository_id=rid,
            file_path="src/auth/service.py",
            symbol_id="src/auth/service.py::login",
            name="login",
            qualified_name="auth.service.AuthService.login",
            kind="method",
            signature="async def login(self, username: str, password: str) -> Token",
            start_line=20,
            end_line=40,
            docstring="Authenticate a user.",
            visibility="public",
            is_async=True,
            complexity_estimate=5,
            language="python",
            parent_name="AuthService",
            created_at=_NOW,
            updated_at=_NOW,
        ),
        WikiSymbol(
            id="sym3",
            repository_id=rid,
            file_path="src/db/models.py",
            symbol_id="src/db/models.py::User",
            name="User",
            qualified_name="db.models.User",
            kind="class",
            signature="class User(Base)",
            start_line=5,
            end_line=30,
            docstring="User ORM model.",
            visibility="public",
            is_async=False,
            complexity_estimate=2,
            language="python",
            parent_name=None,
            created_at=_NOW,
            updated_at=_NOW,
        ),
    ]
    for s in symbols:
        session.add(s)

    # ---- Graph Nodes ----
    nodes = [
        GraphNode(
            id="gn1",
            repository_id=rid,
            node_id="src/auth/service.py",
            node_type="file",
            language="python",
            symbol_count=2,
            is_entry_point=True,
            pagerank=0.85,
            betweenness=0.5,
            community_id=1,
            created_at=_NOW,
        ),
        GraphNode(
            id="gn2",
            repository_id=rid,
            node_id="src/auth/middleware.py",
            node_type="file",
            language="python",
            symbol_count=1,
            is_entry_point=False,
            pagerank=0.4,
            betweenness=0.2,
            community_id=1,
            created_at=_NOW,
        ),
        GraphNode(
            id="gn3",
            repository_id=rid,
            node_id="src/db/models.py",
            node_type="file",
            language="python",
            symbol_count=1,
            is_entry_point=False,
            pagerank=0.6,
            betweenness=0.3,
            community_id=2,
            created_at=_NOW,
        ),
    ]
    for n in nodes:
        session.add(n)

    # ---- Graph Edges ----
    edges = [
        GraphEdge(
            id="ge1",
            repository_id=rid,
            source_node_id="src/auth/service.py",
            target_node_id="src/db/models.py",
            imported_names_json='["User"]',
            created_at=_NOW,
        ),
        GraphEdge(
            id="ge2",
            repository_id=rid,
            source_node_id="src/auth/middleware.py",
            target_node_id="src/auth/service.py",
            imported_names_json='["AuthService"]',
            created_at=_NOW,
        ),
    ]
    for e in edges:
        session.add(e)

    # ---- Git Metadata ----
    git_metas = [
        GitMetadata(
            id="gm1",
            repository_id=rid,
            file_path="src/auth/service.py",
            commit_count_total=42,
            commit_count_90d=8,
            commit_count_30d=3,
            first_commit_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            last_commit_at=datetime(2026, 3, 15, tzinfo=timezone.utc),
            primary_owner_name="Alice",
            primary_owner_email="alice@example.com",
            primary_owner_commit_pct=0.65,
            top_authors_json=json.dumps([
                {"name": "Alice", "count": 27},
                {"name": "Bob", "count": 15},
            ]),
            significant_commits_json=json.dumps([
                {"sha": "abc1234", "date": "2026-03-15", "message": "Refactor auth flow", "author": "Alice"},
                {"sha": "def5678", "date": "2026-02-10", "message": "Add JWT support", "author": "Bob"},
            ]),
            co_change_partners_json=json.dumps([
                {"file_path": "src/auth/middleware.py", "count": 5},
                {"file_path": "src/db/models.py", "count": 3},
            ]),
            is_hotspot=True,
            is_stable=False,
            churn_percentile=0.92,
            age_days=443,
            created_at=_NOW,
            updated_at=_NOW,
        ),
        GitMetadata(
            id="gm2",
            repository_id=rid,
            file_path="src/db/models.py",
            commit_count_total=15,
            commit_count_90d=0,
            commit_count_30d=0,
            first_commit_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            last_commit_at=datetime(2025, 9, 1, tzinfo=timezone.utc),
            primary_owner_name="Bob",
            primary_owner_email="bob@example.com",
            primary_owner_commit_pct=0.90,
            top_authors_json=json.dumps([{"name": "Bob", "count": 13}]),
            significant_commits_json=json.dumps([
                {"sha": "111aaa", "date": "2025-09-01", "message": "Add migration helper", "author": "Bob"},
            ]),
            co_change_partners_json=json.dumps([
                {"file_path": "src/auth/service.py", "count": 3},
            ]),
            is_hotspot=False,
            is_stable=True,
            churn_percentile=0.15,
            age_days=443,
            created_at=_NOW,
            updated_at=_NOW,
        ),
    ]
    for g in git_metas:
        session.add(g)

    # ---- Dead Code Findings ----
    findings = [
        DeadCodeFinding(
            id="dc1",
            repository_id=rid,
            kind="unreachable_file",
            file_path="src/legacy/old_auth.py",
            symbol_name=None,
            symbol_kind=None,
            confidence=0.9,
            reason="No imports found; file not referenced by any other module",
            lines=150,
            safe_to_delete=True,
            primary_owner="Alice",
            age_days=365,
            status="open",
            analyzed_at=_NOW,
        ),
        DeadCodeFinding(
            id="dc2",
            repository_id=rid,
            kind="unused_export",
            file_path="src/auth/service.py",
            symbol_name="deprecated_login",
            symbol_kind="function",
            confidence=0.7,
            reason="Exported but no external callers found",
            lines=20,
            safe_to_delete=True,
            primary_owner="Bob",
            age_days=120,
            status="open",
            analyzed_at=_NOW,
        ),
        DeadCodeFinding(
            id="dc3",
            repository_id=rid,
            kind="unused_export",
            file_path="src/db/models.py",
            symbol_name="OldModel",
            symbol_kind="class",
            confidence=0.5,
            reason="Exported but no external callers found",
            lines=40,
            safe_to_delete=False,
            primary_owner="Bob",
            age_days=200,
            status="open",
            analyzed_at=_NOW,
        ),
    ]
    for f in findings:
        session.add(f)

    await session.flush()
    return rid


# ---------------------------------------------------------------------------
# MCP tool tests
# ---------------------------------------------------------------------------


@pytest.fixture
async def setup_mcp(factory, fts, vector_store, populated_db):
    """Configure the MCP module's global state for testing."""
    import wikicode.server.mcp_server as mcp_mod

    mcp_mod._session_factory = factory
    mcp_mod._fts = fts
    mcp_mod._vector_store = vector_store
    mcp_mod._repo_path = "/tmp/test-repo"

    yield populated_db

    # Reset globals
    mcp_mod._session_factory = None
    mcp_mod._fts = None
    mcp_mod._vector_store = None
    mcp_mod._repo_path = None


# ---- Tool 1: get_overview ----


@pytest.mark.asyncio
async def test_get_overview(setup_mcp):
    from wikicode.server.mcp_server import get_overview

    result = await get_overview()
    assert result["title"] == "Test Repo Overview"
    assert "comprehensive test" in result["content_md"]
    assert result["architecture_diagram_mermaid"] is not None
    assert "graph TD" in result["architecture_diagram_mermaid"]
    assert len(result["key_modules"]) == 2
    assert any(m["name"] == "Auth Module" for m in result["key_modules"])
    assert "src/auth/service.py" in result["entry_points"]


@pytest.mark.asyncio
async def test_get_overview_with_repo_path(setup_mcp):
    from wikicode.server.mcp_server import get_overview

    result = await get_overview(repo="/tmp/test-repo")
    assert result["title"] == "Test Repo Overview"


@pytest.mark.asyncio
async def test_get_overview_repo_not_found(setup_mcp):
    from wikicode.server.mcp_server import get_overview

    with pytest.raises(LookupError, match="not found"):
        await get_overview(repo="/nonexistent")


# ---- Tool 2: get_module_docs ----


@pytest.mark.asyncio
async def test_get_module_docs(setup_mcp):
    from wikicode.server.mcp_server import get_module_docs

    result = await get_module_docs("src/auth")
    assert result["title"] == "Auth Module"
    assert "authentication" in result["content_md"].lower()
    assert len(result["files"]) == 2  # service.py and middleware.py
    assert result["public_api_summary"]


@pytest.mark.asyncio
async def test_get_module_docs_not_found(setup_mcp):
    from wikicode.server.mcp_server import get_module_docs

    result = await get_module_docs("src/nonexistent")
    assert "error" in result


# ---- Tool 3: get_file_docs ----


@pytest.mark.asyncio
async def test_get_file_docs(setup_mcp):
    from wikicode.server.mcp_server import get_file_docs

    result = await get_file_docs("src/auth/service.py")
    assert result["title"] == "Auth Service"
    assert "AuthService" in result["content_md"]
    assert len(result["symbols"]) == 2
    assert any(s["name"] == "AuthService" for s in result["symbols"])
    assert any(s["name"] == "login" for s in result["symbols"])
    assert "src/auth/middleware.py" in result["imported_by"]
    assert result["confidence_score"] == 0.85
    assert result["freshness_status"] == "fresh"


@pytest.mark.asyncio
async def test_get_file_docs_not_found(setup_mcp):
    from wikicode.server.mcp_server import get_file_docs

    result = await get_file_docs("src/nonexistent.py")
    assert "error" in result


# ---- Tool 4: get_symbol ----


@pytest.mark.asyncio
async def test_get_symbol_exact_match(setup_mcp):
    from wikicode.server.mcp_server import get_symbol

    result = await get_symbol("AuthService")
    assert result["name"] == "AuthService"
    assert result["kind"] == "class"
    assert result["file_path"] == "src/auth/service.py"
    assert result["signature"] == "class AuthService"
    assert result["documentation"]  # Has content from page


@pytest.mark.asyncio
async def test_get_symbol_fuzzy_match(setup_mcp):
    from wikicode.server.mcp_server import get_symbol

    result = await get_symbol("Auth")  # Partial match
    assert result["name"] == "AuthService"


@pytest.mark.asyncio
async def test_get_symbol_with_kind(setup_mcp):
    from wikicode.server.mcp_server import get_symbol

    result = await get_symbol("login", kind="method")
    assert result["name"] == "login"
    assert result["kind"] == "method"


@pytest.mark.asyncio
async def test_get_symbol_not_found(setup_mcp):
    from wikicode.server.mcp_server import get_symbol

    result = await get_symbol("NonExistentSymbol123")
    assert "error" in result


# ---- Tool 5: search_codebase ----


@pytest.mark.asyncio
async def test_search_codebase(setup_mcp):
    from wikicode.server.mcp_server import search_codebase

    # Index pages in the MCP module's vector store (which is the InMemoryVectorStore)
    import wikicode.server.mcp_server as mcp_mod

    await mcp_mod._vector_store.embed_and_upsert(
        "file_page:src/auth/service.py",
        "Auth Service — Main authentication service class",
        {"title": "Auth Service", "page_type": "file_page", "target_path": "src/auth/service.py"},
    )
    await mcp_mod._vector_store.embed_and_upsert(
        "file_page:src/db/models.py",
        "DB Models — SQLAlchemy ORM models",
        {"title": "DB Models", "page_type": "file_page", "target_path": "src/db/models.py"},
    )

    result = await search_codebase("authentication service")
    assert "results" in result
    assert len(result["results"]) >= 1


# ---- Tool 6: get_architecture_diagram ----


@pytest.mark.asyncio
async def test_get_architecture_diagram_repo(setup_mcp):
    from wikicode.server.mcp_server import get_architecture_diagram

    result = await get_architecture_diagram(scope="repo")
    assert result["diagram_type"] in ("flowchart", "auto")
    assert "mermaid_syntax" in result
    assert "graph TD" in result["mermaid_syntax"]


@pytest.mark.asyncio
async def test_get_architecture_diagram_module(setup_mcp):
    from wikicode.server.mcp_server import get_architecture_diagram

    result = await get_architecture_diagram(scope="module", path="src/auth")
    assert "mermaid_syntax" in result
    assert result["description"]


# ---- Tool 7: get_dependency_path ----


@pytest.mark.asyncio
async def test_get_dependency_path(setup_mcp):
    from wikicode.server.mcp_server import get_dependency_path

    result = await get_dependency_path("src/auth/service.py", "src/db/models.py")
    assert result["distance"] == 1
    assert len(result["path"]) == 2


@pytest.mark.asyncio
async def test_get_dependency_path_multi_hop(setup_mcp):
    from wikicode.server.mcp_server import get_dependency_path

    result = await get_dependency_path("src/auth/middleware.py", "src/db/models.py")
    assert result["distance"] == 2
    assert len(result["path"]) == 3


@pytest.mark.asyncio
async def test_get_dependency_path_no_path(setup_mcp):
    from wikicode.server.mcp_server import get_dependency_path

    # Reverse direction — no path from models to middleware
    result = await get_dependency_path("src/db/models.py", "src/auth/middleware.py")
    assert result["distance"] == -1
    assert result["path"] == []


@pytest.mark.asyncio
async def test_get_dependency_path_node_not_found(setup_mcp):
    from wikicode.server.mcp_server import get_dependency_path

    result = await get_dependency_path("nonexistent.py", "src/auth/service.py")
    assert "error" in result


# ---- Tool 8: get_stale_pages ----


@pytest.mark.asyncio
async def test_get_stale_pages(setup_mcp):
    from wikicode.server.mcp_server import get_stale_pages

    result = await get_stale_pages(threshold=0.6)
    stale = result["stale_pages"]
    assert len(stale) == 2  # middleware (0.50) and models (0.40)
    # Should be sorted by confidence ASC
    assert stale[0]["confidence_score"] <= stale[1]["confidence_score"]


@pytest.mark.asyncio
async def test_get_stale_pages_high_threshold(setup_mcp):
    from wikicode.server.mcp_server import get_stale_pages

    result = await get_stale_pages(threshold=0.9)
    stale = result["stale_pages"]
    assert len(stale) >= 3  # middleware, models, service all below 0.9


# ---- Tool 9: get_file_history ----


@pytest.mark.asyncio
async def test_get_file_history(setup_mcp):
    from wikicode.server.mcp_server import get_file_history

    result = await get_file_history("src/auth/service.py")
    assert result["file_path"] == "src/auth/service.py"
    assert result["age_days"] == 443
    assert result["primary_owner"]["name"] == "Alice"
    assert result["primary_owner"]["pct"] == 0.65
    assert result["is_hotspot"] is True
    assert result["is_stable"] is False
    assert result["commit_count_total"] == 42
    assert result["commit_count_90d"] == 8
    assert len(result["significant_commits"]) == 2
    assert len(result["co_change_partners"]) == 2


@pytest.mark.asyncio
async def test_get_file_history_not_found(setup_mcp):
    from wikicode.server.mcp_server import get_file_history

    result = await get_file_history("nonexistent.py")
    assert "error" in result


# ---- Tool 10: get_hotspots ----


@pytest.mark.asyncio
async def test_get_hotspots(setup_mcp):
    from wikicode.server.mcp_server import get_hotspots

    result = await get_hotspots()
    assert len(result["hotspots"]) == 1
    assert result["hotspots"][0]["file_path"] == "src/auth/service.py"
    assert result["hotspots"][0]["churn_percentile"] == 0.92
    assert "stable_files" not in result


@pytest.mark.asyncio
async def test_get_hotspots_include_stable(setup_mcp):
    from wikicode.server.mcp_server import get_hotspots

    result = await get_hotspots(include_stable=True)
    assert "stable_files" in result
    assert len(result["stable_files"]) == 1
    assert result["stable_files"][0]["file_path"] == "src/db/models.py"


# ---- Tool 11: get_codebase_ownership ----


@pytest.mark.asyncio
async def test_get_codebase_ownership_by_module(setup_mcp):
    from wikicode.server.mcp_server import get_codebase_ownership

    result = await get_codebase_ownership(by="module")
    assert "by_module" in result
    modules = result["by_module"]
    # Both files are under src/, so grouped as one module "src"
    assert len(modules) == 1
    assert modules[0]["module_path"] == "src"
    assert modules[0]["contributor_count"] == 2


@pytest.mark.asyncio
async def test_get_codebase_ownership_by_file(setup_mcp):
    from wikicode.server.mcp_server import get_codebase_ownership

    result = await get_codebase_ownership(by="file")
    assert "by_file" in result
    assert len(result["by_file"]) == 2  # Only files with git metadata


# ---- Tool 12: get_co_changes ----


@pytest.mark.asyncio
async def test_get_co_changes(setup_mcp):
    from wikicode.server.mcp_server import get_co_changes

    result = await get_co_changes("src/auth/service.py", min_count=3)
    assert result["file_path"] == "src/auth/service.py"
    partners = result["co_change_partners"]
    assert len(partners) == 2
    # Check enrichment
    middleware_partner = next(p for p in partners if p["file_path"] == "src/auth/middleware.py")
    assert middleware_partner["co_change_count"] == 5
    assert middleware_partner["has_import_relationship"] is True  # edge exists
    assert middleware_partner["wiki_page_snippet"] is not None


@pytest.mark.asyncio
async def test_get_co_changes_not_found(setup_mcp):
    from wikicode.server.mcp_server import get_co_changes

    result = await get_co_changes("nonexistent.py")
    assert "error" in result


# ---- Tool 13: get_dead_code ----


@pytest.mark.asyncio
async def test_get_dead_code(setup_mcp):
    from wikicode.server.mcp_server import get_dead_code

    result = await get_dead_code()
    assert result["summary"]["total_findings"] == 3
    assert result["summary"]["safe_to_delete_count"] == 2
    # Default min_confidence=0.5, so all findings at >= 0.5 are included
    findings = result["findings"]
    assert len(findings) == 3
    assert findings[0]["confidence"] >= findings[1]["confidence"]  # sorted desc


@pytest.mark.asyncio
async def test_get_dead_code_safe_only(setup_mcp):
    from wikicode.server.mcp_server import get_dead_code

    result = await get_dead_code(safe_only=True)
    for f in result["findings"]:
        assert f["safe_to_delete"] is True


@pytest.mark.asyncio
async def test_get_dead_code_by_kind(setup_mcp):
    from wikicode.server.mcp_server import get_dead_code

    result = await get_dead_code(kind="unreachable_file", min_confidence=0.0)
    for f in result["findings"]:
        assert f["kind"] == "unreachable_file"


@pytest.mark.asyncio
async def test_get_dead_code_low_confidence(setup_mcp):
    from wikicode.server.mcp_server import get_dead_code

    result = await get_dead_code(min_confidence=0.0)
    assert len(result["findings"]) == 3  # All 3 findings included


# ---- MCP config generation ----


def test_generate_mcp_config():
    from pathlib import Path
    from wikicode.cli.mcp_config import generate_mcp_config

    config = generate_mcp_config(Path("/tmp/test-repo"))
    assert "mcpServers" in config
    assert "wikicode" in config["mcpServers"]
    server = config["mcpServers"]["wikicode"]
    assert server["command"] == "wikicode"
    assert "mcp" in server["args"]
    assert "stdio" in server["args"]


def test_format_setup_instructions():
    from pathlib import Path
    from wikicode.cli.mcp_config import format_setup_instructions

    instructions = format_setup_instructions(Path("/tmp/test-repo"))
    assert "Claude Code" in instructions
    assert "Cursor" in instructions
    assert "Cline" in instructions
    assert "wikicode" in instructions
