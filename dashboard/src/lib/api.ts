/**
 * API client for Company Brain FastAPI backend (127.0.0.1:8000)
 * All types mirror the actual Pydantic response models in api/main.py
 */

const BASE = "http://127.0.0.1:8000";

export type QueryType = "FACT" | "LOCAL" | "GLOBAL" | "TABULAR";

export interface QueryResponse {
  query_type: QueryType;
  answer: string;
  context_used: string;
  metadata: {
    fallback_reason?: string;   // e.g. "ollama_exception:RequestError"
    [key: string]: unknown;
  };
}

export interface OllamaStatus {
  reachable: boolean;
  model: string;
  vram_used_gb: number | null;
  vram_total_gb: number | null;
}

export interface TenantInfo {
  tenant_id: string;
  registered: boolean;
  description: string;
  doc_count: number;
  last_indexed_at: string | null;
  has_pipeline_output: boolean;
}

export interface AdminStatus {
  ollama: OllamaStatus;
  tenants: TenantInfo[];
  registered_tenant_count: number;
  total_docs: number;
  timestamp: string;
}

export async function postQuery(
  query: string,
  tenant_id: string,
  signal?: AbortSignal
): Promise<QueryResponse> {
  const res = await fetch(`${BASE}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, tenant_id }),
    signal,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`API error ${res.status}: ${detail}`);
  }
  return res.json();
}

export async function getAdminStatus(): Promise<AdminStatus> {
  const res = await fetch(`${BASE}/admin/status`, {
    next: { revalidate: 0 },   // no cache — always live
  });
  if (!res.ok) throw new Error(`Status fetch failed: ${res.status}`);
  return res.json();
}

export async function getHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/health`, { signal: AbortSignal.timeout(2000) });
    return res.ok;
  } catch {
    return false;
  }
}

/** Parse the answer field to detect its type and extract structured data */
export type AnswerKind =
  | { kind: "disambiguation"; options: { index: number; name: string; roll: string; score: number }[]; extracted: string }
  | { kind: "student_record"; raw: string }
  | { kind: "text"; raw: string }
  | { kind: "error"; raw: string };

export function classifyAnswer(answer: string): AnswerKind {
  // Disambiguation: "Did you mean one of these? (Extracted: 'name')"
  if (answer.startsWith("Did you mean one of these?")) {
    const extractedMatch = answer.match(/Extracted: '([^']+)'/);
    const extracted = extractedMatch ? extractedMatch[1] : "";
    const lines = answer.split("\n").slice(1);
    const options: { index: number; name: string; roll: string; score: number }[] = [];
    for (const line of lines) {
      // "1. Name Here (Roll: 22051470) - Match Score: 95.0"
      const m = line.match(/^(\d+)\.\s+(.+?)\s+\(Roll:\s+(\S+)\)\s+-\s+Match Score:\s+([\d.]+)/);
      if (m) options.push({ index: parseInt(m[1]), name: m[2], roll: m[3], score: parseFloat(m[4]) });
    }
    return { kind: "disambiguation", options, extracted };
  }

  // Student record: starts with the emoji header from tabular_queries.py L103
  if (answer.startsWith("🎓 **Student Record for")) {
    return { kind: "student_record", raw: answer };
  }

  // Error cases from tabular_queries.py L191, L200
  if (
    answer.startsWith("Could not extract") ||
    answer.startsWith("Student matching") ||
    answer.startsWith("I don't have enough")
  ) {
    return { kind: "error", raw: answer };
  }

  return { kind: "text", raw: answer };
}

/** Parse student record markdown into structured data */
export interface StudentRecord {
  name: string;
  rollNo: string;
  result: "PASS" | "FAIL" | string;
  sgpa: string;
  isSupply: boolean;
  seatCancelled: boolean;
  totalMarks: string | null;
  subjects: { code: string; grade: string; point: string }[];
}

export function parseStudentRecord(raw: string): StudentRecord {
  const lines = raw.split("\n").map(l => l.trim()).filter(Boolean);
  const name = (lines[0].match(/\*\*Student Record for (.+)\*\*/) || [])[1] || "";
  const rollNo = (lines[1]?.match(/`([^`]+)`/) || [])[1] || "";
  const resultLine = lines[2] || "";
  const result = resultLine.includes("PASS") ? "PASS" : resultLine.includes("FAIL") ? "FAIL" : "UNKNOWN";
  const sgpa = (lines[3]?.match(/\*\*([\d.]+|N\/A)\*\*/) || [])[1] || "N/A";
  const isSupply = lines.some(l => l.includes("Supplementary Exam"));
  const seatCancelled = lines.some(l => l.includes("Seat Cancelled"));
  const totalMarksLine = lines.find(l => l.includes("Total Marks:"));
  const totalMarks = totalMarksLine ? (totalMarksLine.match(/:\s*(\d+)/) || [])[1] || null : null;

  const subjects: { code: string; grade: string; point: string }[] = [];
  for (const l of lines) {
    const m = l.match(/•\s+`([^`]+)`.*Grade \*\*([^*]+)\*\*.*Point:\s*([\d.]+)/);
    if (m) subjects.push({ code: m[1], grade: m[2], point: m[3] });
  }

  return { name, rollNo, result, sgpa, isSupply, seatCancelled, totalMarks, subjects };
}
