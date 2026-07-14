# Grabbertoullie for VS Code

Search multiple book sources for a direct download link — Anna's Archive,
Z-Library, Open Library, Project Gutenberg, Standard Ebooks, Semantic Scholar —
without leaving the editor.

This extension is a thin front-end over the [`grabbertoullie`](../grabbertoullie)
Python CLI: it runs the search on your machine and shows the results in a
Quick Pick.

## Requirements

The `grabbertoullie` CLI must be installed:

```bash
pip install grabbertoullie
playwright install chromium
```

If it isn't on your PATH (e.g. it lives in a virtualenv), set
**`grabbertoullie.cliPath`** to the executable, for example
`C:\path\to\.venv\Scripts\grabbertoullie.exe`.

## Usage

1. Run **Grabbertoullie: Search for a Book** from the Command Palette
   (`Ctrl+Shift+P`).
2. Type a title (optionally with an author or a `pdf`/`epub` suffix).
3. Pick a result, then **Open in browser** or **Copy link**.

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `grabbertoullie.cliPath` | `grabbertoullie` | Path to the CLI executable. |
| `grabbertoullie.groqApiKey` | `""` | Optional Groq key for smarter query parsing. Blank uses the built-in parser. |

## Development

```bash
npm install
npm run compile      # or: npm run watch
```

Press **F5** in VS Code to launch an Extension Development Host with the
extension loaded.
