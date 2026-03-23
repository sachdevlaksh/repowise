"""WikiCode MCP Server — 13 tools for AI coding assistants.

Exposes the full WikiCode wiki as queryable tools via the MCP protocol.
Supports both stdio transport (Claude Code, Cursor, Cline) and SSE transport
(web-based MCP clients).

Usage:
    wikicode mcp --transport stdio  # for Claude Code / Cursor / Cline
    wikicode mcp --transport sse    # for web-based clients
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from wikicode.core.persistence.database import get_session, init_db
from wikicode.core.persistence.embedder import MockEmbedder
from wikicode.core.persistence.models import (
    DeadCodeFinding,
    DecisionRecord,
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
# Shared state (set during lifespan)
# ---------------------------------------------------------------------------

_session_factory: async_sessionmaker[AsyncSession] | None = None
_vector_store: Any = None
_decision_store: Any = None
_fts: Any = None
_repo_path: str | None = None


@asynccontextmanager
async def _lifespan(server: FastMCP):
    """Initialize DB engine, session factory, vector store, FTS on startup."""
    global _session_factory, _vector_store, _decision_store, _fts  # noqa: PLW0603

    db_url = os.environ.get(
        "WIKICODE_DATABASE_URL", "sqlite+aiosqlite:///wikicode.db"
    )

    # If a repo path was configured, try .wikicode/wikicode.db
    if _repo_path:
        from pathlib import Path

        wikicode_dir = Path(_repo_path) / ".wikicode"
        if wikicode_dir.exists():
            db_path = wikicode_dir / "wikicode.db"
            if db_path.exists():
                db_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"

    connect_args: dict = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_async_engine(db_url, connect_args=connect_args)
    await init_db(engine)

    _session_factory = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )

    _fts = FullTextSearch(engine)
    await _fts.ensure_index()

    embedder = MockEmbedder()
    _vector_store = InMemoryVectorStore(embedder=embedder)

    # Try to load LanceDB if available
    try:
        from wikicode.core.persistence.vector_store import LanceDBVectorStore

        if _repo_path:
            from pathlib import Path

            lance_dir = Path(_repo_path) / ".wikicode" / "lancedb"
            if lance_dir.exists():
                _vector_store = LanceDBVectorStore(
                    str(lance_dir), embedder=embedder
                )
                _decision_store = LanceDBVectorStore(
                    str(lance_dir), embedder=embedder, table_name="decision_records"
                )
    except ImportError:
        pass

    if _decision_store is None:
        _decision_store = InMemoryVectorStore(embedder=embedder)

    yield

    await engine.dispose()
    await _vector_store.close()
    if _decision_store is not None:
        await _decision_store.close()


# ---------------------------------------------------------------------------
# Create the MCP server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "WikiCode",
    instructions=(
        "WikiCode is a codebase documentation engine. Use these tools to query "
        "the wiki for architecture overviews, file docs, symbol lookups, "
        "dependency paths, git history, hotspots, ownership, and dead code."
    ),
    lifespan=_lifespan,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_repo(session: AsyncSession, repo: str | None = None) -> Repository:
    """Resolve a repository — by path, by ID, or return the first one."""
    if repo:
        # Try by path
        result = await session.execute(
            select(Repository).where(Repository.local_path == repo)
        )
        obj = result.scalar_one_or_none()
        if obj:
            return obj
        # Try by ID
        obj = await session.get(Repository, repo)
        if obj:
            return obj
        # Try by name
        result = await session.execute(
            select(Repository).where(Repository.name == repo)
        )
        obj = result.scalar_one_or_none()
        if obj:
            return obj
        raise LookupError(f"Repository not found: {repo}")

    # Default: return the first (and often only) repository
    result = await session.execute(select(Repository).limit(1))
    obj = result.scalar_one_or_none()
    if obj is None:
        raise LookupError(
            "No repositories found. Run 'wikicode init' first."
        )
    return obj


# ---------------------------------------------------------------------------
# Tool 1: get_overview
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_overview(repo: str | None = None) -> dict:
    """Get the repository overview: architecture summary, module map, key entry points.

    Best first call when starting to explore an unfamiliar codebase.

    Args:
        repo: Repository path, name, or ID. Omit if only one repo exists.
    """
    async with get_session(_session_factory) as session:
        repository = await _get_repo(session, repo)

        # Get repo overview page
        result = await session.execute(
            select(Page).where(
                Page.repository_id == repository.id,
                Page.page_type == "repo_overview",
            )
        )
        overview_page = result.scalar_one_or_none()

        # Get architecture diagram page
        result = await session.execute(
            select(Page).where(
                Page.repository_id == repository.id,
                Page.page_type == "architecture_diagram",
            )
        )
        arch_page = result.scalar_one_or_none()

        # Get module pages
        result = await session.execute(
            select(Page)
            .where(
                Page.repository_id == repository.id,
                Page.page_type == "module_page",
            )
            .order_by(Page.title)
        )
        module_pages = result.scalars().all()

        # Get entry point files from graph nodes
        result = await session.execute(
            select(GraphNode).where(
                GraphNode.repository_id == repository.id,
                GraphNode.is_entry_point == True,  # noqa: E712
            )
        )
        entry_nodes = result.scalars().all()

        return {
            "title": overview_page.title if overview_page else repository.name,
            "content_md": overview_page.content if overview_page else "No overview generated yet.",
            "architecture_diagram_mermaid": arch_page.content if arch_page else None,
            "key_modules": [
                {
                    "name": p.title,
                    "path": p.target_path,
                    "description": p.content[:200] + "..." if len(p.content) > 200 else p.content,
                }
                for p in module_pages
            ],
            "entry_points": [n.node_id for n in entry_nodes],
        }


# ---------------------------------------------------------------------------
# Tool 2: get_module_docs
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_module_docs(module_path: str, repo: str | None = None) -> dict:
    """Get the wiki page for a module/package/directory.

    Args:
        module_path: Module path (e.g. "src/auth", "packages/core").
        repo: Repository path, name, or ID.
    """
    async with get_session(_session_factory) as session:
        repository = await _get_repo(session, repo)

        # Look up module page by target_path match
        result = await session.execute(
            select(Page).where(
                Page.repository_id == repository.id,
                Page.page_type == "module_page",
                Page.target_path == module_path,
            )
        )
        page = result.scalar_one_or_none()

        # Fallback: try partial match
        if page is None:
            result = await session.execute(
                select(Page).where(
                    Page.repository_id == repository.id,
                    Page.page_type == "module_page",
                    Page.target_path.contains(module_path),
                )
            )
            page = result.scalar_one_or_none()

        if page is None:
            return {"error": f"Module page not found for '{module_path}'"}

        # Get file pages within this module
        result = await session.execute(
            select(Page).where(
                Page.repository_id == repository.id,
                Page.page_type == "file_page",
                Page.target_path.like(f"{module_path}%"),
            )
        )
        file_pages = result.scalars().all()

        return {
            "title": page.title,
            "content_md": page.content,
            "files": [
                {
                    "path": f.target_path,
                    "description": f.title,
                    "confidence_score": f.confidence,
                }
                for f in file_pages
            ],
            "public_api_summary": page.content[:500] if page.content else "",
        }


# ---------------------------------------------------------------------------
# Tool 3: get_file_docs
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_file_docs(file_path: str, repo: str | None = None) -> dict:
    """Get the wiki page for a specific file.

    Args:
        file_path: Relative file path (e.g. "src/auth/service.py").
        repo: Repository path, name, or ID.
    """
    async with get_session(_session_factory) as session:
        repository = await _get_repo(session, repo)

        page_id = f"file_page:{file_path}"
        page = await session.get(Page, page_id)

        if page is None:
            # Try searching by target_path
            result = await session.execute(
                select(Page).where(
                    Page.repository_id == repository.id,
                    Page.page_type == "file_page",
                    Page.target_path == file_path,
                )
            )
            page = result.scalar_one_or_none()

        if page is None:
            return {"error": f"File page not found for '{file_path}'"}

        # Get symbols in this file
        result = await session.execute(
            select(WikiSymbol).where(
                WikiSymbol.repository_id == repository.id,
                WikiSymbol.file_path == file_path,
            )
        )
        symbols = result.scalars().all()

        # Get files that import this one (from graph edges)
        result = await session.execute(
            select(GraphEdge).where(
                GraphEdge.repository_id == repository.id,
                GraphEdge.target_node_id == file_path,
            )
        )
        importers = result.scalars().all()

        return {
            "title": page.title,
            "content_md": page.content,
            "symbols": [
                {"name": s.name, "kind": s.kind, "signature": s.signature}
                for s in symbols
            ],
            "imported_by": [e.source_node_id for e in importers],
            "confidence_score": page.confidence,
            "freshness_status": page.freshness_status,
        }


# ---------------------------------------------------------------------------
# Tool 4: get_symbol
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_symbol(
    symbol_name: str, kind: str | None = None, repo: str | None = None
) -> dict:
    """Look up any symbol by name (fuzzy match if exact match fails).

    Args:
        symbol_name: Symbol name (e.g. "AuthService", "login", "UserRepository.find_by_id").
        kind: Optional filter by kind (function, class, method, interface, enum, etc.).
        repo: Repository path, name, or ID.
    """
    async with get_session(_session_factory) as session:
        repository = await _get_repo(session, repo)

        # Try exact match first
        query = select(WikiSymbol).where(
            WikiSymbol.repository_id == repository.id,
            WikiSymbol.name == symbol_name,
        )
        if kind:
            query = query.where(WikiSymbol.kind == kind)
        result = await session.execute(query)
        matches = list(result.scalars().all())

        # Fallback to fuzzy match
        if not matches:
            query = select(WikiSymbol).where(
                WikiSymbol.repository_id == repository.id,
                WikiSymbol.name.ilike(f"%{symbol_name}%"),
            )
            if kind:
                query = query.where(WikiSymbol.kind == kind)
            result = await session.execute(query.limit(10))
            matches = list(result.scalars().all())

        if not matches:
            return {"error": f"Symbol not found: '{symbol_name}'"}

        sym = matches[0]

        # Get the file page for this symbol's documentation
        page_id = f"file_page:{sym.file_path}"
        page = await session.get(Page, page_id)

        # Get files that use this symbol
        result = await session.execute(
            select(GraphEdge).where(
                GraphEdge.repository_id == repository.id,
                GraphEdge.target_node_id == sym.file_path,
            )
        )
        edges = result.scalars().all()
        used_by = [e.source_node_id for e in edges]

        return {
            "name": sym.name,
            "qualified_name": sym.qualified_name,
            "kind": sym.kind,
            "signature": sym.signature,
            "file_path": sym.file_path,
            "documentation": page.content if page else sym.docstring or "",
            "used_by": used_by[:20],
            "confidence_score": page.confidence if page else None,
            "candidates": [
                {"name": m.name, "kind": m.kind, "file_path": m.file_path}
                for m in matches[1:5]
            ]
            if len(matches) > 1
            else [],
        }


# ---------------------------------------------------------------------------
# Tool 5: search_codebase
# ---------------------------------------------------------------------------


@mcp.tool()
async def search_codebase(
    query: str,
    limit: int = 5,
    page_type: str | None = None,
    repo: str | None = None,
) -> dict:
    """Semantic search over the full wiki. Ask in natural language.

    Args:
        query: Natural language search query (e.g. "how does authentication work?").
        limit: Maximum results to return (default 5).
        page_type: Optional filter by page type (file_page, module_page, etc.).
        repo: Repository path, name, or ID.
    """
    async with get_session(_session_factory) as session:
        # Ensure repo exists
        await _get_repo(session, repo)

    # Try semantic search first, fall back to fulltext
    try:
        results = await _vector_store.search(query, limit=limit)
    except Exception:
        results = await _fts.search(query, limit=limit)

    output = []
    for r in results:
        if page_type and r.page_type != page_type:
            continue
        output.append(
            {
                "page_id": r.page_id,
                "title": r.title,
                "page_type": r.page_type,
                "snippet": r.snippet,
                "relevance_score": r.score,
                "confidence_score": getattr(r, "confidence", None),
            }
        )

    return {"results": output[:limit]}


# ---------------------------------------------------------------------------
# Tool 6: get_architecture_diagram
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_architecture_diagram(
    scope: str = "repo",
    path: str | None = None,
    diagram_type: str = "auto",
    repo: str | None = None,
) -> dict:
    """Get a Mermaid diagram for the codebase or a specific module.

    Args:
        scope: "repo", "module", or "file".
        path: Module or file path (required for module/file scope).
        diagram_type: "auto", "flowchart", "class", or "sequence".
        repo: Repository path, name, or ID.
    """
    async with get_session(_session_factory) as session:
        repository = await _get_repo(session, repo)

        if scope == "repo":
            # Return the architecture diagram page
            result = await session.execute(
                select(Page).where(
                    Page.repository_id == repository.id,
                    Page.page_type == "architecture_diagram",
                )
            )
            page = result.scalar_one_or_none()
            if page:
                return {
                    "diagram_type": diagram_type if diagram_type != "auto" else "flowchart",
                    "mermaid_syntax": page.content,
                    "description": page.title,
                }

        # For module/file scope or fallback, build diagram from graph
        if path:
            filter_prefix = path
        else:
            filter_prefix = ""

        result = await session.execute(
            select(GraphNode).where(
                GraphNode.repository_id == repository.id,
                GraphNode.node_id.like(f"{filter_prefix}%") if filter_prefix else GraphNode.repository_id == repository.id,
            )
        )
        nodes = result.scalars().all()

        result = await session.execute(
            select(GraphEdge).where(
                GraphEdge.repository_id == repository.id,
            )
        )
        edges = result.scalars().all()

        node_ids = {n.node_id for n in nodes}
        relevant_edges = [
            e for e in edges
            if e.source_node_id in node_ids or e.target_node_id in node_ids
        ]

        # Build Mermaid flowchart
        lines = ["graph TD"]
        seen_nodes = set()
        for e in relevant_edges[:50]:  # Limit to 50 edges for readability
            src = e.source_node_id.replace("/", "_").replace(".", "_").replace("-", "_")
            tgt = e.target_node_id.replace("/", "_").replace(".", "_").replace("-", "_")
            if src not in seen_nodes:
                lines.append(f'    {src}["{e.source_node_id}"]')
                seen_nodes.add(src)
            if tgt not in seen_nodes:
                lines.append(f'    {tgt}["{e.target_node_id}"]')
                seen_nodes.add(tgt)
            lines.append(f"    {src} --> {tgt}")

        mermaid = "\n".join(lines) if len(lines) > 1 else "graph TD\n    A[No graph data available]"

        return {
            "diagram_type": diagram_type if diagram_type != "auto" else "flowchart",
            "mermaid_syntax": mermaid,
            "description": f"Dependency graph for {scope}: {path or 'entire repo'}",
        }


# ---------------------------------------------------------------------------
# Tool 7: get_dependency_path
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_dependency_path(
    source: str, target: str, repo: str | None = None
) -> dict:
    """Find how two files/modules are connected in the dependency graph.

    Args:
        source: Source file or module path.
        target: Target file or module path.
        repo: Repository path, name, or ID.
    """
    async with get_session(_session_factory) as session:
        repository = await _get_repo(session, repo)

        result = await session.execute(
            select(GraphEdge).where(
                GraphEdge.repository_id == repository.id,
            )
        )
        edges = result.scalars().all()

    try:
        import networkx as nx
    except ImportError:
        return {"error": "networkx not available for path queries"}

    G = nx.DiGraph()
    for e in edges:
        G.add_edge(e.source_node_id, e.target_node_id)

    if source not in G:
        return {"error": f"Source node '{source}' not found in graph"}
    if target not in G:
        return {"error": f"Target node '{target}' not found in graph"}

    try:
        path = nx.shortest_path(G, source, target)
    except nx.NetworkXNoPath:
        return {"path": [], "distance": -1, "explanation": "No path found"}

    # Build path with relationships
    path_with_info = []
    for i, node in enumerate(path):
        relationship = ""
        if i < len(path) - 1:
            relationship = "imports"
        path_with_info.append({"node": node, "relationship": relationship})

    return {
        "path": path_with_info,
        "distance": len(path) - 1,
        "explanation": f"Shortest path from {source} to {target} has {len(path) - 1} hops",
    }


# ---------------------------------------------------------------------------
# Tool 8: get_stale_pages
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_stale_pages(
    threshold: float = 0.6, repo: str | None = None
) -> dict:
    """List pages whose confidence has dropped below a threshold.

    Useful for knowing which docs to distrust or prioritize for regeneration.

    Args:
        threshold: Confidence score threshold (default 0.6). Pages below this are returned.
        repo: Repository path, name, or ID.
    """
    async with get_session(_session_factory) as session:
        repository = await _get_repo(session, repo)

        result = await session.execute(
            select(Page)
            .where(
                Page.repository_id == repository.id,
                Page.confidence < threshold,
            )
            .order_by(Page.confidence)
            .limit(50)
        )
        pages = result.scalars().all()

        return {
            "stale_pages": [
                {
                    "id": p.id,
                    "title": p.title,
                    "page_type": p.page_type,
                    "confidence_score": p.confidence,
                    "stale_since": p.updated_at.isoformat() if p.updated_at else None,
                    "source_files": [p.target_path],
                }
                for p in pages
            ]
        }


# ---------------------------------------------------------------------------
# Tool 9: get_file_history
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_file_history(
    file_path: str, repo: str | None = None, limit: int = 10
) -> dict:
    """Get the git history for a file — the WHY behind its current structure.

    Call this before making changes to understand why code was written as it was.

    Args:
        file_path: Relative file path (e.g. "src/auth/service.py").
        repo: Repository path, name, or ID.
        limit: Max significant commits to return (default 10).
    """
    async with get_session(_session_factory) as session:
        repository = await _get_repo(session, repo)

        result = await session.execute(
            select(GitMetadata).where(
                GitMetadata.repository_id == repository.id,
                GitMetadata.file_path == file_path,
            )
        )
        meta = result.scalar_one_or_none()

        if meta is None:
            return {"error": f"No git metadata found for '{file_path}'"}

        significant_commits = json.loads(meta.significant_commits_json)
        co_change_partners = json.loads(meta.co_change_partners_json)

        return {
            "file_path": meta.file_path,
            "age_days": meta.age_days,
            "primary_owner": {
                "name": meta.primary_owner_name,
                "email": meta.primary_owner_email,
                "pct": meta.primary_owner_commit_pct,
            },
            "is_hotspot": meta.is_hotspot,
            "is_stable": meta.is_stable,
            "commit_count_total": meta.commit_count_total,
            "commit_count_90d": meta.commit_count_90d,
            "significant_commits": significant_commits[:limit],
            "co_change_partners": [
                {
                    "file_path": p.get("file_path", p.get("path", "")),
                    "co_change_count": p.get("count", 0),
                }
                for p in co_change_partners
            ],
        }


# ---------------------------------------------------------------------------
# Tool 10: get_hotspots
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_hotspots(
    repo: str | None = None,
    limit: int = 10,
    include_stable: bool = False,
) -> dict:
    """Get the riskiest files: high churn AND high complexity.

    These are the files most likely to contain bugs.

    Args:
        repo: Repository path, name, or ID.
        limit: Max hotspots to return (default 10).
        include_stable: Also return stable files (default false).
    """
    async with get_session(_session_factory) as session:
        repository = await _get_repo(session, repo)

        result = await session.execute(
            select(GitMetadata)
            .where(
                GitMetadata.repository_id == repository.id,
                GitMetadata.is_hotspot == True,  # noqa: E712
            )
            .order_by(GitMetadata.churn_percentile.desc())
            .limit(limit)
        )
        hotspots = result.scalars().all()

        response: dict[str, Any] = {
            "hotspots": [
                {
                    "file_path": h.file_path,
                    "commit_count_90d": h.commit_count_90d,
                    "churn_percentile": h.churn_percentile,
                    "primary_owner": h.primary_owner_name,
                }
                for h in hotspots
            ],
        }

        if include_stable:
            result = await session.execute(
                select(GitMetadata)
                .where(
                    GitMetadata.repository_id == repository.id,
                    GitMetadata.is_stable == True,  # noqa: E712
                )
                .order_by(GitMetadata.commit_count_total.desc())
                .limit(limit)
            )
            stables = result.scalars().all()
            response["stable_files"] = [
                {
                    "file_path": s.file_path,
                    "commit_count_total": s.commit_count_total,
                    "primary_owner": s.primary_owner_name,
                }
                for s in stables
            ]

        return response


# ---------------------------------------------------------------------------
# Tool 11: get_codebase_ownership
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_codebase_ownership(
    repo: str | None = None, by: str = "module"
) -> dict:
    """Get ownership breakdown. Identifies knowledge silos and abandoned areas.

    Args:
        repo: Repository path, name, or ID.
        by: Granularity — "file", "module", or "package" (default "module").
    """
    async with get_session(_session_factory) as session:
        repository = await _get_repo(session, repo)

        result = await session.execute(
            select(GitMetadata).where(
                GitMetadata.repository_id == repository.id,
            )
        )
        all_meta = list(result.scalars().all())

    if by == "file":
        return {
            "by_file": [
                {
                    "file_path": m.file_path,
                    "primary_owner": m.primary_owner_name,
                    "owner_pct": m.primary_owner_commit_pct,
                    "contributor_count": len(json.loads(m.top_authors_json)),
                    "is_silo": (m.primary_owner_commit_pct or 0) > 0.8,
                    "last_commit_days_ago": m.age_days,
                }
                for m in all_meta
            ]
        }

    # Group by module (top-level directory)
    modules: dict[str, list[GitMetadata]] = {}
    for m in all_meta:
        parts = m.file_path.split("/")
        module = parts[0] if len(parts) > 1 else "root"
        modules.setdefault(module, []).append(m)

    entries = []
    for module_path, files in sorted(modules.items()):
        owners: dict[str, int] = {}
        all_contributors: set[str] = set()
        for f in files:
            if f.primary_owner_name:
                owners[f.primary_owner_name] = owners.get(f.primary_owner_name, 0) + 1
            for author in json.loads(f.top_authors_json):
                name = author.get("name", "")
                if name:
                    all_contributors.add(name)

        if owners:
            top_owner = max(owners, key=owners.get)  # type: ignore[arg-type]
            owner_pct = owners[top_owner] / len(files)
        else:
            top_owner = None
            owner_pct = 0.0

        entries.append(
            {
                "module_path": module_path,
                "primary_owner": top_owner,
                "owner_pct": owner_pct,
                "contributor_count": len(all_contributors),
                "is_silo": owner_pct > 0.8,
                "last_commit_days_ago": min(
                    (f.age_days for f in files), default=0
                ),
            }
        )

    return {"by_module": entries}


# ---------------------------------------------------------------------------
# Tool 12: get_co_changes
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_co_changes(
    file_path: str, repo: str | None = None, min_count: int = 3
) -> dict:
    """Get files that frequently change together with the given file.

    Essential before refactoring — reveals hidden coupling not visible in imports.

    Args:
        file_path: Relative file path.
        repo: Repository path, name, or ID.
        min_count: Minimum co-change count to include (default 3).
    """
    async with get_session(_session_factory) as session:
        repository = await _get_repo(session, repo)

        result = await session.execute(
            select(GitMetadata).where(
                GitMetadata.repository_id == repository.id,
                GitMetadata.file_path == file_path,
            )
        )
        meta = result.scalar_one_or_none()

        if meta is None:
            return {"error": f"No git metadata found for '{file_path}'"}

        partners = json.loads(meta.co_change_partners_json)
        filtered = [p for p in partners if p.get("count", 0) >= min_count]

        # Check if partners have import relationships
        partner_paths = [p.get("file_path", p.get("path", "")) for p in filtered]
        result = await session.execute(
            select(GraphEdge).where(
                GraphEdge.repository_id == repository.id,
                GraphEdge.source_node_id == file_path,
            )
        )
        outgoing = {e.target_node_id for e in result.scalars().all()}

        result = await session.execute(
            select(GraphEdge).where(
                GraphEdge.repository_id == repository.id,
                GraphEdge.target_node_id == file_path,
            )
        )
        incoming = {e.source_node_id for e in result.scalars().all()}
        import_related = outgoing | incoming

        enriched_partners = []
        for p in filtered:
            p_path = p.get("file_path", p.get("path", ""))
            # Try to get a wiki page snippet
            page_id = f"file_page:{p_path}"
            page = await session.get(Page, page_id)
            snippet = page.content[:150] + "..." if page and len(page.content) > 150 else (page.content if page else None)

            enriched_partners.append(
                {
                    "file_path": p_path,
                    "co_change_count": p.get("count", 0),
                    "has_import_relationship": p_path in import_related,
                    "wiki_page_snippet": snippet,
                }
            )

        return {
            "file_path": file_path,
            "co_change_partners": enriched_partners,
        }


# ---------------------------------------------------------------------------
# Tool 13: get_dead_code
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_dead_code(
    repo: str | None = None,
    kind: str | None = None,
    min_confidence: float = 0.6,
    safe_only: bool = False,
    limit: int = 20,
) -> dict:
    """Get dead and unused code findings. Use before cleanup tasks.

    Results sorted by confidence desc, then lines desc (biggest wins first).

    Args:
        repo: Repository path, name, or ID.
        kind: Filter by kind (unreachable_file, unused_export, unused_internal, zombie_package).
        min_confidence: Minimum confidence threshold (default 0.6).
        safe_only: Only return findings marked safe_to_delete (default false).
        limit: Maximum findings to return (default 20).
    """
    async with get_session(_session_factory) as session:
        repository = await _get_repo(session, repo)

        query = (
            select(DeadCodeFinding)
            .where(
                DeadCodeFinding.repository_id == repository.id,
                DeadCodeFinding.status == "open",
                DeadCodeFinding.confidence >= min_confidence,
            )
            .order_by(DeadCodeFinding.confidence.desc(), DeadCodeFinding.lines.desc())
        )

        if kind:
            query = query.where(DeadCodeFinding.kind == kind)

        result = await session.execute(query)
        findings = list(result.scalars().all())

        if safe_only:
            findings = [f for f in findings if f.safe_to_delete]

        findings = findings[:limit]

        # Compute summary
        all_result = await session.execute(
            select(DeadCodeFinding).where(
                DeadCodeFinding.repository_id == repository.id,
                DeadCodeFinding.status == "open",
            )
        )
        all_findings = list(all_result.scalars().all())

        by_kind: dict[str, int] = {}
        for f in all_findings:
            by_kind[f.kind] = by_kind.get(f.kind, 0) + 1

        return {
            "summary": {
                "total_findings": len(all_findings),
                "deletable_lines": sum(f.lines for f in all_findings if f.safe_to_delete),
                "safe_to_delete_count": sum(1 for f in all_findings if f.safe_to_delete),
                "by_kind": by_kind,
            },
            "findings": [
                {
                    "kind": f.kind,
                    "file_path": f.file_path,
                    "symbol_name": f.symbol_name,
                    "confidence": f.confidence,
                    "reason": f.reason,
                    "safe_to_delete": f.safe_to_delete,
                    "lines": f.lines,
                    "last_commit_at": f.last_commit_at.isoformat() if f.last_commit_at else None,
                    "primary_owner": f.primary_owner,
                    "age_days": f.age_days,
                }
                for f in findings
            ],
        }


# ---------------------------------------------------------------------------
# Tool 14: get_decisions
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_decisions(
    module: str | None = None,
    tag: str | None = None,
    include_proposed: bool = False,
    include_stale: bool = True,
    repo: str | None = None,
) -> dict:
    """Get architectural decision records for the codebase.

    Use this before making architectural changes to understand existing
    constraints and why things are built the way they are.

    Args:
        module: Filter by module path (e.g. "src/auth", "packages/core").
        tag: Filter by tag: auth, database, api, performance, security, infra, testing.
        include_proposed: Include unconfirmed proposed decisions (default false).
        include_stale: Include decisions with high staleness scores (default true).
        repo: Repository path, name, or ID.
    """
    from wikicode.core.persistence.crud import list_decisions as _list_decisions

    async with get_session(_session_factory) as session:
        repository = await _get_repo(session, repo)

        statuses = ["active"]
        if include_proposed:
            statuses.append("proposed")

        decisions = await _list_decisions(
            session,
            repository.id,
            tag=tag,
            module=module,
            include_proposed=include_proposed,
            limit=50,
        )

    # Filter stale if requested
    if not include_stale:
        decisions = [d for d in decisions if d.staleness_score < 0.5]

    # Filter to requested statuses
    decisions = [d for d in decisions if d.status in statuses]

    return {
        "decisions": [
            {
                "id": d.id,
                "title": d.title,
                "status": d.status,
                "context": d.context,
                "decision": d.decision,
                "rationale": d.rationale,
                "alternatives": json.loads(d.alternatives_json),
                "consequences": json.loads(d.consequences_json),
                "affected_files": json.loads(d.affected_files_json),
                "affected_modules": json.loads(d.affected_modules_json),
                "tags": json.loads(d.tags_json),
                "source": d.source,
                "confidence": d.confidence,
                "staleness_score": d.staleness_score,
            }
            for d in decisions
        ],
        "total": len(decisions),
    }


# ---------------------------------------------------------------------------
# Tool 15: get_why
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_why(query: str, repo: str | None = None) -> dict:
    """Answer 'why is X implemented this way?' using decision records and docs.

    Use this before modifying significant code to understand architectural intent
    and prevent re-introducing previously solved problems.

    Args:
        query: Natural language question (e.g. "why is auth using JWT?").
        repo: Repository path, name, or ID.
    """
    from wikicode.core.persistence.crud import list_decisions as _list_decisions

    async with get_session(_session_factory) as session:
        repository = await _get_repo(session, repo)

        # Keyword match on decision title and body
        all_decisions = await _list_decisions(
            session, repository.id, include_proposed=False, limit=200
        )

    # Score decisions by keyword relevance
    query_lower = query.lower()
    query_words = set(query_lower.split())
    scored_decisions = []
    for d in all_decisions:
        text = f"{d.title} {d.decision} {d.rationale}".lower()
        match_count = sum(1 for w in query_words if w in text)
        if match_count > 0:
            scored_decisions.append((match_count, d))
    scored_decisions.sort(key=lambda t: t[0], reverse=True)
    keyword_matches = [d for _, d in scored_decisions[:5]]

    # Semantic search over decision vector store
    decision_results = []
    try:
        decision_results = await _decision_store.search(query, limit=5)
    except Exception:
        pass

    # Semantic search over documentation
    doc_results = []
    try:
        doc_results = await _vector_store.search(query, limit=3)
    except Exception:
        try:
            doc_results = await _fts.search(query, limit=3)
        except Exception:
            pass

    # Merge keyword matches with semantic results (dedup by ID)
    seen_ids: set[str] = set()
    merged_decisions = []
    for d in keyword_matches:
        if d.id not in seen_ids:
            seen_ids.add(d.id)
            merged_decisions.append({
                "id": d.id,
                "title": d.title,
                "status": d.status,
                "decision": d.decision,
                "rationale": d.rationale,
                "consequences": json.loads(d.consequences_json),
                "affected_files": json.loads(d.affected_files_json),
                "source": d.source,
                "confidence": d.confidence,
            })

    # Add semantic decision results (from vector store — these are SearchResult objects)
    for r in decision_results:
        if r.page_id not in seen_ids:
            seen_ids.add(r.page_id)
            merged_decisions.append({
                "id": r.page_id,
                "title": r.title,
                "snippet": r.snippet,
                "relevance_score": r.score,
            })

    return {
        "query": query,
        "decisions": merged_decisions[:8],
        "related_documentation": [
            {
                "page_id": r.page_id,
                "title": r.title,
                "page_type": r.page_type,
                "snippet": r.snippet,
                "relevance_score": r.score,
            }
            for r in doc_results[:3]
        ],
    }


# ---------------------------------------------------------------------------
# Tool 16: get_decision_health
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_decision_health(repo: str | None = None) -> dict:
    """Get the health status of architectural decision records.

    Returns stale decisions, ungoverned hotspots (high-churn files with no
    decisions), and proposed decisions awaiting confirmation.

    Args:
        repo: Repository path, name, or ID.
    """
    from wikicode.core.persistence.crud import get_decision_health_summary

    async with get_session(_session_factory) as session:
        repository = await _get_repo(session, repo)
        health = await get_decision_health_summary(session, repository.id)

    stale = health["stale_decisions"]
    proposed = health["proposed_awaiting_review"]
    ungoverned = health["ungoverned_hotspots"]

    return {
        "summary": (
            f"{health['summary'].get('active', 0)} active · "
            f"{health['summary'].get('stale', 0)} stale · "
            f"{len(proposed)} proposed · "
            f"{len(ungoverned)} ungoverned hotspots"
        ),
        "counts": health["summary"],
        "stale_decisions": [
            {
                "id": d.id,
                "title": d.title,
                "staleness_score": d.staleness_score,
                "affected_files": json.loads(d.affected_files_json)[:5],
            }
            for d in stale[:10]
        ],
        "proposed_awaiting_review": [
            {
                "id": d.id,
                "title": d.title,
                "source": d.source,
                "confidence": d.confidence,
            }
            for d in proposed[:10]
        ],
        "ungoverned_hotspots": ungoverned[:15],
    }


# ---------------------------------------------------------------------------
# Server runner
# ---------------------------------------------------------------------------


def create_mcp_server(repo_path: str | None = None) -> FastMCP:
    """Create and return the MCP server instance, optionally scoped to a repo."""
    global _repo_path  # noqa: PLW0603
    _repo_path = repo_path
    return mcp


def run_mcp(
    transport: str = "stdio",
    repo_path: str | None = None,
    port: int = 7338,
) -> None:
    """Run the MCP server with the specified transport."""
    global _repo_path  # noqa: PLW0603
    _repo_path = repo_path

    if transport == "sse":
        mcp.settings.port = port
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
