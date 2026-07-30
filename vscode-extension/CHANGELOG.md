# Changelog

## 0.1.1

- The Chromium browser Playwright needs is now installed automatically the
  first time it's required, so there's no manual `playwright install chromium`
  step. The first search may take a little longer while it downloads (~150 MB,
  one time).
- Increased the search timeout to accommodate that one-time download.
- Docs: install the CLI with `pipx` (or `pip`) straight from the repo instead
  of cloning and doing an editable install; removed contributor-only build
  steps from the extension README.

## 0.1.0

- Initial release.
- Search Anna's Archive, Z-Library, Open Library, Project Gutenberg, Standard
  Ebooks, and Semantic Scholar from a panel inside VS Code.
- Open or copy a direct link for any result.
- Anna's Archive results resolve their real file link on demand (clearing the
  site's browser-verification challenge) instead of only linking to the
  book's info page.
