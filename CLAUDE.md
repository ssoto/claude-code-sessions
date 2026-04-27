# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Dev install (editable)
pip install -e .

# Run
claude-code-sessions

# CLI modes
claude-code-sessions list        # JSON output of all sessions
claude-code-sessions show <id>   # JSON detail for one session
```

No test suite or linter configured. Single-file stdlib-only project.

## Architecture

Single Python file: `claude_sessions.py`. Entry point: `main()`.

**Data flow:** `collect_sessions()` → scans `~/.claude/projects/**/*.jsonl` → `parse_session()` per file → sorted list of session dicts → TUI or CLI output.

**Session JSONL format:** Claude Code writes conversation turns as JSONL. Parser extracts model, timestamps, token counts (input/output/cache creation/cache read), tool usage (Counter from assistant blocks), modified files (from `file-history-snapshot` events), git branch, working directory, last user prompt.

**TUI state machine** in `tui()`: two views — table (default) and detail. Table supports column sort (keys 1-5), live filter (`/`), vim navigation. Detail view accessed via Enter, exits with Esc. Session resume uses `os.execvp("claude", ["claude", "--resume", session_id])` after `os.chdir()` to session's working dir.

**Color pairs** defined at module level (16 pairs) using curses constants — all rendering functions reference these.

**CLI mode** (`list`/`show` subcommands) skips curses entirely, outputs JSON to stdout for piping.

**First-run welcome** stored in `~/.claude/claude-sessions-welcomed-<version>` sentinel file.

## Key constraints

- Python ≥3.9, stdlib only (no pip dependencies)
- Package name: `claude-code-sessions`, import name: `claude_sessions`
- AGPL-3.0 licensed
