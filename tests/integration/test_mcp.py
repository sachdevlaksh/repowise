"""Integration tests for the MCP server tools.

Tests MCP tools against a fully populated database created by running
a mock init pipeline — verifying end-to-end tool responses with realistic data.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
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

_NOW = datetime(2026, 3, 19, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
async def mcp_env():
    """Set up a complete MCP test environment with realistic data."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    await init_db(engine)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    fts = FullTextSearch(engine)
    await fts.ensure_index()
    embedder = MockEmbedder()
    vector_store = InMemoryVectorStore(embedder=embedder)

    # Populate DB with a realistic multi-file Python project
    async with factory() as session:
        repo = Repository(
            id="integ-repo",
            name="sample-project",
            url="https://github.com/example/sample",
            local_path="/tmp/sample-project",
            default_branch="main",
            settings_json="{}",
            created_at=_NOW,
            updated_at=_NOW,
        )
        session.add(repo)

        # Pages: overview, arch diagram, 2 modules, 4 files
        pages_data = [
            ("repo_overview:sample", "repo_overview", "Sample Project Overview",
             "# Sample Project\n\nA Python web application with auth and data modules.",
             "sample", 6),
            ("architecture_diagram:sample", "architecture_diagram", "Architecture",
             "graph TD\n    auth[Auth] --> db[Database]\n    api[API] --> auth\n    api --> db",
             "sample", 6),
            ("module_page:src/auth", "module_page", "Authentication Module",
             "# Auth\n\nHandles user authentication, sessions, and JWT tokens.",
             "src/auth", 4),
            ("module_page:src/data", "module_page", "Data Module",
             "# Data\n\nDatabase models, repositories, and query builders.",
             "src/data", 4),
            ("file_page:src/auth/login.py", "file_page", "Login Handler",
             "# Login\n\nHandles user login via username/password or OAuth.",
             "src/auth/login.py", 2),
            ("file_page:src/auth/jwt.py", "file_page", "JWT Utilities",
             "# JWT\n\nJSON Web Token creation, validation, and refresh.",
             "src/auth/jwt.py", 2),
            ("file_page:src/data/user_repo.py", "file_page", "User Repository",
             "# UserRepository\n\nCRUD operations for User model.",
             "src/data/user_repo.py", 2),
            ("file_page:src/data/models.py", "file_page", "Data Models",
             "# Models\n\nSQLAlchemy ORM models: User, Session, Token.",
             "src/data/models.py", 2),
        ]
        for pid, ptype, title, content, tpath, level in pages_data:
            session.add(Page(
                id=pid, repository_id="integ-repo", page_type=ptype,
                title=title, content=content, target_path=tpath,
                source_hash="h" + pid[:6], model_name="mock", provider_name="mock",
                generation_level=level, confidence=0.9, freshness_status="fresh",
                metadata_json="{}", created_at=_NOW, updated_at=_NOW,
            ))

        # Symbols
        sym_data = [
            ("src/auth/login.py", "login_handler", "function",
             "async def login_handler(request: Request) -> Response"),
            ("src/auth/login.py", "LoginForm", "class", "class LoginForm(BaseModel)"),
            ("src/auth/jwt.py", "create_token", "function",
             "def create_token(user_id: str, secret: str) -> str"),
            ("src/auth/jwt.py", "verify_token", "function",
             "def verify_token(token: str, secret: str) -> dict"),
            ("src/data/user_repo.py", "UserRepository", "class",
             "class UserRepository"),
            ("src/data/user_repo.py", "find_by_email", "method",
             "async def find_by_email(self, email: str) -> User | None"),
            ("src/data/models.py", "User", "class", "class User(Base)"),
            ("src/data/models.py", "Session", "class", "class Session(Base)"),
        ]
        for i, (fp, name, kind, sig) in enumerate(sym_data):
            session.add(WikiSymbol(
                id=f"is{i}", repository_id="integ-repo", file_path=fp,
                symbol_id=f"{fp}::{name}", name=name, qualified_name=name,
                kind=kind, signature=sig, start_line=1, end_line=20,
                visibility="public", language="python",
                created_at=_NOW, updated_at=_NOW,
            ))

        # Graph nodes
        files = ["src/auth/login.py", "src/auth/jwt.py",
                 "src/data/user_repo.py", "src/data/models.py"]
        for i, fp in enumerate(files):
            session.add(GraphNode(
                id=f"ign{i}", repository_id="integ-repo", node_id=fp,
                node_type="file", language="python", symbol_count=2,
                is_entry_point=(fp == "src/auth/login.py"),
                pagerank=0.8 - i * 0.15, betweenness=0.3, community_id=1 if "auth" in fp else 2,
                created_at=_NOW,
            ))

        # Graph edges
        edge_data = [
            ("src/auth/login.py", "src/auth/jwt.py", '["create_token"]'),
            ("src/auth/login.py", "src/data/user_repo.py", '["UserRepository"]'),
            ("src/data/user_repo.py", "src/data/models.py", '["User"]'),
        ]
        for i, (src, tgt, names) in enumerate(edge_data):
            session.add(GraphEdge(
                id=f"ige{i}", repository_id="integ-repo",
                source_node_id=src, target_node_id=tgt,
                imported_names_json=names, created_at=_NOW,
            ))

        # Git metadata
        session.add(GitMetadata(
            id="igm1", repository_id="integ-repo",
            file_path="src/auth/login.py",
            commit_count_total=50, commit_count_90d=12, commit_count_30d=5,
            first_commit_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            last_commit_at=datetime(2026, 3, 18, tzinfo=timezone.utc),
            primary_owner_name="Alice", primary_owner_email="alice@ex.com",
            primary_owner_commit_pct=0.70,
            top_authors_json=json.dumps([{"name": "Alice", "count": 35}, {"name": "Bob", "count": 15}]),
            significant_commits_json=json.dumps([
                {"sha": "a1", "date": "2026-03-18", "message": "Fix OAuth redirect", "author": "Alice"},
            ]),
            co_change_partners_json=json.dumps([
                {"file_path": "src/auth/jwt.py", "count": 8},
            ]),
            is_hotspot=True, is_stable=False, churn_percentile=0.95, age_days=443,
            created_at=_NOW, updated_at=_NOW,
        ))

        # Dead code
        session.add(DeadCodeFinding(
            id="idc1", repository_id="integ-repo",
            kind="unused_export", file_path="src/auth/jwt.py",
            symbol_name="deprecated_verify", symbol_kind="function",
            confidence=0.8, reason="No callers", lines=15, safe_to_delete=True,
            primary_owner="Alice", status="open", analyzed_at=_NOW,
        ))

        await session.commit()

    # Index pages in vector store for search
    await vector_store.embed_and_upsert(
        "file_page:src/auth/login.py", "Login Handler — OAuth and password auth",
        {"title": "Login Handler", "page_type": "file_page", "target_path": "src/auth/login.py"},
    )
    await vector_store.embed_and_upsert(
        "file_page:src/data/models.py", "Data Models — SQLAlchemy User Session Token",
        {"title": "Data Models", "page_type": "file_page", "target_path": "src/data/models.py"},
    )

    # Configure MCP globals
    import wikicode.server.mcp_server as mcp_mod
    mcp_mod._session_factory = factory
    mcp_mod._fts = fts
    mcp_mod._vector_store = vector_store
    mcp_mod._repo_path = "/tmp/sample-project"

    yield

    mcp_mod._session_factory = None
    mcp_mod._fts = None
    mcp_mod._vector_store = None
    mcp_mod._repo_path = None

    await vector_store.close()
    await engine.dispose()


