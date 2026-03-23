"""``wikicode mcp`` — Start the MCP server for editor integration."""

from __future__ import annotations

import click

from wikicode.cli.helpers import console, resolve_repo_path


@click.command("mcp")
@click.argument("path", required=False, default=None)
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    help="Transport protocol: stdio (Claude Code/Cursor) or sse (web clients).",
)
@click.option(
    "--port",
    type=int,
    default=7338,
    help="Port for SSE transport (default: 7338).",
)
def mcp_command(path: str | None, transport: str, port: int) -> None:
    """Start the MCP server for editor integration.

    Exposes 13 tools for querying the WikiCode wiki via the MCP protocol.
    Supports both stdio (for Claude Code, Cursor, Cline) and SSE transports.

    Examples:

        wikicode mcp                     # stdio, current directory
        wikicode mcp /path/to/repo       # stdio, specific repo
        wikicode mcp --transport sse     # SSE on port 7338
    """
    repo_path = resolve_repo_path(path)

    wikicode_dir = repo_path / ".wikicode"
    if not wikicode_dir.exists():
        console.print(
            f"[yellow]Warning: No .wikicode directory found at {repo_path}.[/yellow]\n"
            "Run 'wikicode init' first to generate documentation."
        )

    if transport == "sse":
        console.print(
            f"[bold green]Starting WikiCode MCP server (SSE) on port {port}...[/bold green]"
        )
    else:
        # stdio mode — no console output (it would corrupt the protocol)
        pass

    from wikicode.server.mcp_server import run_mcp

    run_mcp(
        transport=transport,
        repo_path=str(repo_path),
        port=port,
    )
