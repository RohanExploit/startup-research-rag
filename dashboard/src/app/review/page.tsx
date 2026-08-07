"use client";
import { useEffect, useState } from "react";

const API = "http://localhost:8000";

interface ReviewItem {
  roll_no: string;
  issue_type: string;
  details: string;
  source_doc: string;
  created_at: string;
}

export default function ReviewPage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/review`)
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
              <span className="badge badge-fail">{items.length} items</span>
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {["Roll No", "Issue", "Details", "Source", "Flagged At"].map(h => (
                    <th key={h} style={{ textAlign: "left", padding: "8px 16px", fontSize: "var(--text-xs)", color: "var(--color-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", borderBottom: "1px solid var(--color-border)" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((item, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid rgba(46,58,80,0.4)" }}>
                    <td style={{ padding: "10px 16px" }}><span className="font-data" style={{ color: "var(--color-accent)" }}>{item.roll_no}</span></td>
                    <td style={{ padding: "10px 16px" }}><span className="badge badge-warn">{item.issue_type}</span></td>
                    <td style={{ padding: "10px 16px", fontSize: "var(--text-sm)", color: "var(--color-muted)", maxWidth: 300 }}>{item.details}</td>
                    <td style={{ padding: "10px 16px" }}><span className="font-data" style={{ fontSize: "var(--text-xs)", color: "var(--color-muted)" }}>{item.source_doc}</span></td>
                    <td style={{ padding: "10px 16px" }}><span className="font-data" style={{ fontSize: "var(--text-xs)", color: "var(--color-muted)" }}>{item.created_at}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
