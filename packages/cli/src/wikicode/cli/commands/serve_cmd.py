"""``wikicode serve`` — start the FastAPI web server."""

from __future__ import annotations

import click

from wikicode.cli.helpers import console


@click.command("serve")
@click.option("--port", default=7337, type=int, help="Port to listen on.")
@click.option("--host", default="127.0.0.1", help="Host to bind to.")
@click.option("--workers", default=1, type=int, help="Number of uvicorn workers.")
def serve_command(port: int, host: str, workers: int) -> None:
    """Start a local web server for browsing wiki pages."""
    try:
        import uvicorn
    except ImportError:
        console.print(
            "[red]uvicorn is not installed. "
            "Install wikicode-server: pip install wikicode-server[/red]"
        )
        raise SystemExit(1)

    console.print(f"[green]Starting WikiCode server on {host}:{port}[/green]")
    uvicorn.run(
        "wikicode.server.app:create_app",
        factory=True,
        host=host,
        port=port,
        workers=workers,
        log_level="info",
    )
