"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface ReviewItem {
  roll_no: string;
  name?: string;
  flags?: string;          // JSON-encoded string[] e.g. '["gap_exceeds_max_possible"]'
  gap?: number;
  derived_max?: number;
  raw_block?: string;
  tenant_id?: string;
}

function parseFlags(flags?: string): string[] {
  if (!flags) return [];
  try {
    const parsed = JSON.parse(flags);
    return Array.isArray(parsed) ? parsed.map(String) : [String(parsed)];
  } catch {
    return [flags];
  }
}

export default function ReviewPage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch(`/review`)
      .then(r => r.json())
      .then(d => { setItems(d.items ?? []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Needs-Review Queue</h1>
        <p className="page-subtitle">Extraction failures · SGPA mismatches · flagged records requiring human verification</p>
      </div>
      <div className="page-body">
        {loading ? (
          <div className="empty-state"><span className="spinner" /><div className="empty-state-title">Loading…</div></div>
        ) : items.length === 0 ? (
          <div className="empty-state">
            <div style={{ fontSize: 24, color: "var(--color-pass)" }}>✓</div>
            <div className="empty-state-title">No records in review queue</div>
            <div className="empty-state-sub">All extractions verified clean</div>
          </div>
        ) : (
          <div className="card">
            <div className="card-header">
              <span className="card-title">Flagged Records</span>
              <span className="badge badge-fail">{items.length} item{items.length !== 1 ? "s" : ""}</span>
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {["Roll No", "Name", "Issue", "Details", "Source"].map(h => (
                    <th key={h} style={{ textAlign: "left", padding: "8px 16px", fontSize: "var(--text-xs)", color: "var(--color-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", borderBottom: "1px solid var(--color-border)" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((item, i) => {
                  const flags = parseFlags(item.flags);
                  const detailBits: string[] = [];
                  if (item.gap != null) detailBits.push(`gap ${item.gap}`);
                  if (item.derived_max != null) detailBits.push(`max ${item.derived_max}`);
                  const details = detailBits.join(" · ") || (item.raw_block?.split("\n")[0] ?? "—");
                  return (
                    <tr key={i} style={{ borderBottom: "1px solid rgba(46,58,80,0.4)" }}>
                      <td style={{ padding: "10px 16px" }}><span className="font-data" style={{ color: "var(--color-accent)" }}>{item.roll_no}</span></td>
                      <td style={{ padding: "10px 16px", fontSize: "var(--text-sm)", color: "var(--color-text)" }}>{item.name ?? "—"}</td>
                      <td style={{ padding: "10px 16px", display: "flex", flexWrap: "wrap", gap: 4 }}>
                        {flags.length ? flags.map((f, j) => (
                          <span key={j} className="badge badge-warn">{f}</span>
                        )) : <span style={{ color: "var(--color-muted)" }}>—</span>}
                      </td>
                      <td style={{ padding: "10px 16px", fontSize: "var(--text-sm)", color: "var(--color-muted)", maxWidth: 320 }}>{details}</td>
                      <td style={{ padding: "10px 16px" }}><span className="font-data" style={{ fontSize: "var(--text-xs)", color: "var(--color-muted)" }}>{item.tenant_id ?? "—"}</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