# ---------------------------------------------------------------------------
# Integration tests — verify end-to-end MCP tool responses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mcp_full_exploration_flow(mcp_env):
    """Test the typical MCP exploration flow: overview → module → file → symbol."""
    from wikicode.server.mcp_server import (
        get_file_docs,
        get_module_docs,
        get_overview,
        get_symbol,
    )

    # Step 1: Get overview
    overview = await get_overview()
    assert "Sample Project" in overview["content_md"]
    assert len(overview["key_modules"]) == 2
    assert overview["architecture_diagram_mermaid"] is not None

    # Step 2: Drill into auth module
    auth_module = await get_module_docs("src/auth")
    assert "authentication" in auth_module["content_md"].lower()
    assert len(auth_module["files"]) == 2

    # Step 3: Get file docs
    login_file = await get_file_docs("src/auth/login.py")
    assert login_file["title"] == "Login Handler"
    assert any(s["name"] == "login_handler" for s in login_file["symbols"])

    # Step 4: Look up a symbol
    symbol = await get_symbol("UserRepository")
    assert symbol["kind"] == "class"
    assert symbol["file_path"] == "src/data/user_repo.py"


@pytest.mark.asyncio
async def test_mcp_dependency_and_graph_flow(mcp_env):
    """Test dependency path and architecture diagram tools."""
    from wikicode.server.mcp_server import (
        get_architecture_diagram,
        get_dependency_path,
    )

    # Dependency path from login to models (2 hops)
    path = await get_dependency_path("src/auth/login.py", "src/data/models.py")
    assert path["distance"] == 2
    assert len(path["path"]) == 3

    # Architecture diagram
    diagram = await get_architecture_diagram(scope="repo")
    assert "graph TD" in diagram["mermaid_syntax"]


@pytest.mark.asyncio
async def test_mcp_git_intelligence_flow(mcp_env):
    """Test git intelligence tools: history, hotspots, ownership, co-changes."""
    from wikicode.server.mcp_server import (
        get_codebase_ownership,
        get_co_changes,
        get_file_history,
        get_hotspots,
    )

    # File history
    history = await get_file_history("src/auth/login.py")
    assert history["is_hotspot"] is True
    assert history["primary_owner"]["name"] == "Alice"
    assert len(history["co_change_partners"]) == 1

    # Hotspots
    hotspots = await get_hotspots()
    assert len(hotspots["hotspots"]) == 1

    # Ownership
    ownership = await get_codebase_ownership()
    assert len(ownership["by_module"]) >= 1

    # Co-changes
    co = await get_co_changes("src/auth/login.py", min_count=3)
    assert len(co["co_change_partners"]) == 1
    assert co["co_change_partners"][0]["file_path"] == "src/auth/jwt.py"


@pytest.mark.asyncio
async def test_mcp_dead_code_and_stale_flow(mcp_env):
    """Test dead code and stale pages tools."""
    from wikicode.server.mcp_server import get_dead_code, get_stale_pages

    # Dead code
    dead = await get_dead_code()
    assert dead["summary"]["total_findings"] == 1
    assert dead["findings"][0]["symbol_name"] == "deprecated_verify"

    # Stale pages (all have confidence 0.9, so threshold 0.95 catches them)
    stale = await get_stale_pages(threshold=0.95)
    assert len(stale["stale_pages"]) >= 1


@pytest.mark.asyncio
async def test_mcp_search_flow(mcp_env):
    """Test semantic search."""
    from wikicode.server.mcp_server import search_codebase

    result = await search_codebase("authentication login OAuth")
    assert "results" in result
    assert len(result["results"]) >= 1
