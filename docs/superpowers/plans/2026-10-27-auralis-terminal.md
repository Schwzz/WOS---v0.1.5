# Auralis Branding and Terminal Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rename visible WOS branding to Auralis and create a quieter original terminal interface.

**Architecture:** Keep the current session, command bridge, Textual UI, desktop overlay, and storage formats. Replace the terminal's inline command-output panel with a bounded journal in a separate details dialog and short dismissible notices. Keep slash completion, pickers, and shortcuts.

**Tech Stack:** Python 3.11+, Textual 8.2.x, existing HTML/CSS/JavaScript overlay.

**Spec:** User-approved roadmap items 1 and 2 in this conversation.

## Global Constraints

- Preserve existing chats, settings, paths, protocol identifiers, and environment variables.
- Do not add Desktop-mode conversion, STT, vision, tools, or avatar redesign.
- Keep Nexis as the character name; update its shipped project identity to Auralis.
- Keep existing keyboard interactions and draft/history preservation.

## Review Focus

- Short terminal windows must keep the composer visible.
- Long command output must remain bounded and accessible without occupying chat space.
- Details dialogs must preserve drafts and accept cancellation.
- Background replies must preserve transcript widgets and reading position.
- Branding must not rename protocol headers or filter system errors into voice output.

### Task 1: Visible branding

**Files:** start.py, core user-facing strings, overlay UI/window labels, characters/nexis.json, README.md, OVERLAY.md, TERMINAL.md, run.bat, workflow name.

- [x] Replace visible app branding, preserving X-WOS-Token, WOS-Overlay discovery, restart environment variables, Python identifiers, and repository links.
- [x] Update affected expectations in existing tests; verify the suite.

### Task 2: Quiet terminal interface

**Files:** core/terminal_ui.py, core/terminal_ui.tcss, tests/test_terminal_ui.py, tests/terminal_preview.py, TERMINAL.md, docs/terminal-*.

- [x] Add regressions for hidden sidebar, notice-only output, bounded history, F8 details, Escape/draft preservation, and small screens; observe failures.
- [x] Implement Auralis colors/layout, compact status/composer, separate details dialog, bounded output journal, and dismissible notices.
- [x] Preserve existing keyboard/interaction regressions; update visual previews and docs.
- [x] Run complete Python and JS checks, inspect previews, and review changed code.

### Task 3: Repository review and delivery

- [x] Review session persistence, provider/network handling, voice cancellation, desktop lifecycle, and frontend behavior.
- [x] Record remaining reproducible findings with file references; do not implement unrelated roadmap features.
- [x] Publish a focused draft PR from current main; verify CI and report remaining limitations.
