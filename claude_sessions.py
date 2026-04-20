#!/usr/bin/env python3
"""
Claude Code Session Token Viewer
Parses ~/.claude/projects/ JSONL files to show token usage per session.
Navigate with arrow keys, Enter to view detail, q to quit.
"""

import curses
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict, Counter


CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"

# Color pair IDs
C_TITLE     = 1   # title bar
C_HEADER    = 2   # column headers
C_SEP       = 3   # separator line
C_DATE      = 4   # date column
C_PROJECT   = 5   # project column
C_NUM       = 6   # token numbers
C_MODEL     = 7   # model name
C_CURSOR    = 8   # selected row
C_FOOTER    = 9   # footer bar
C_LABEL     = 10  # detail labels
C_VALUE     = 11  # detail values
C_TOTAL     = 12  # total row highlight
C_BTN       = 13  # open button
C_SORT_IND  = 14  # sort arrow indicator
C_RECENT    = 15  # sessions from last 24h


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    bg = -1  # transparent background

    curses.init_pair(C_TITLE,    curses.COLOR_BLACK,  curses.COLOR_CYAN)
    curses.init_pair(C_HEADER,   curses.COLOR_CYAN,   bg)
    curses.init_pair(C_SEP,      curses.COLOR_BLUE,   bg)
    curses.init_pair(C_DATE,     curses.COLOR_YELLOW, bg)
    curses.init_pair(C_PROJECT,  curses.COLOR_WHITE,  bg)
    curses.init_pair(C_NUM,      curses.COLOR_GREEN,  bg)
    curses.init_pair(C_MODEL,    curses.COLOR_MAGENTA,bg)
    curses.init_pair(C_CURSOR,   curses.COLOR_BLACK,  curses.COLOR_CYAN)
    curses.init_pair(C_FOOTER,   curses.COLOR_BLACK,  curses.COLOR_BLUE)
    curses.init_pair(C_LABEL,    curses.COLOR_CYAN,   bg)
    curses.init_pair(C_VALUE,    curses.COLOR_WHITE,  bg)
    curses.init_pair(C_TOTAL,    curses.COLOR_GREEN,  bg)
    curses.init_pair(C_BTN,      curses.COLOR_BLACK,  curses.COLOR_GREEN)
    curses.init_pair(C_SORT_IND, curses.COLOR_YELLOW, bg)
    curses.init_pair(C_RECENT,   curses.COLOR_WHITE,  bg)
    curses.init_pair(C_DANGER,   curses.COLOR_WHITE,  curses.COLOR_RED)


def parse_session(jsonl_path: Path) -> dict:
    session_id = jsonl_path.stem
    totals = defaultdict(int)
    first_ts = None
    last_ts = None
    project = jsonl_path.parent.name
    model = None
    message_count = 0
    cwd = None
    git_branch = None
    entrypoint = None
    permission_mode = None
    last_prompt = None
    tools_used = Counter()
    modified_files = set()

    try:
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                t = obj.get("type")

                if cwd is None and "cwd" in obj:
                    cwd = obj["cwd"]
                if git_branch is None and "gitBranch" in obj:
                    git_branch = obj["gitBranch"]
                if entrypoint is None and "entrypoint" in obj:
                    entrypoint = obj["entrypoint"]

                if t == "permission-mode":
                    permission_mode = obj.get("permissionMode")

                if t == "last-prompt":
                    last_prompt = obj.get("lastPrompt")

                if t == "file-history-snapshot":
                    snap = obj.get("snapshot", {})
                    for fpath in (snap.get("trackedFileBackups") or {}).keys():
                        modified_files.add(fpath)

                ts_str = obj.get("timestamp")
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        if first_ts is None or ts < first_ts:
                            first_ts = ts
                        if last_ts is None or ts > last_ts:
                            last_ts = ts
                    except ValueError:
                        pass

                msg = obj.get("message", {})

                # Count tool uses from assistant messages
                if t == "assistant":
                    for block in (msg.get("content") or []):
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            tools_used[block["name"]] += 1

                usage = msg.get("usage")
                if usage:
                    message_count += 1
                    if model is None:
                        model = msg.get("model")
                    totals["input_tokens"] += usage.get("input_tokens", 0)
                    totals["output_tokens"] += usage.get("output_tokens", 0)
                    totals["cache_creation_input_tokens"] += usage.get(
                        "cache_creation_input_tokens", 0
                    )
                    totals["cache_read_input_tokens"] += usage.get(
                        "cache_read_input_tokens", 0
                    )
    except (OSError, PermissionError):
        return None

    return {
        "session_id": session_id,
        "project": project,
        "model": model or "unknown",
        "first_ts": first_ts,
        "last_ts": last_ts,
        "message_count": message_count,
        "input_tokens": totals["input_tokens"],
        "output_tokens": totals["output_tokens"],
        "cache_creation_tokens": totals["cache_creation_input_tokens"],
        "cache_read_tokens": totals["cache_read_input_tokens"],
        "total_tokens": totals["input_tokens"] + totals["output_tokens"],
        "cwd": cwd,
        "git_branch": git_branch,
        "entrypoint": entrypoint,
        "permission_mode": permission_mode,
        "last_prompt": last_prompt,
        "tools_used": dict(tools_used),
        "modified_files": sorted(modified_files),
        "path": jsonl_path,
    }


