# wikicode-cli

Command-line interface for WikiCode — generate, maintain, search, and export AI-powered codebase documentation from your terminal.

**Python >= 3.11 · Apache-2.0**

---

## Installation

```bash
pip install wikicode-cli

# Recommended: use uv
uv pip install wikicode-cli
```

`wikicode-core` is installed automatically as a dependency. The `wikicode` command is available immediately after installation.

---

## Quick Start

```bash
# 1. Generate documentation for the first time
cd /path/to/your/repo
wikicode init --provider anthropic

# 2. Check what was generated
wikicode status

# 3. Keep docs in sync after commits
wikicode update

# 4. Search the wiki
wikicode search "authentication flow"

# 5. Start the web UI
wikicode serve
```

All data is stored in a `.wikicode/` directory at the root of your repository.

---

## Commands

### `wikicode init`

Generate full wiki documentation from scratch. This is the expensive, one-time operation — it traverses every file, builds the dependency graph, and calls the LLM to generate all wiki pages in dependency order. It is resumable: if interrupted, re-run with `--resume`.

```
wikicode init [PATH] [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--provider` | `anthropic` | LLM provider: `anthropic`, `openai`, `ollama`, `litellm` |
| `--model` | provider default | Model identifier (e.g., `claude-opus-4-6`, `gpt-4o`) |
| `--concurrency` | `5` | Max simultaneous LLM calls |
| `--skip-tests` | off | Skip test files during generation |
| `--resume` | off | Resume an interrupted init job from last checkpoint |
| `--dry-run` | off | Show generation plan and cost estimate without calling the LLM |
| `--no-batch` | off | Disable Anthropic batch API (faster wall-clock time, higher cost) |

```bash
# Current directory, Anthropic (default)
wikicode init

# Specific path and provider
wikicode init /path/to/repo --provider openai --model gpt-4o

# Fully offline with Ollama
wikicode init --provider ollama --model llama3.2

# Preview cost before spending tokens
wikicode init --dry-run

# Resume after an interruption
wikicode init --resume
```

**Batch API:** When using the Anthropic provider, `wikicode init` uses the Message Batches API by default, which reduces cost by ~50%. Pass `--no-batch` to use streaming instead (returns results immediately, costs more).

**Prompt caching:** The Anthropic provider caches the shared system prompt and repository context across all generation calls. On large repos, this typically cuts cost by 60–90%.

---

### `wikicode update`

Incrementally regenerate wiki pages for files changed since the last sync. Uses git diff to detect what changed and propagates changes through the dependency graph — only pages that actually need updating are regenerated.

```
wikicode update [PATH] [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--provider` | last used | LLM provider |
| `--model` | provider default | Model override |
| `--since` | last sync commit | Base git ref to diff from (overrides saved state) |
| `--cascade-budget` | `30` | Max pages to regenerate per run |
| `--dry-run` | off | Show affected pages without regenerating |

```bash
# Update current repo (diffs HEAD against last sync commit)
wikicode update

# Preview what would be regenerated
wikicode update --dry-run

# Diff from a specific branch or commit
wikicode update --since main
wikicode update --since a1b2c3d
```

`wikicode update` requires that `wikicode init` has been run first. It reads `last_sync_commit` from `.wikicode/state.json`.

---

### `wikicode watch`

Watch a repository for file changes and automatically run `wikicode update` after a debounce period. Useful during active development.

```
wikicode watch [PATH] [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--provider` | last used | LLM provider |
| `--model` | provider default | Model override |
| `--debounce` | `2000` | Milliseconds to wait after the last change before updating |

```bash
# Watch current directory
wikicode watch

# Custom debounce (wait 5 seconds after last change)
wikicode watch --debounce 5000
```

Press `Ctrl+C` to stop. Changes to `.wikicode/` are automatically ignored.

---

### `wikicode search`

Search wiki pages by keyword, meaning, or symbol name.

```
wikicode search QUERY [PATH] [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--mode` | `fulltext` | Search mode: `fulltext`, `semantic`, `symbol` |
| `--limit` | `10` | Maximum results to return |

```bash
# Full-text search (SQLite FTS5)
wikicode search "authentication"

# Semantic / vector search
wikicode search "rate limiting strategy" --mode semantic

# Find a symbol by name
wikicode search "AuthService" --mode symbol
```

`semantic` search requires the `[search]` extra (`pip install "wikicode-core[search]"`).

---

### `wikicode export`

Export all wiki pages to files on disk in Markdown, HTML, or JSON format.

```
wikicode export [PATH] [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--format` | `markdown` | Output format: `markdown`, `html`, `json` |
| `--output`, `-o` | `.wikicode/export` | Output directory |

```bash
# Export as Markdown to .wikicode/export/
wikicode export

# Export as JSON to a custom directory
wikicode export --format json -o ./wiki-export

# Export as HTML
wikicode export --format html -o ./docs/wiki
```

