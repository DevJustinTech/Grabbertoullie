// Thin wrapper around the `grabbertoullie` Python CLI. Intentionally free of
// any `vscode` import so it can be unit-tested / run under plain Node.
import { execFile } from "child_process";

export interface Candidate {
  source: string;
  title: string;
  author: string;
  year: string;
  pdf_url: string;
  epub_url: string;
  weight?: number;
  _score?: number;
}

export interface SearchOptions {
  cliPath: string;
  groqApiKey?: string;
  format?: "pdf" | "epub" | "any";
  author?: string;
  cwd?: string;
  timeoutMs?: number;
}

/** The direct download / detail link for a candidate. */
export function downloadUrl(c: Candidate): string {
  return c.epub_url || c.pdf_url || "";
}

/** The file format a candidate resolves to. */
export function fileFormat(c: Candidate): string {
  return c.epub_url ? "epub" : c.pdf_url ? "pdf" : "?";
}

export class CliNotFoundError extends Error {}

/**
 * Run `grabbertoullie <query> --all --json` and return the ranked candidates
 * (best first). Throws CliNotFoundError if the CLI cannot be located.
 */
export function runSearch(query: string, opts: SearchOptions): Promise<Candidate[]> {
  const args = [query, "--all", "--json"];
  if (opts.format && opts.format !== "any") {
    args.push("--format", opts.format);
  }
  if (opts.author) {
    args.push("--author", opts.author);
  }

  const env = { ...process.env };
  if (opts.groqApiKey) {
    env.GROQ_API_KEY = opts.groqApiKey;
  }

  return new Promise((resolve, reject) => {
    execFile(
      opts.cliPath,
      args,
      {
        env,
        cwd: opts.cwd,
        timeout: opts.timeoutMs ?? 120_000,
        maxBuffer: 10 * 1024 * 1024,
        windowsHide: true,
      },
      (error, stdout, stderr) => {
        // The CLI exits 1 when there are no results but still prints valid
        // JSON (an empty array) to stdout, so parse stdout first regardless
        // of exit code, and only treat unparseable output as a failure.
        const text = (stdout || "").trim();
        if (text) {
          try {
            const parsed = JSON.parse(text);
            if (Array.isArray(parsed)) {
              return resolve(parsed as Candidate[]);
            }
          } catch {
            // fall through to error handling below
          }
        }

        if (error && (error as NodeJS.ErrnoException).code === "ENOENT") {
          return reject(
            new CliNotFoundError(
              `Could not find the grabbertoullie CLI at "${opts.cliPath}". ` +
                `Install it with "pip install grabbertoullie" or set ` +
                `"grabbertoullie.cliPath" to the executable.`
            )
          );
        }

        return reject(
          new Error(
            `grabbertoullie failed: ${(stderr || "").trim() || error?.message || "unknown error"}`
          )
        );
      }
    );
  });
}
