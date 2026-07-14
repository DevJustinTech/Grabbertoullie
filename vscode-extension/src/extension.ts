import * as vscode from "vscode";
import {
  runSearch,
  downloadUrl,
  fileFormat,
  CliNotFoundError,
  Candidate,
} from "./grabbertoullie";

export function activate(context: vscode.ExtensionContext) {
  const disposable = vscode.commands.registerCommand(
    "grabbertoullie.search",
    () => searchCommand()
  );
  context.subscriptions.push(disposable);
}

async function searchCommand(): Promise<void> {
  const query = await vscode.window.showInputBox({
    prompt: "Search for a book",
    placeHolder: "e.g. somadina · the great gatsby epub · atomic habits",
    ignoreFocusOut: true,
  });
  if (!query || !query.trim()) {
    return;
  }

  const config = vscode.workspace.getConfiguration("grabbertoullie");
  const cliPath = config.get<string>("cliPath", "grabbertoullie");
  const groqApiKey = config.get<string>("groqApiKey", "") || undefined;
  const cwd = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

  let results: Candidate[];
  try {
    results = await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: `Searching for "${query.trim()}"…`,
        cancellable: false,
      },
      () => runSearch(query.trim(), { cliPath, groqApiKey, cwd })
    );
  } catch (err) {
    await reportError(err);
    return;
  }

  if (!results.length) {
    vscode.window.showInformationMessage(
      `No results found for "${query.trim()}".`
    );
    return;
  }

  const items: (vscode.QuickPickItem & { candidate: Candidate })[] = results.map(
    (c) => ({
      label: c.title || "(untitled)",
      description: [c.author, c.year].filter(Boolean).join(" · "),
      detail: `${c.source} · ${fileFormat(c)} · ${downloadUrl(c)}`,
      candidate: c,
    })
  );

  const picked = await vscode.window.showQuickPick(items, {
    title: `Results for "${query.trim()}"`,
    placeHolder: "Select a book",
    matchOnDescription: true,
    matchOnDetail: true,
  });
  if (!picked) {
    return;
  }

  await actOnResult(picked.candidate);
}

async function actOnResult(candidate: Candidate): Promise<void> {
  const url = downloadUrl(candidate);
  if (!url) {
    vscode.window.showWarningMessage("This result has no download link.");
    return;
  }

  const OPEN = "$(link-external) Open in browser";
  const COPY = "$(clippy) Copy link";
  const action = await vscode.window.showQuickPick([OPEN, COPY], {
    title: candidate.title || "Book",
    placeHolder: url,
  });

  if (action === OPEN) {
    await vscode.env.openExternal(vscode.Uri.parse(url));
  } else if (action === COPY) {
    await vscode.env.clipboard.writeText(url);
    vscode.window.showInformationMessage("Download link copied to clipboard.");
  }
}

async function reportError(err: unknown): Promise<void> {
  if (err instanceof CliNotFoundError) {
    const OPEN_SETTINGS = "Open Settings";
    const choice = await vscode.window.showErrorMessage(
      err.message,
      OPEN_SETTINGS
    );
    if (choice === OPEN_SETTINGS) {
      vscode.commands.executeCommand(
        "workbench.action.openSettings",
        "grabbertoullie.cliPath"
      );
    }
    return;
  }
  const message = err instanceof Error ? err.message : String(err);
  vscode.window.showErrorMessage(message);
}

export function deactivate() {
  // no-op
}
