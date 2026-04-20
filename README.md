# claude-code-sessions

A terminal UI (TUI) tool to browse, inspect, and resume [Claude Code](https://claude.ai/code) sessions stored in `~/.claude/projects/`.

![Python](https://img.shields.io/badge/python-3.9%2B-blue) ![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey)

## Features

- Browse all local Claude Code sessions in an interactive table
- Sortable columns: date, project, input tokens, output tokens, total tokens
- Live filter with `/` (search by project or model)
- Detail view: git branch, last prompt, token breakdown, tools used, modified files
- Resume a session directly from the TUI (`o` key → launches `claude --resume <id>`)
- Delete sessions (`d` key) with confirmation
- Vim-style navigation (`j`/`k`)
- Color-coded output, recent sessions highlighted

## Requirements

- Python 3.9+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and accessible as `claude` in your `$PATH`

No external Python dependencies — uses only the standard library (`curses`, `json`, `pathlib`, …).

## Installation

```bash
pip install git+https://github.com/ssoto/claude-code-sessions.git
```

## Usage

```bash
claude-sessions
```

## Keybindings

### Table view

| Key | Action |
|-----|--------|
| `↑` / `↓` or `j` / `k` | Move cursor |
| `Enter` | Open session detail |
| `1`–`5` | Sort by Date / Project / In / Out / Total |
| `/` | Activate filter (type to search, `Esc` to clear, `Enter` to confirm) |
| `d` | Delete selected session (asks confirmation) |
| `q` / `Esc` | Quit |

### Detail view

| Key | Action |
|-----|--------|
| `↑` / `↓` or `j` / `k` | Scroll |
| `PgUp` / `PgDn` | Scroll by page |
| `o` | Resume session in Claude Code |
| `q` / `Esc` | Back to table |

## Session data location

Sessions are read from `~/.claude/projects/`. This directory is created and managed by Claude Code — each subdirectory corresponds to a project, and each `.jsonl` file is one session.

## License

MIT