def collect_sessions(limit: int = 50) -> list[dict]:
    sessions = []

    if not CLAUDE_PROJECTS.exists():
        print(f"Error: {CLAUDE_PROJECTS} not found.")
        sys.exit(1)

    for project_dir in CLAUDE_PROJECTS.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl in project_dir.glob("*.jsonl"):
            data = parse_session(jsonl)
            if data and data["message_count"] > 0:
                sessions.append(data)

    sessions.sort(
        key=lambda s: s["last_ts"] or datetime.min.replace(tzinfo=None),
        reverse=True,
    )
    return sessions[:limit]


def fmt_ts(ts) -> str:
    if ts is None:
        return "unknown"
    return ts.strftime("%Y-%m-%d %H:%M")


def fmt_num(n: int) -> str:
    return f"{n:,}"


def is_recent(ts) -> bool:
    """True if session was active in the last 24 hours."""
    if ts is None:
        return False
    now = datetime.now(tz=timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (now - ts).total_seconds() < 86400


SORT_KEYS   = ["last_ts", "project", "input_tokens", "output_tokens", "total_tokens"]
SORT_LABELS = ["Date", "Project", "In", "Out", "Total"]
COL_HINT    = "  1:Date  2:Project  3:In  4:Out  5:Total"

MODEL_W  = 24
FIXED_W  = 4 + 1 + 17 + 1 + 1 + 10 + 1 + 10 + 1 + 10 + 2 + MODEL_W
MIN_PROJ_W = 10


def sorted_sessions(sessions, sort_col, sort_asc):
    key = SORT_KEYS[sort_col]
    reverse = not sort_asc
    if sort_col == 0:
        none_last = datetime.min.replace(tzinfo=None)
    elif sort_col == 1:
        none_last = ""
    else:
        none_last = 0
    return sorted(
        sessions,
        key=lambda s: (s[key] is None, s[key] if s[key] is not None else none_last),
        reverse=reverse,
    )


def proj_width(terminal_w):
    return max(MIN_PROJ_W, terminal_w - FIXED_W)


def addstr_clipped(win, row, col, text, attr, max_w):
    """Write text clipped to max_w chars from col."""
    available = max_w - col
    if available <= 0:
        return
    win.addstr(row, col, text[:available], attr)


def draw_header(stdscr, sort_col, sort_asc, pw, w):
    arrow = "▲" if sort_asc else "▼"
    cols = list(SORT_LABELS)

    # Build column positions manually so we can color each segment
    col = 0
    # "#   "
    addstr_clipped(stdscr, 1, col, f"{'#':<4} ", curses.color_pair(C_HEADER) | curses.A_BOLD, w)
    col += 5

    for i, (label, width, align) in enumerate([
        (cols[0], 17, "<"),
        (cols[1], pw,  "<"),
        (cols[2], 10, ">"),
        (cols[3], 10, ">"),
        (cols[4], 10, ">"),
    ]):
        is_sort = (i == sort_col)
        text = f"{label}{arrow}" if is_sort else label
        if align == "<":
            formatted = f"{text:<{width}}"
        else:
            formatted = f"{text:>{width}}"
        attr = (curses.color_pair(C_SORT_IND) | curses.A_BOLD) if is_sort else (curses.color_pair(C_HEADER) | curses.A_BOLD)
        addstr_clipped(stdscr, 1, col, formatted + " ", attr, w)
        col += width + 1

    # "Model"
    addstr_clipped(stdscr, 1, col, " Model", curses.color_pair(C_HEADER) | curses.A_BOLD, w)


def draw_table(stdscr, sessions, cursor, scroll, sort_col, sort_asc, filter_text="", esc_pending=False):
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    # Title bar
    if filter_text is not None:
        active = f"{filter_text}█" if filter_text else "█"
        title = f" Filter: {active}  Esc clear  Enter confirm "
        stdscr.addstr(0, 0, title[:w].ljust(w - 1), curses.color_pair(C_BTN) | curses.A_BOLD)
    else:
        title = " Claude Code Sessions — ↑↓ navigate  Enter detail  / filter  d delete  q quit "
        stdscr.addstr(0, 0, title[:w].ljust(w - 1), curses.color_pair(C_TITLE) | curses.A_BOLD)

    pw = proj_width(w)
    draw_header(stdscr, sort_col, sort_asc, pw, w)

    sep = "─" * (w - 1)
    addstr_clipped(stdscr, 2, 0, sep, curses.color_pair(C_SEP), w)

    visible = h - 5
    for i in range(visible):
        idx = scroll + i
        if idx >= len(sessions):
            break
        s = sessions[idx]
        is_cursor = (idx == cursor)
        recent = is_recent(s["last_ts"])

        if is_cursor:
            cp_date = cp_proj = cp_num = cp_model = curses.color_pair(C_CURSOR)
            base_attr = curses.color_pair(C_CURSOR)
        elif recent:
            cp_date  = curses.color_pair(C_DATE)   | curses.A_BOLD
            cp_proj  = curses.color_pair(C_RECENT) | curses.A_BOLD
            cp_num   = curses.color_pair(C_NUM)    | curses.A_BOLD
            cp_model = curses.color_pair(C_MODEL)  | curses.A_BOLD
            base_attr = curses.color_pair(C_RECENT) | curses.A_BOLD
        else:
            cp_date  = curses.color_pair(C_DATE)
            cp_proj  = curses.color_pair(C_PROJECT)
            cp_num   = curses.color_pair(C_NUM)
            cp_model = curses.color_pair(C_MODEL)
            base_attr = curses.color_pair(C_PROJECT)

        row_y = 3 + i
        col = 0

        addstr_clipped(stdscr, row_y, col, f"{idx+1:<4} ", base_attr, w)
        col += 5

        addstr_clipped(stdscr, row_y, col, f"{fmt_ts(s['last_ts']):<17} ", cp_date, w)
        col += 18

        proj = s["project"][:pw]
        addstr_clipped(stdscr, row_y, col, f"{proj:<{pw}} ", cp_proj, w)
        col += pw + 1

        addstr_clipped(stdscr, row_y, col, f"{fmt_num(s['input_tokens']):>10} ", cp_num, w)
        col += 11
        addstr_clipped(stdscr, row_y, col, f"{fmt_num(s['output_tokens']):>10} ", cp_num, w)
        col += 11
        addstr_clipped(stdscr, row_y, col, f"{fmt_num(s['total_tokens']):>10}  ", cp_num, w)
        col += 12

        addstr_clipped(stdscr, row_y, col, s["model"][:MODEL_W], cp_model, w)

    sort_label = SORT_LABELS[sort_col]
    dir_label  = "asc" if sort_asc else "desc"
    filter_hint = f"  filter: \"{filter_text}\"" if filter_text is not None else ""
    if esc_pending:
        footer = " Press Esc again to quit "
        stdscr.addstr(h - 1, 0, footer[:w - 1].ljust(w - 1), curses.color_pair(C_DANGER) | curses.A_BOLD)
    else:
        footer = f" {cursor+1}/{len(sessions)}  sorted by {sort_label} {dir_label}{COL_HINT}{filter_hint} "
        stdscr.addstr(h - 1, 0, footer[:w - 1].ljust(w - 1), curses.color_pair(C_FOOTER))
    stdscr.refresh()


def session_resumable(s) -> tuple[bool, str]:
    """Check if session can be resumed. Returns (ok, reason)."""
    path = s["path"]
    if not path.exists():
        return False, "session file not found on disk"
    if path.stat().st_size == 0:
        return False, "session file is empty"
    return True, ""


def build_detail_lines(s, w):
    """Build list of (text, color_pair, bold) for the detail view."""
    sep = "─" * min(60, w - 4)
    lines = []

    def row(label, value, val_cp=C_VALUE):
        lines.append((f"  {label:<24}", C_LABEL, False))
        lines[-1] = (f"  {label:<24}{str(value)}", val_cp, True)

    def section(title):
        lines.append((f"  {sep}", C_SEP, False))
        lines.append((f"  {title}", C_LABEL, True))
        lines.append((f"  {sep}", C_SEP, False))

    # Session info
    section("Session")
    row("Session ID",      s["session_id"])
    row("Project",         s["project"],              C_PROJECT)
    row("Model",           s["model"],                C_MODEL)
    row("Git branch",      s["git_branch"] or "—",    C_NUM)
    row("Entrypoint",      s["entrypoint"] or "—")
    row("Permission mode", s["permission_mode"] or "—")
    row("Directory",       s["cwd"] or "—")
    row("Start",           fmt_ts(s["first_ts"]),     C_DATE)
    row("End",             fmt_ts(s["last_ts"]),       C_DATE)
    row("Messages",        s["message_count"])

    # Last prompt
    section("Last prompt")
    prompt = s.get("last_prompt") or "—"
    # wrap to terminal width
    max_w = max(10, w - 6)
    for i in range(0, len(prompt), max_w):
        chunk = prompt[i:i + max_w]
        lines.append((f"  {chunk}", C_VALUE, False))

    # Tokens
    section("Token breakdown")
    row("Input tokens",          fmt_num(s["input_tokens"]),          C_NUM)
    row("Output tokens",         fmt_num(s["output_tokens"]),         C_NUM)
    row("Cache creation tokens", fmt_num(s["cache_creation_tokens"]), C_NUM)
    row("Cache read tokens",     fmt_num(s["cache_read_tokens"]),     C_NUM)
    lines.append((f"  {sep}", C_SEP, False))
    row("TOTAL tokens",          fmt_num(s["total_tokens"]),          C_TOTAL)

    # Tools used
    section("Tools used")
    tools = s.get("tools_used") or {}
    if tools:
        for tool, count in sorted(tools.items(), key=lambda x: -x[1]):
            row(f"  {tool}", count, C_NUM)
    else:
        lines.append(("  —", C_VALUE, False))

    # Modified files
    section("Modified files")
    files = s.get("modified_files") or []
    if files:
        for f in files:
            lines.append((f"  {f}"[:w - 2], C_VALUE, False))
    else:
        lines.append(("  —", C_VALUE, False))

    lines.append(("", C_VALUE, False))
    return lines


def draw_detail(stdscr, s):
    """Returns True if user chose to open session in Claude."""
    resumable, reason = session_resumable(s)
    lines = build_detail_lines(s, 80)  # built once, rebuilt on resize
    scroll = 0

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        lines = build_detail_lines(s, w)

        title = " Session detail — ↑↓/jk scroll  o open  Esc/q back "
        stdscr.addstr(0, 0, title[:w].ljust(w - 1), curses.color_pair(C_TITLE) | curses.A_BOLD)

        visible = h - 3  # title + footer + btn
        for i in range(visible):
            idx = scroll + i
            if idx >= len(lines):
                break
            text, cp, bold = lines[idx]
            attr = curses.color_pair(cp) | (curses.A_BOLD if bold else curses.A_NORMAL)
            addstr_clipped(stdscr, 1 + i, 0, text, attr, w)

        # Button / error row
        if resumable:
            btn = "  [ o ]  Open in Claude  "
            stdscr.addstr(h - 1, 0, btn[:w - 1].ljust(w - 1), curses.color_pair(C_BTN) | curses.A_BOLD)
        else:
            warn = f"  ✗ Cannot resume: {reason}  "
            stdscr.addstr(h - 1, 0, warn[:w - 1].ljust(w - 1), curses.color_pair(C_DANGER) | curses.A_BOLD)

        stdscr.refresh()
        key = stdscr.getch()

        max_scroll = max(0, len(lines) - visible)
        if key in (ord("q"), ord("Q"), 27, curses.KEY_LEFT):
            return False
        elif key in (ord("o"), ord("O")) and resumable:
            return True
        elif key in (curses.KEY_UP, ord("k"), ord("K")):
            scroll = max(0, scroll - 1)
        elif key in (curses.KEY_DOWN, ord("j"), ord("J")):
            scroll = min(max_scroll, scroll + 1)
        elif key == curses.KEY_PPAGE:
            scroll = max(0, scroll - visible)
        elif key == curses.KEY_NPAGE:
            scroll = min(max_scroll, scroll + visible)
        elif key == curses.KEY_HOME:
            scroll = 0
        elif key == curses.KEY_END:
            scroll = max_scroll
        elif key == curses.KEY_RESIZE:
            pass


C_DANGER = 16  # red confirm prompt


def confirm_delete(stdscr, s, w, h):
    """Overlay a confirmation bar at bottom. Returns True if user confirms."""
    msg = f" Delete \"{s['project']} / {s['session_id'][:12]}…\" ?  y confirm  any other key cancel "
    stdscr.addstr(h - 1, 0, msg[:w - 1].ljust(w - 1), curses.color_pair(C_DANGER) | curses.A_BOLD)
    stdscr.refresh()
    key = stdscr.getch()
    return key in (ord("y"), ord("Y"))


def apply_filter(sessions, text):
    if not text:
        return sessions
    needle = text.lower()
    return [s for s in sessions if needle in s["project"].lower() or needle in s["model"].lower()]


def tui(stdscr, all_sessions):
    curses.curs_set(0)
    init_colors()

    sort_col    = 0
    sort_asc    = False
    filter_text = ""
    filtering   = False   # True while user is typing filter

    def rebuild():
        base = sorted_sessions(all_sessions, sort_col, sort_asc)
        return apply_filter(base, filter_text)

    sessions = rebuild()
    cursor    = 0
    scroll    = 0
    esc_pending = False

    while True:
        h, _ = stdscr.getmaxyx()
        visible = h - 5
        draw_table(stdscr, sessions, cursor, scroll, sort_col, sort_asc,
                   filter_text if filtering else None, esc_pending)
        key = stdscr.getch()

        if filtering:
            if key == 27:                        # Esc — clear filter
                filter_text = ""
                filtering   = False
                sessions    = rebuild()
                cursor = scroll = 0
            elif key in (curses.KEY_ENTER, ord("\n"), ord("\r")):
                filtering = False                # confirm, keep filter
            elif key in (curses.KEY_BACKSPACE, 127):
                filter_text = filter_text[:-1]
                sessions    = rebuild()
                cursor = scroll = 0
            elif 32 <= key <= 126:               # printable ASCII
                filter_text += chr(key)
                sessions     = rebuild()
                cursor = scroll = 0
            continue

        # Normal navigation mode
        if key in (ord("q"), ord("Q")):
            break
        elif key == 27:
            if filter_text:
                filter_text = ""
                sessions    = rebuild()
                cursor = scroll = 0
            elif esc_pending:
                break
            else:
                esc_pending = True
                continue
        elif key == ord("/"):
            filtering = True
        elif key in (curses.KEY_UP, ord("k"), ord("K")):
            if cursor > 0:
                cursor -= 1
                if cursor < scroll:
                    scroll = cursor
        elif key in (curses.KEY_DOWN, ord("j"), ord("J")):
            if cursor < len(sessions) - 1:
                cursor += 1
                if cursor >= scroll + visible:
                    scroll = cursor - visible + 1
        elif key == curses.KEY_PPAGE:
            cursor = max(0, cursor - visible)
            scroll = max(0, scroll - visible)
        elif key == curses.KEY_NPAGE:
            cursor = min(len(sessions) - 1, cursor + visible)
            scroll = min(max(0, len(sessions) - visible), scroll + visible)
        elif key == curses.KEY_HOME:
            cursor = 0
            scroll = 0
        elif key == curses.KEY_END:
            cursor = len(sessions) - 1
            scroll = max(0, cursor - visible + 1)
        elif key in (curses.KEY_ENTER, ord("\n"), ord("\r")):
            if sessions:
                open_session = draw_detail(stdscr, sessions[cursor])
                if open_session:
                    curses.endwin()
                    s = sessions[cursor]
                    cwd = s.get("cwd") or str(Path.home())
                    if Path(cwd).exists():
                        os.chdir(cwd)
                    os.execvp("claude", ["claude", "--resume", s["session_id"]])
        elif key in (ord("d"), ord("D")):
            if sessions:
                h, w = stdscr.getmaxyx()
                if confirm_delete(stdscr, sessions[cursor], w, h):
                    target = sessions[cursor]["path"]
                    try:
                        target.unlink()
                    except OSError:
                        pass
                    all_sessions[:] = [s for s in all_sessions if s["path"] != target]
                    sessions = rebuild()
                    if cursor >= len(sessions):
                        cursor = max(0, len(sessions) - 1)
                    if scroll > cursor:
                        scroll = cursor
        elif key == curses.KEY_RESIZE:
            pass
        elif ord("1") <= key <= ord("5"):
            col = key - ord("1")
            if col == sort_col:
                sort_asc = not sort_asc
            else:
                sort_col = col
                sort_asc = col != 0
            sessions = rebuild()
            cursor = scroll = 0
        esc_pending = False


def cmd_list(sessions) -> None:
    out = [
        {
            "session_id": s["session_id"],
            "project": s["project"],
            "model": s["model"],
            "last_ts": fmt_ts(s["last_ts"]),
            "input_tokens": s["input_tokens"],
            "output_tokens": s["output_tokens"],
            "total_tokens": s["total_tokens"],
        }
        for s in sessions
    ]
    print(json.dumps(out, indent=2))


def cmd_show(sessions, session_id) -> None:
    match = next((s for s in sessions if s["session_id"] == session_id), None)
    if match is None:
        print(json.dumps({"error": f"session not found: {session_id}"}), file=sys.stderr)
        sys.exit(1)
    out = {
        "session_id": match["session_id"],
        "project": match["project"],
        "model": match["model"],
        "last_ts": fmt_ts(match["last_ts"]),
        "first_ts": fmt_ts(match["first_ts"]),
        "input_tokens": match["input_tokens"],
        "output_tokens": match["output_tokens"],
        "cache_creation_tokens": match["cache_creation_tokens"],
        "cache_read_tokens": match["cache_read_tokens"],
        "total_tokens": match["total_tokens"],
        "message_count": match["message_count"],
        "git_branch": match["git_branch"],
        "cwd": match["cwd"],
        "tools_used": match["tools_used"],
        "modified_files": match["modified_files"],
    }
    print(json.dumps(out, indent=2))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="claude-sessions",
        description="Browse Claude Code sessions (TUI) or query them (CLI).",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List sessions as JSON")

    p_show = sub.add_parser("show", help="Show token details for a session")
    p_show.add_argument("session_id", help="Session ID (from 'list')")

    args = parser.parse_args()

    if args.command is None:
        # TUI mode
        sys.stdout.write("Scanning sessions...")
        sys.stdout.flush()
        sessions = collect_sessions(limit=50)
        sys.stdout.write(f" found {len(sessions)} sessions.\n")
        sys.stdout.flush()
        if not sessions:
            print("No sessions found.")
            return
        curses.wrapper(tui, sessions)
        return

    sessions = collect_sessions(limit=500)

    if args.command == "list":
        cmd_list(sessions)
    elif args.command == "show":
        cmd_show(sessions, args.session_id)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        curses.endwin()
        print("\nBye.")
        sys.exit(0)
