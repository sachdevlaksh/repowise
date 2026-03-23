"""``wikicode export`` — export wiki pages to markdown, HTML, or JSON."""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.progress import Progress

from wikicode.cli.helpers import (
    console,
    ensure_wikicode_dir,
    get_db_url_for_repo,
    resolve_repo_path,
    run_async,
)


@click.command("export")
@click.argument("path", required=False, default=None)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["markdown", "html", "json"]),
    default="markdown",
    help="Output format.",
)
@click.option("--output", "-o", "output_dir", default=None, help="Output directory (default: .wikicode/export).")
def export_command(
    path: str | None,
    fmt: str,
    output_dir: str | None,
) -> None:
    """Export wiki pages to files."""
    repo_path = resolve_repo_path(path)
    ensure_wikicode_dir(repo_path)

    if output_dir is None:
        out = repo_path / ".wikicode" / "export"
    else:
        out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    # Load pages from DB
    async def _load_pages():
        from wikicode.core.persistence import (
            create_engine,
            create_session_factory,
            get_session,
            list_pages,
            get_repository_by_path,
        )

        url = get_db_url_for_repo(repo_path)
        engine = create_engine(url)
        sf = create_session_factory(engine)

        async with get_session(sf) as session:
            repo = await get_repository_by_path(session, str(repo_path))
            if repo is None:
                await engine.dispose()
                return []
            pages = await list_pages(session, repo.id, limit=10000)

        await engine.dispose()
        return pages

    pages = run_async(_load_pages())

    if not pages:
        console.print("[yellow]No pages found. Run 'wikicode init' first.[/yellow]")
        return

    with Progress(console=console) as progress:
        task = progress.add_task(f"Exporting {len(pages)} pages as {fmt}...", total=len(pages))

        if fmt == "markdown":
            for page in pages:
                safe_name = (
                    page.target_path
                    .replace("/", "_")
                    .replace("::", "__")
                    .replace("->", "--")
                    .replace(">", "")
                    .replace("<", "")
                    .replace(":", "_")
                    .replace("\\", "_")
                    .replace("|", "_")
                    .replace("?", "")
                    .replace("*", "")
                    .replace('"', "")
                )
                filepath = out / f"{safe_name}.md"
                filepath.write_text(
                    f"# {page.title}\n\n{page.content}",
                    encoding="utf-8",
                )
                progress.advance(task)

        elif fmt == "html":
            for page in pages:
                safe_name = (
                    page.target_path
                    .replace("/", "_")
                    .replace("::", "__")
                    .replace("->", "--")
                    .replace(">", "")
                    .replace("<", "")
                    .replace(":", "_")
                    .replace("\\", "_")
                    .replace("|", "_")
                    .replace("?", "")
                    .replace("*", "")
                    .replace('"', "")
                )
                filepath = out / f"{safe_name}.html"
                html = (
                    "<!DOCTYPE html>\n<html>\n<head>\n"
                    f"<title>{page.title}</title>\n"
                    '<meta charset="utf-8">\n'
                    "</head>\n<body>\n"
                    f"<h1>{page.title}</h1>\n"
                    f"<pre>{page.content}</pre>\n"
                    "</body>\n</html>"
                )
                filepath.write_text(html, encoding="utf-8")
                progress.advance(task)

        elif fmt == "json":
            data = []
            for page in pages:
                data.append({
                    "page_id": page.id,
                    "page_type": page.page_type,
                    "title": page.title,
                    "content": page.content,
                    "target_path": page.target_path,
                })
                progress.advance(task)
            filepath = out / "wiki_pages.json"
            filepath.write_text(json.dumps(data, indent=2), encoding="utf-8")

    console.print(f"[bold green]Exported {len(pages)} pages to {out}[/bold green]")
