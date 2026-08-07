"use client";

import { useState, useRef, useEffect } from "react";
import {
  postQuery,
  classifyAnswer,
  parseStudentRecord,
  type QueryResponse,
  type QueryType,
  type AnswerKind,
} from "@/lib/api";

// ─── Types ─────────────────────────────────────────────────────

interface HistoryEntry {
  id: number;
  query: string;
  tenant: string;
  type: QueryType;
  hasFallback: boolean;
  ts: Date;
  response: QueryResponse;
}

// ─── Badge for query route type ─────────────────────────────────

function TypeBadge({ type }: { type: QueryType }) {
  const map: Record<QueryType, string> = {
    FACT: "badge-fact",
    LOCAL: "badge-local",
    GLOBAL: "badge-global",
    TABULAR: "badge-tabular",
  };
  return <span className={`badge ${map[type]}`}>{type}</span>;
}

// ─── Fallback warning banner ────────────────────────────────────

function FallbackBanner({ reason }: { reason: string }) {
  return (
    <div className="fallback-banner">
      <span>⚠</span>
      <span>
        Router fell back to FACT —{" "}
        <span className="fallback-code">{reason}</span>. Classification may be wrong.
      </span>
    </div>
  );
}

// ─── Student record renderer ────────────────────────────────────

function StudentCard({ raw }: { raw: string }) {
  const rec = parseStudentRecord(raw);
  const resultClass = rec.result === "PASS" ? "badge-pass" : rec.result === "FAIL" ? "badge-fail" : "badge-warn";
  return (
    <div className="student-card">
      <div className="student-card-header">
        <div>
          <div className="student-name">{rec.name || "Student"}</div>
          <div className="student-roll font-data">Roll: {rec.rollNo}</div>
        </div>
        <span className={`badge ${resultClass}`}>{rec.result}</span>
        {rec.sgpa !== "N/A" && (
          <span className="badge badge-info">SGPA {rec.sgpa}</span>
        )}
        {rec.isSupply && <span className="badge badge-warn">Supplementary</span>}
        {rec.seatCancelled && <span className="badge badge-fail">Seat Cancelled</span>}
      </div>

      {rec.subjects.length > 0 && (
        <div className="card-body" style={{ padding: 0 }}>
          <table className="grade-table">
            <thead>
              <tr>
                <th>Subject</th>
                <th>Grade</th>
                <th>Points</th>
              </tr>
            </thead>
            <tbody>
              {rec.subjects.map(s => {
                const failGrade = s.grade === "FF" || s.grade.startsWith("F") || s.grade === "AB";
                return (
                  <tr key={s.code}>
                    <td className="font-data">{s.code}</td>
                    <td>
                      <span className={`badge ${failGrade ? "badge-fail" : "badge-pass"}`}>
                        {s.grade}
                      </span>
                    </td>
                    <td className="font-data">{s.point}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {rec.totalMarks && (
        <div style={{ padding: "10px 12px", borderTop: "1px solid var(--color-border)", fontSize: "var(--text-xs)", color: "var(--color-muted)", fontFamily: "var(--font-mono)" }}>
          Total Marks: {rec.totalMarks}
        </div>
      )}
    </div>
  );
}

// ─── Disambiguation renderer ─────────────────────────────────────

function DisambiguationOptions({
  kind,
  onSelect,
}: {
  kind: Extract<AnswerKind, { kind: "disambiguation" }>;
  onSelect: (roll: string) => void;
}) {
  return (
    <div>
      <p style={{ fontSize: "var(--text-sm)", color: "var(--color-muted)", marginBottom: 12 }}>
        Multiple students match <span className="font-data" style={{ color: "var(--color-text)" }}>{kind.extracted}</span>. Select one:
      </p>
      <div className="disambiguation-grid">
        {kind.options.map(opt => (
          <button key={opt.roll} className="disambiguation-option" onClick={() => onSelect(opt.roll)}>
            <div>
              <div className="disambiguation-name">{opt.name}</div>
              <div className="disambiguation-meta">Roll: {opt.roll}</div>
            </div>
            <div className="match-score">
              {opt.score.toFixed(1)}% match
            </div>
          </button>
        ))}
      </div>
      <p style={{ fontSize: "var(--text-xs)", color: "var(--color-muted)", marginTop: 10 }}>
        Click a name to fetch the full record.
      </p>
    </div>
  );
}

// ─── Context panel ───────────────────────────────────────────────

function ContextPanel({ context }: { context: string }) {
  if (!context || context.trim() === "") return null;
  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Context Used</span>
        <span style={{ fontSize: "var(--text-xs)", color: "var(--color-muted)", fontFamily: "var(--font-mono)" }}>
          {context.length} chars
        </span>
      </div>
      <div className="card-body">
        <pre style={{
          margin: 0,
          fontSize: "var(--text-xs)",
          color: "var(--color-muted)",
          fontFamily: "var(--font-mono)",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          lineHeight: 1.5,
          maxHeight: 380,
          overflowY: "auto",
        }}>
          {context}
        </pre>
      </div>
    </div>
  );
}

// ─── History sidebar item ────────────────────────────────────────

function HistoryList({
  history,
  onSelect,
}: {
  history: HistoryEntry[];
  onSelect: (e: HistoryEntry) => void;
}) {
  if (!history.length)
    return (
      <div className="empty-state" style={{ padding: "24px 12px" }}>
        <div className="empty-state-sub">No queries yet</div>
      </div>
    );
  return (
    <div>
      {history.map(e => (
        <div key={e.id} className="history-item" onClick={() => onSelect(e)}>
          <TypeBadge type={e.type} />
          <span className="history-query" title={e.query}>{e.query}</span>
          <span className="history-time">
            {e.ts.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── Main page ───────────────────────────────────────────────────

const TENANTS = ["tenant_1"];  // registered tenants from allowlist

export default function QueryConsolePage() {
  const [query, setQuery] = useState("");
  const [tenant, setTenant] = useState("tenant_1");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const idRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  const submit = async (q: string = query) => {
    if (!q.trim() || loading) return;
    abortRef.current?.abort();
    abortRef.current = new AbortController();
    setLoading(true);
    setError(null);
    setResponse(null);
    try {
      const res = await postQuery(q.trim(), tenant, abortRef.current.signal);
      setResponse(res);
      setHistory(prev => [
        {
          id: idRef.current++,
          query: q.trim(),
          tenant,
          type: res.query_type,
          hasFallback: !!res.metadata.fallback_reason,
          ts: new Date(),
          response: res,
        },
        ...prev.slice(0, 49),
      ]);
    } catch (e: unknown) {
      if ((e as Error).name === "AbortError") return;
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  // When user clicks a disambiguation option, re-query with just the roll number
  const handleDisambiguationSelect = (roll: string) => {
    setQuery(roll);
    submit(roll);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
  };

  const classified = response ? classifyAnswer(response.answer) : null;

  return (
    <div style={{ display: "flex", height: "calc(100vh - var(--strip-h))", overflow: "hidden" }}>
      {/* ─ Left: Query history ─────────────────────────────────── */}
      <div style={{
        width: 280, flexShrink: 0,
        borderRight: "1px solid var(--color-border)",
        background: "var(--color-shell)",
        display: "flex", flexDirection: "column", overflow: "hidden",
      }}>
        <div className="card-header">
          <span className="card-title">Query History</span>
          {history.length > 0 && (
            <button
              onClick={() => setHistory([])}
              style={{ fontSize: "var(--text-xs)", color: "var(--color-muted)", background: "none", border: "none", cursor: "pointer" }}
            >
              Clear
            </button>
          )}
        </div>
        <div style={{ overflowY: "auto", flex: 1 }}>
          <HistoryList
            history={history}
            onSelect={e => { setQuery(e.query); setResponse(e.response); }}
          />
        </div>
      </div>

      {/* ─ Centre: Main query area ─────────────────────────────── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <div className="page-header">
          <h1 className="page-title">Query Console</h1>
          <p className="page-subtitle">Query the Company Brain retrieval engine — fact lookup, multi-hop, tabular, or decision-assisting</p>
        </div>

        <div className="page-body" style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Input row */}
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <select
              className="tenant-select"
              value={tenant}
              onChange={e => setTenant(e.target.value)}
            >
              {TENANTS.map(t => <option key={t} value={t}>{t}</option>)}
            </select>

            <div className="query-input-wrap" style={{ flex: 1 }}>
              <input
                className="query-input"
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder='e.g. "search for gaikwad rohan vijay" or "average SGPA" or "what is RAG-MicroSim?"'
                autoFocus
              />
              <button
                className="query-submit"
                onClick={() => submit()}
                disabled={loading || !query.trim()}
                title="Submit (Enter)"
              >
                {loading
                  ? <span className="spinner" style={{ width: 14, height: 14 }} />
                  : <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                }
              </button>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div style={{
              background: "var(--color-fail-bg)", border: "1px solid rgba(229,72,77,0.25)",
              borderRadius: 6, padding: "10px 14px",
              fontSize: "var(--text-sm)", color: "var(--color-fail)",
              fontFamily: "var(--font-mono)",
            }}>
              {error}
            </div>
          )}

          {/* Result */}
          {response && classified && (
            <div className="result-wrap">
              {/* Main answer */}
              <div className="result-main">
                {/* Fallback warning */}
                {response.metadata.fallback_reason && (
                  <FallbackBanner reason={response.metadata.fallback_reason} />
                )}

                {/* Type + metadata row */}
                <div className="result-header">
                  <TypeBadge type={response.query_type} />
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-muted)", fontFamily: "var(--font-mono)" }}>
                    tenant: {tenant}
                  </span>
                </div>

                {/* Render by answer kind */}
                {classified.kind === "student_record" && (
                  <StudentCard raw={classified.raw} />
                )}

                {classified.kind === "disambiguation" && (
                  <DisambiguationOptions
                    kind={classified}
                    onSelect={handleDisambiguationSelect}
                  />
                )}

                {classified.kind === "error" && (
                  <div style={{
                    background: "var(--color-warn-bg)", border: "1px solid rgba(229,165,0,0.25)",
                    borderRadius: 6, padding: "12px 16px",
                    fontSize: "var(--text-sm)", color: "var(--color-warn)",
                  }}>
                    {classified.raw}
                  </div>
                )}

                {classified.kind === "text" && (
                  <div className="result-answer">{classified.raw}</div>
                )}
              </div>

              {/* Context panel */}
              <div className="result-context">
                <ContextPanel context={response.context_used} />
              </div>
            </div>
          )}

          {/* Empty state */}
          {!response && !loading && !error && (
            <div className="empty-state" style={{ marginTop: 40 }}>
              <div style={{ fontSize: 28, opacity: 0.3 }}>⌕</div>
              <div className="empty-state-title">Ready to query</div>
              <div className="empty-state-sub">
                Queries route to FACT / LOCAL / GLOBAL / TABULAR automatically.
              </div>
              <div className="empty-state-sub" style={{ marginTop: 8, fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" }}>
                Try: &quot;search for gaikwad rohan vijay&quot; · &quot;average SGPA&quot; · &quot;what is RAG-MicroSim?&quot;
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
