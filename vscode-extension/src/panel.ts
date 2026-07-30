import * as vscode from "vscode";
import {
  runSearch,
  downloadUrl,
  fileFormat,
  extractAnnasMd5,
  resolveAnnasDownload,
  CliNotFoundError,
  Candidate,
} from "./grabbertoullie";

type ToWebviewMessage =
  | { type: "searching"; query: string }
  | { type: "results"; query: string; results: (Candidate & { _downloadUrl: string; _format: string })[] }
  | { type: "error"; message: string; cliNotFound: boolean }
  | { type: "resolving"; title: string }
  | { type: "resolved" }
  | { type: "copied" };

type FromWebviewMessage =
  | { type: "search"; query: string }
  | { type: "openUrl"; url: string; source: string; title: string }
  | { type: "copyUrl"; url: string; source: string; title: string }
  | { type: "openSettings" };

export class SearchPanel {
  private static current: SearchPanel | undefined;

  private readonly panel: vscode.WebviewPanel;
  private readonly disposables: vscode.Disposable[] = [];

  public static show(): void {
    const column = vscode.window.activeTextEditor?.viewColumn;
    if (SearchPanel.current) {
      SearchPanel.current.panel.reveal(column);
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      "grabbertoullieSearch",
      "Grabbertoullie",
      column ?? vscode.ViewColumn.Active,
      { enableScripts: true, retainContextWhenHidden: true }
    );
    SearchPanel.current = new SearchPanel(panel);
  }

  private constructor(panel: vscode.WebviewPanel) {
    this.panel = panel;
    this.panel.webview.html = renderHtml(panel.webview);

    this.panel.onDidDispose(() => this.dispose(), null, this.disposables);
    this.panel.webview.onDidReceiveMessage(
      (message: FromWebviewMessage) => this.handleMessage(message),
      null,
      this.disposables
    );
  }

  private async handleMessage(message: FromWebviewMessage): Promise<void> {
    switch (message.type) {
      case "search":
        await this.runSearch(message.query);
        break;
      case "openUrl": {
        const url = await this.resolveForAction(message);
        await vscode.env.openExternal(vscode.Uri.parse(url));
        break;
      }
      case "copyUrl": {
        const url = await this.resolveForAction(message);
        await vscode.env.clipboard.writeText(url);
        this.post({ type: "copied" });
        break;
      }
      case "openSettings":
        await vscode.commands.executeCommand(
          "workbench.action.openSettings",
          "grabbertoullie.cliPath"
        );
        break;
    }
  }

  /**
   * Anna's Archive search results only ever carry a mirror-page link (getting
   * the real file link requires driving a slow-download challenge that's too
   * slow to do for every result up front). So on the specific result the user
   * acts on, try to resolve the actual file URL first and fall back to the
   * mirror link if that doesn't pan out.
   */
  private async resolveForAction(message: { url: string; source: string; title: string }): Promise<string> {
    if (message.source !== "Anna's Archive") {
      return message.url;
    }
    const md5 = extractAnnasMd5(message.url);
    if (!md5) {
      return message.url;
    }

    const { cliPath, cwd } = this.getCliConfig();
    this.post({ type: "resolving", title: message.title });
    try {
      const resolved = await resolveAnnasDownload(md5, { cliPath, cwd });
      return resolved || message.url;
    } catch (err) {
      if (err instanceof CliNotFoundError) {
        await reportCliNotFound(err);
      }
      return message.url;
    } finally {
      this.post({ type: "resolved" });
    }
  }

  private getCliConfig(): { cliPath: string; groqApiKey?: string; cwd?: string } {
    const config = vscode.workspace.getConfiguration("grabbertoullie");
    return {
      cliPath: config.get<string>("cliPath", "grabbertoullie"),
      groqApiKey: config.get<string>("groqApiKey", "") || undefined,
      cwd: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath,
    };
  }

  private async runSearch(rawQuery: string): Promise<void> {
    const query = rawQuery.trim();
    if (!query) {
      return;
    }

    const { cliPath, groqApiKey, cwd } = this.getCliConfig();

    this.post({ type: "searching", query });
    try {
      const results = await runSearch(query, { cliPath, groqApiKey, cwd });
      this.post({
        type: "results",
        query,
        results: results.map((c) => ({
          ...c,
          _downloadUrl: downloadUrl(c),
          _format: fileFormat(c),
        })),
      });
    } catch (err) {
      const cliNotFound = err instanceof CliNotFoundError;
      const message = err instanceof Error ? err.message : String(err);
      this.post({ type: "error", message, cliNotFound });
    }
  }

