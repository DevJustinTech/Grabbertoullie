import * as vscode from "vscode";
import { SearchPanel } from "./panel";

export function activate(context: vscode.ExtensionContext) {
  const disposable = vscode.commands.registerCommand("grabbertoullie.search", () =>
    SearchPanel.show()
  );
  context.subscriptions.push(disposable);
}

export function deactivate() {
  // no-op
}
