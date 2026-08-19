import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import type { Diff } from "../types";
import { errorMessage } from "../errors";

export default function DiffPage() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const pid = Number(id);
  const path = params.get("path") || "";
  const from = params.get("from") ? Number(params.get("from")) : undefined;
  const to = params.get("to") ? Number(params.get("to")) : undefined;

  const [diff, setDiff] = useState<Diff | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!path) return;
    setDiff(null);
    api
      .getDiff(pid, path, { from, to })
      .then(setDiff)
      .catch((err) => setError(errorMessage(err, "Failed")));
  }, [pid, path, from, to]);

  return (
    <div>
      <div className="row" style={{ marginBottom: 6 }}>
        <Link to={`/projects/${pid}`} className="muted" style={{ fontSize: 13 }}>
          ← project
        </Link>
      </div>
      <h1 style={{ fontFamily: "monospace", fontSize: 18, wordBreak: "break-all" }}>
        {path || "diff"}
      </h1>
      <p className="muted" style={{ marginTop: 0 }}>
        {from ? `commit #${from}` : "root"} → {to ? `commit #${to}` : "HEAD"}
        {diff?.format && (
          <>
            {" "}· <span className="badge badge-daw" style={{ background: "#888" }}>{diff.format.toUpperCase()}</span>
          </>
        )}
        {diff?.binary && <span className="chip">binary</span>}
      </p>

      {error && <div className="error">{error}</div>}
      {!diff && !error && <p className="muted">Loading diff…</p>}

      {diff && (
        <>
          <div className="diff-summary">
            {diff.summary.length === 0 && (
              <div className="muted">No structural changes detected.</div>
            )}
            {diff.summary.map((c, i) => (
              <div className={`diff-change kind-${c.kind}`} key={i}>
                <span className="chip">{c.label}</span>
                {c.old !== null && <span className="chip removed">{c.old}</span>}
                {c.old !== null && c.new !== null && <span className="muted">→</span>}
                {c.new !== null && <span className="chip added">{c.new}</span>}
              </div>
            ))}
          </div>

          {diff.raw ? (
            <pre className="diff-raw">
              <code>
                {diff.raw.split("\n").map((line, i) => (
                  <span
                    key={i}
                    className={
                      line.startsWith("+") && !line.startsWith("+++")
                        ? "diff-line add"
                        : line.startsWith("-") && !line.startsWith("---")
                          ? "diff-line del"
                          : line.startsWith("@@")
                            ? "diff-line hunk"
                            : "diff-line"
                    }
                  >
                    {line || " "}
                  </span>
                ))}
              </code>
            </pre>
          ) : (
            <p className="muted">Identical content.</p>
          )}
          {diff.truncated && (
            <p className="muted" style={{ fontSize: 12 }}>
              Raw diff truncated for readability.
            </p>
          )}
        </>
      )}
    </div>
  );
}