  private post(message: ToWebviewMessage): void {
    this.panel.webview.postMessage(message);
  }

  private dispose(): void {
    SearchPanel.current = undefined;
    this.panel.dispose();
    while (this.disposables.length) {
      this.disposables.pop()?.dispose();
    }
  }
}

async function reportCliNotFound(err: CliNotFoundError): Promise<void> {
  const OPEN_SETTINGS = "Open Settings";
  const choice = await vscode.window.showErrorMessage(err.message, OPEN_SETTINGS);
  if (choice === OPEN_SETTINGS) {
    await vscode.commands.executeCommand(
      "workbench.action.openSettings",
      "grabbertoullie.cliPath"
    );
  }
}

function getNonce(): string {
  const chars =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let text = "";
  for (let i = 0; i < 32; i++) {
    text += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return text;
}

function renderHtml(webview: vscode.Webview): string {
  const nonce = getNonce();
  const csp = [
    "default-src 'none'",
    "style-src 'unsafe-inline'",
    `script-src 'nonce-${nonce}'`,
  ].join("; ");

  return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta http-equiv="Content-Security-Policy" content="${csp}" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Grabbertoullie</title>
<style>
  body {
    font-family: var(--vscode-font-family);
    font-size: var(--vscode-font-size, 13px);
    color: var(--vscode-foreground);
    background: var(--vscode-editor-background);
    padding: 16px 20px 24px;
  }
  h1 {
    font-size: 1.15em;
    font-weight: 600;
    margin: 0 0 12px;
  }
  .search-row {
    display: flex;
    gap: 8px;
    margin-bottom: 10px;
  }
  #query {
    flex: 1;
    padding: 6px 8px;
    background: var(--vscode-input-background);
    color: var(--vscode-input-foreground);
    border: 1px solid var(--vscode-input-border, transparent);
    border-radius: 2px;
    font-size: inherit;
    font-family: inherit;
  }
  #query:focus {
    outline: 1px solid var(--vscode-focusBorder);
    outline-offset: -1px;
  }
  button {
    padding: 6px 14px;
    background: var(--vscode-button-background);
    color: var(--vscode-button-foreground);
    border: none;
    border-radius: 2px;
    cursor: pointer;
    font-size: inherit;
    font-family: inherit;
  }
  button:hover:not(:disabled) {
    background: var(--vscode-button-hoverBackground);
  }
  button:disabled {
    opacity: 0.6;
    cursor: default;
  }
  button.secondary {
    background: transparent;
    color: var(--vscode-foreground);
    border: 1px solid var(--vscode-panel-border, #8888);
    padding: 4px 10px;
    white-space: nowrap;
  }
  button.secondary:hover:not(:disabled) {
    background: var(--vscode-list-hoverBackground);
  }
  #status {
    color: var(--vscode-descriptionForeground);
    margin: 4px 0 14px;
    min-height: 1.2em;
  }
  #status.error {
    color: var(--vscode-errorForeground);
  }
  .error-box {
    border: 1px solid var(--vscode-inputValidation-errorBorder, var(--vscode-errorForeground));
    background: var(--vscode-inputValidation-errorBackground, transparent);
    padding: 10px 12px;
    border-radius: 3px;
    margin-bottom: 8px;
  }
  .error-box p {
    margin: 0 0 8px;
  }
  .card {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    border: 1px solid var(--vscode-panel-border, transparent);
    border-radius: 4px;
    margin-bottom: 8px;
  }
  .card:hover {
    background: var(--vscode-list-hoverBackground);
  }
  .card-main {
    min-width: 0;
  }
  .title {
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .meta {
    color: var(--vscode-descriptionForeground);
    font-size: 0.9em;
    margin-top: 2px;
  }
  .badges {
    display: flex;
    gap: 6px;
    margin-top: 6px;
  }
  .badge {
    background: var(--vscode-badge-background);
    color: var(--vscode-badge-foreground);
    border-radius: 10px;
    padding: 1px 8px;
    font-size: 0.75em;
  }
  .actions {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
  }
</style>
</head>
<body>
  <h1>Grabbertoullie</h1>
  <div class="search-row">
    <input id="query" type="text" placeholder="e.g. somadina &middot; the great gatsby epub &middot; atomic habits" autocomplete="off" />
    <button id="searchBtn">Search</button>
  </div>
  <div id="status">Search for a book by title, author, or ISBN.</div>
  <div id="results"></div>

  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    const input = document.getElementById("query");
    const button = document.getElementById("searchBtn");
    const status = document.getElementById("status");
    const results = document.getElementById("results");

    let savedStatus = null;
    let pendingCopyBtn = null;

    function setBusy(busy) {
      input.disabled = busy;
      button.disabled = busy;
      button.textContent = busy ? "Searching…" : "Search";
    }

    function setActionsBusy(busy) {
      document.querySelectorAll(".actions button").forEach((b) => {
        b.disabled = busy;
      });
    }

    function doSearch() {
      const q = input.value.trim();
      if (!q) {
        return;
      }
      results.innerHTML = "";
      status.className = "";
      setBusy(true);
      vscode.postMessage({ type: "search", query: q });
    }

    button.addEventListener("click", doSearch);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        doSearch();
      }
    });
    input.focus();

    window.addEventListener("message", (event) => {
      const msg = event.data;
      switch (msg.type) {
        case "searching":
          status.className = "";
          status.textContent = 'Searching for "' + msg.query + '"…';
          break;
        case "results":
          setBusy(false);
          renderResults(msg.query, msg.results);
          break;
        case "error":
          setBusy(false);
          renderError(msg.message, msg.cliNotFound);
          break;
        case "resolving":
          savedStatus = { text: status.textContent, className: status.className };
          status.className = "";
          status.textContent =
            'Resolving the direct download link for "' + msg.title +
            '"… this can take up to ~2 minutes and may briefly show a browser window.';
          setActionsBusy(true);
          break;
        case "resolved":
          setActionsBusy(false);
          if (savedStatus) {
            status.textContent = savedStatus.text;
            status.className = savedStatus.className;
            savedStatus = null;
          }
          break;
        case "copied":
          if (pendingCopyBtn) {
            const btn = pendingCopyBtn;
            const original = btn.dataset.label;
            btn.textContent = "Copied!";
            setTimeout(() => {
              btn.textContent = original;
            }, 1200);
            pendingCopyBtn = null;
          }
          break;
      }
    });

    function renderResults(query, items) {
      results.innerHTML = "";
      status.className = "";
      if (!items.length) {
        status.textContent = 'No results found for "' + query + '".';
        return;
      }
      status.textContent =
        items.length + " result" + (items.length === 1 ? "" : "s") + ' for "' + query + '"';
      for (const c of items) {
        results.appendChild(renderCard(c));
      }
    }

    function renderCard(c) {
      const card = document.createElement("div");
      card.className = "card";

      const main = document.createElement("div");
      main.className = "card-main";

      const title = document.createElement("div");
      title.className = "title";
      title.textContent = c.title || "(untitled)";
      main.appendChild(title);

      const meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = [c.author, c.year].filter(Boolean).join(" · ");
      main.appendChild(meta);

      const badges = document.createElement("div");
      badges.className = "badges";
      badges.appendChild(badge(c.source));
      badges.appendChild(badge(c._format));
      main.appendChild(badges);

      card.appendChild(main);

      const actions = document.createElement("div");
      actions.className = "actions";

      if (c._downloadUrl) {
        const openBtn = document.createElement("button");
        openBtn.className = "secondary";
        openBtn.textContent = "Open ↗";
        openBtn.addEventListener("click", () =>
          vscode.postMessage({
            type: "openUrl",
            url: c._downloadUrl,
            source: c.source,
            title: c.title,
          })
        );
        actions.appendChild(openBtn);

        const copyBtn = document.createElement("button");
        copyBtn.className = "secondary";
        copyBtn.textContent = "Copy link";
        copyBtn.dataset.label = "Copy link";
        copyBtn.addEventListener("click", () => {
          pendingCopyBtn = copyBtn;
          vscode.postMessage({
            type: "copyUrl",
            url: c._downloadUrl,
            source: c.source,
            title: c.title,
          });
        });
        actions.appendChild(copyBtn);
      } else {
        const none = document.createElement("span");
        none.textContent = "No link";
        actions.appendChild(none);
      }

      card.appendChild(actions);
      return card;
    }

    function badge(text) {
      const el = document.createElement("span");
      el.className = "badge";
      el.textContent = text;
      return el;
    }

    function renderError(message, cliNotFound) {
      results.innerHTML = "";
      status.className = "error";
      status.textContent = "Search failed.";

      const box = document.createElement("div");
      box.className = "error-box";

      const p = document.createElement("p");
      p.textContent = message;
      box.appendChild(p);

      if (cliNotFound) {
        const settingsBtn = document.createElement("button");
        settingsBtn.textContent = "Open Settings";
        settingsBtn.addEventListener("click", () =>
          vscode.postMessage({ type: "openSettings" })
        );
        box.appendChild(settingsBtn);
      }

      results.appendChild(box);
    }
  </script>
</body>
</html>`;
}
