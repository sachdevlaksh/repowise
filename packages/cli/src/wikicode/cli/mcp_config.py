"""Auto-generated MCP config for Claude Code, Cursor, and Cline."""

from __future__ import annotations

import json
from pathlib import Path


def generate_mcp_config(repo_path: Path) -> dict:
    """Generate MCP config JSON for a repository.

    Returns a dict in the standard mcpServers format.
    """
    abs_path = str(repo_path.resolve()).replace("\\", "/")
    return {
        "mcpServers": {
            "wikicode": {
                "command": "wikicode",
                "args": ["mcp", abs_path, "--transport", "stdio"],
                "description": "WikiCode: live documentation for this codebase",
            }
        }
    }


def save_mcp_config(repo_path: Path) -> Path:
    """Save MCP config to .wikicode/mcp.json and return the path."""
    wikicode_dir = repo_path / ".wikicode"
    wikicode_dir.mkdir(parents=True, exist_ok=True)
    config_path = wikicode_dir / "mcp.json"
    config = generate_mcp_config(repo_path)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return config_path


def format_setup_instructions(repo_path: Path) -> str:
    """Return human-readable setup instructions for MCP clients."""
    config = generate_mcp_config(repo_path)
    server_block = json.dumps(config["mcpServers"]["wikicode"], indent=4)
    abs_path = str(repo_path.resolve()).replace("\\", "/")

    return f"""
MCP Server Configuration
========================

Add the following to your editor's MCP config:

Claude Code (~/.claude.json or ~/.claude/claude.json):
  "mcpServers": {{
    "wikicode": {server_block}
  }}

Cursor (.cursor/mcp.json):
  {server_block}

Cline (cline_mcp_settings.json):
  "mcpServers": {{
    "wikicode": {server_block}
  }}

Or run directly:
  wikicode mcp {abs_path}
  wikicode mcp {abs_path} --transport sse --port 7338

Config saved to: {repo_path / '.wikicode' / 'mcp.json'}
""".strip()