The JSON output is a single `wiki_pages.json` file with all pages as an array. Markdown and HTML outputs write one file per page.

---

### `wikicode status`

Show sync state, page counts by type, and total token consumption.

```
wikicode status [PATH]
```

Displays:

- Last sync commit hash
- Provider and model used for the last init/update
- Total token consumption (input + output)
- Page count broken down by type (`file_page`, `module_page`, `symbol_spotlight`, etc.)

---

### `wikicode doctor`

Run health checks on the wiki setup. Useful for debugging why `init` or `update` is failing.

```
wikicode doctor [PATH]
```

Checks performed:

| Check | What it verifies |
|-------|-----------------|
| Git repository | The path is inside a git repo |
| `.wikicode/` directory | The init directory exists |
| Database | `wiki.db` is connectable; shows page count |
| `state.json` | Valid JSON with a `last_sync_commit` entry |
| Providers | At least one LLM provider is importable |
| Stale pages | Number of pages whose source has changed since generation |

Exits with a summary of passed/failed checks.

---

### `wikicode dead-code`

Detect dead and unused code using the dependency graph. Does not call an LLM — purely graph analysis and git metadata.

```
wikicode dead-code [PATH] [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--min-confidence` | `0.4` | Minimum confidence threshold (0.0–1.0) |
| `--safe-only` | off | Only show findings marked as safe to delete |
| `--kind` | all | Filter: `unreachable_file`, `unused_export`, `unused_internal`, `zombie_package` |
| `--format` | `table` | Output: `table`, `json`, `md` |

```bash
# All findings, table format
wikicode dead-code

# Only safe-to-delete findings
wikicode dead-code --safe-only

# Only unreachable files (no importers in the graph)
wikicode dead-code --kind unreachable_file

# Export to JSON for CI integration
wikicode dead-code --format json > dead-code.json

# High-confidence findings only
wikicode dead-code --min-confidence 0.8
```

Finding kinds:

| Kind | Description |
|------|-------------|
| `unreachable_file` | File has no importers in the dependency graph |
| `unused_export` | Symbol is exported but not imported anywhere |
| `unused_internal` | Symbol is defined but never called within the repo |
| `zombie_package` | Package directory exists but has no live references |

---

### `wikicode serve`

Start the WikiCode REST API and web UI server. Requires `wikicode-server` to be installed.

```
wikicode serve [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--port` | `7337` | Port to listen on |
| `--host` | `127.0.0.1` | Host to bind to (`0.0.0.0` to expose externally) |
| `--workers` | `1` | Number of uvicorn workers |

```bash
# Start on localhost:7337
wikicode serve

# Expose on all interfaces
wikicode serve --host 0.0.0.0

# Custom port
wikicode serve --port 8080
```

The API docs are available at `http://localhost:7337/docs`. Start the Next.js web UI separately and point `WIKICODE_API_URL` at this server.

---

### `wikicode mcp`

Start the MCP server for AI editor integration (Claude Code, Cursor, Cline).

```
wikicode mcp [PATH] [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--transport` | `stdio` | Transport protocol: `stdio` (editors) or `sse` (web clients) |
| `--port` | `7338` | Port for SSE transport |

```bash
# stdio transport, current directory (typical editor integration)
wikicode mcp

# Specific repository path
wikicode mcp /path/to/repo

# SSE transport for web clients
wikicode mcp --transport sse
```

Exposes 13 MCP tools for querying wiki pages, symbols, the dependency graph, git analytics, ownership data, hotspots, and dead code findings.

**Claude Code setup** — add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "wikicode": {
      "command": "wikicode",
      "args": ["mcp", "/path/to/your/repo"]
    }
  }
}
```

**Cursor / Cline setup** — add to your MCP configuration file:

```json
{
  "mcpServers": {
    "wikicode": {
      "command": "wikicode",
      "args": ["mcp", "/absolute/path/to/repo"]
    }
  }
}
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | API key for the Anthropic provider |
| `OPENAI_API_KEY` | API key for the OpenAI provider |
| `WIKICODE_DB_URL` | Override the default SQLite path (e.g., `postgresql://user:pass@host/db`) |
| `WIKICODE_EMBEDDER` | Embedder backend: `mock` (default) or `gemini` |

---

## The `.wikicode/` Directory

After `wikicode init`, your repo will contain:

```
.wikicode/
├── wiki.db         # SQLite database — all pages, symbols, jobs, git metadata
├── lancedb/        # LanceDB vector store (if [search] extra is installed)
├── graph.json      # Serialized dependency graph (repos < 30K nodes)
├── state.json      # Sync state: last_sync_commit, provider, model, token counts
└── export/         # Output directory for `wikicode export`
```

Add `.wikicode/` to your `.gitignore` to avoid committing generated data.

---

## Development

```bash
# Install for development (from repo root)
uv pip install -e packages/cli -e packages/core

# Run tests
pytest tests/unit/cli/
```
