# Grabbertoullie for VS Code

![Version](https://img.shields.io/badge/version-0.1.1-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![VS Code](https://img.shields.io/badge/VS%20Code-%5E1.85.0-007ACC)

Search multiple book sources for a direct download link — Anna's Archive,
Z-Library, Open Library, Project Gutenberg, Standard Ebooks, Semantic Scholar —
without leaving the editor.

This extension is a thin front-end over the `grabbertoullie` Python CLI: it
runs the search on your machine and shows the results in a panel inside VS
Code.

## Features

- Searches six sources in parallel and ranks the results.
- One panel, no leaving the editor — type a title, get direct links.
- **Open ↗** and **Copy link** on every result.
- Anna's Archive links resolve to the real file on demand, not just the
  book's info page.

## Requirements

The `grabbertoullie` CLI must be installed and on your PATH. It isn't published
to PyPI yet, so install it straight from the repo with [pipx][pipx] — that puts
the `grabbertoullie` command on your PATH in its own isolated environment, no
clone or virtualenv to manage:

```bash
pipx install git+https://github.com/DevJustinTech/Grabbertoullie.git
```

<sub>(Prefer plain pip? `pip install git+https://github.com/DevJustinTech/Grabbertoullie.git` works too.)</sub>

The Chromium browser that the Anna's Archive resolver drives is downloaded
**automatically the first time it's needed** (a one-time ~150 MB download), so
you don't have to run `playwright install` yourself — the first search just
takes a little longer.

If the CLI isn't on your PATH (for example, you installed it into a specific
virtualenv), point **`grabbertoullie.cliPath`** at the executable instead, for
example `C:\path\to\.venv\Scripts\grabbertoullie.exe`.

[pipx]: https://pipx.pypa.io/

## Usage

1. Run **Grabbertoullie: Search for a Book** from the Command Palette
   (`Ctrl+Shift+P`). This opens a Grabbertoullie panel.
2. Type a title (optionally with an author or a `pdf`/`epub` suffix) and
   press Enter or **Search**.
3. Each result shows its source and format, with **Open ↗** and
   **Copy link** buttons.

Anna's Archive results are a special case: getting the actual file link
requires clearing a browser-verification challenge, which is too slow to do
for every search result up front. So clicking **Open**/**Copy link** on an
Anna's Archive result resolves the real file URL on demand — this can take up
to ~2 minutes and may briefly show a browser window. If resolution fails, it
falls back to opening Anna's Archive's mirror page instead.

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `grabbertoullie.cliPath` | `grabbertoullie` | Path to the CLI executable. |
| `grabbertoullie.groqApiKey` | `""` | Optional Groq key for smarter query parsing. Blank uses the built-in parser. |
