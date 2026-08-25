import { apiFetch } from "@/lib/api";

/**
 * Same-origin passthrough to the Company Brain API's POST /query.
 *
 * The phone client cannot call the FastAPI directly the way the desktop console
 * does. `API_BASE` is `http://127.0.0.1:8000`, which on a handset means *the
 * handset's* loopback, and the API's CORS allowlist is `localhost:3000` /
 * `127.0.0.1:3000`, so a browser on `http://<laptop-ip>:3000` would be blocked
 * even if the address resolved. Forwarding through the Next server — which does
 * sit on the same machine as the API — makes the request same-origin and the
 * problem disappears without touching the API or its CORS policy.
 *
 * The contract is the API's, unchanged: `{ query, tenant_id }` in, the
 * `QueryResponse` body out, and the upstream status code passed through
 * verbatim so a 400 on an empty query still reads as a 400 on the client.
 * Only those two fields are forwarded — `user_id`/`channel` are the bots'
 * fields and a browser must not be able to set them.
 */
export async function POST(req: Request) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return Response.json({ detail: "Malformed request body." }, { status: 400 });
  }

  const { query, tenant_id } = (body ?? {}) as Partial<{
    query: string;
    tenant_id: string;
  }>;

  if (typeof query !== "string" || typeof tenant_id !== "string") {
    return Response.json(
      { detail: "Both 'query' and 'tenant_id' are required." },
      { status: 400 }
    );
  }

  try {
    const upstream = await apiFetch("/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, tenant_id }),
      // Client aborts (the composer's stop button) propagate to the API.
      signal: req.signal,
    });

    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: {
        "content-type": upstream.headers.get("content-type") ?? "application/json",
        "cache-control": "no-store",
      },
    });
  } catch (e) {
    if ((e as Error)?.name === "AbortError") {
      // The client walked away; nothing to report back to.
      return new Response(null, { status: 499 });
    }
    return Response.json(
      {
        detail:
          "Can't reach the Company Brain API. Start it with " +
          "`uvicorn api.main:app --port 8000`.",
      },
      { status: 502 }
    );
  }
}
