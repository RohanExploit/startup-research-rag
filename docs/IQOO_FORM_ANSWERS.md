# iQOO Hackathon — Round 1 submission form answers

**Track:** Smart Education · **Round:** 1 (online) · **Product:** Company Brain
**Repo:** github.com/RohanExploit/startup-research-rag

Copy the block under each **PASTE** heading verbatim. The *Why it's framed this way* note under
each is for you, not for the form.

---

## The one thesis every field must serve

> **The engine is built, benchmarked, and beats two rival architectures on the same hardware.
> The 30 hours puts it on the phone's silicon.**

Registrations are high and round one is a filter. Every answer below is written with the
confidence of a team that has receipts: the numbers are measured, reproducible, and better than
the alternatives we benchmarked against. Nothing here hedges, and nothing here is unverifiable.
The 30 hours is the next milestone of a system that already works, never a gap being confessed.

**Never invent a number.** Every figure below is measured and reproducible from the repo
(`docs/PITCH_METRICS.md`). If a form field wants a figure that isn't there, write "to be measured".

---

## 1. Idea title

*(short + punchy, min 5 characters)*

**PASTE:**

```
Company Brain — your college's answers, offline, on your phone
```

If the field is short (under ~40 characters):

```
Company Brain: your college, offline
```

If it is a hard-short field:

```
Company Brain
```

**Why it's framed this way.** "Company Brain" alone is memorable but says nothing about
education, and a Smart Education reviewer skimming hundreds of titles needs the category in the
first three words. The subtitle carries all three differentiators in one breath: it's the
*college's* data, it's *offline*, it's on a *phone*. No adjectives, no "AI-powered".

---

## 2. Description

*(min 50 characters — what you're building, for whom, how. Version below is 1,712 characters, sized for a 2,000-character cap.)*

**PASTE:**

```
Students get their college's answers from WhatsApp rumours, a queue outside the admin office, or a photo of a notice board. The institution already holds every answer — attendance rules, results, fee deadlines, who runs which lab — it just isn't reachable from where the student is standing. India has roughly 43,000 colleges and 4 crore students, and all of them have phones.

Company Brain puts the institution in the student's pocket. Ask in plain language. A router sends the question to the store that can actually answer it: SQL for numbers, vector search for facts, a graph for relationships, corpus-wide fan-out for "overall" questions. Every answer comes back with the source document it came from. It runs fully offline, because student records are PII — often minors' — and no college will paste its results database into a cloud LLM. That constraint is the reason nobody has shipped this yet.

The retrieval engine is built and benchmarked: 88.9% on 208 questions, against 62.5% for naive RAG and 69.7% for a GraphRAG-style design on the same corpus, the same local 4B model and the same frozen scorer. On multi-hop relational questions naive RAG gets 8 out of 54; we get 44. Correct abstention 20/20 — it declines rather than inventing. Median latency 1.85 s on 4 GB of VRAM. 280 automated tests. Zero cloud calls, enforced by a test.

We also publish what failed: our own validator rejected 15 of our own benchmark questions, and our own gates rejected 2 of 4 proposed improvements.

The engine is built, benchmarked, and beats two rival architectures on the same hardware. The 30 hours puts it on the phone's silicon: inference on the iQOO's own NPU, and Marathi and Hindi voice answered on-device.
```

**Why it's framed this way.** Problem in the student's words first, mechanism second, evidence third, roadmap last. It closes on the 30 hours so "why do you need the hackathon?" is answered before a reviewer thinks to ask it.

---

## 3. Video walkthrough URL

*(optional)*

**PASTE:**

```
TBD — link to be added before submission
```

**What to record.** Target 2:30, hard ceiling 3:00. Screen recording with voiceover. No slides,
no talking head, no intro music.

| Time | Show |
|---|---|
| 0:00–0:20 | The problem in the student's words. One line: "this is what a student does today to find out whether they're short on attendance." |
| 0:20–1:10 | Live query on the phone client. Ask a numeric question ("how many students failed at least two subjects?") and show the exact figure plus its source document. Then a relational one ("who heads the department that runs the HPC lab?"). |
| 1:10–1:35 | Ask something the corpus cannot answer. Show it decline. Say out loud: "20 out of 20 on abstention — it does not invent." |
| 1:35–2:05 | Aeroplane mode on. Ask again. Same answer. That is the entire privacy thesis in one shot, and it is the most convincing five seconds on the tape. |
| 2:05–2:30 | Benchmark table on screen: 62.5% / 69.7% / 88.9%. One sentence on what the 30 hours adds. Stop. |

**Rules for the recording.** Real screen, real latency — do not cut the 1.85 s wait; it is a
*good* number and cutting it makes the whole video look staged. Do not narrate the architecture;
the diagram is in the deck. If a query fails on take one, use the failure: say what failed and
what the measured failure rate is. By that point a judge has watched forty flawless demos.

---

## 4. Prototype URL

**PASTE:**

```
https://github.com/RohanExploit/startup-research-rag
```

If the form allows a note or a second field, add:

```
Full source, the 208-question benchmark harness and the 280-test suite. Everything in
this submission re-runs from a clean checkout. The phone client is the mobile route /m
in the dashboard app — a PWA against the same API — and that is what the 30-hour block
converts into an on-device Android client.
```

**Why it's framed this way.** The repo, not a demo link, is the proof: a benchmark harness a
judge can actually run outweighs a URL that might be down on judging day. The note names the
phone client honestly as a PWA instead of letting the reader assume a native app already exists.

---

## 5. Deck / supporting document

**PASTE / upload:**

```
docs/pitch_iqoo.pptx
```

**Why it's framed this way.** One artefact, not three. If the field takes a URL rather than a
file, point it at the repo's `docs/` folder so the deck, the metrics pack
(`docs/PITCH_METRICS.md`) and the 30-hour plan (`docs/30_HOUR_PLAN.md`) sit together. The metrics
pack is where a sceptical judge will go, and it includes a section on what we have *not* measured.

---

## 6. Android proficiency

**If there is a dropdown:** choose **Advanced**.

**PASTE (text box):**

```
Advanced. I have shipped a Flutter Android app — FixingNation, a civic grievance
reporter that lets citizens file complaints straight to the local authority
responsible — alongside 66 public repositories and 3,044 contributions in the last
year as a GitHub Developer Program member.

For this project the phone work is an adapter, not a rewrite, and that was a design
decision made on day one rather than a convenience discovered later. Generation sits
behind a single interface with the backend chosen at one call site, so an on-device
runtime (llama.cpp, or MediaPipe LLM Inference on Snapdragon) drops straight in.
Embeddings are MiniLM at roughly 90 MB and the index is FAISS-flat at a few MB per
college, so both ship as app assets. The entire pipeline was built to a 4 GB memory
budget — the same order as a phone's LLM budget.

That is why 30 hours is the right size for this problem: the hard architectural work
is already done, already measured, and already sized for the device.
```

**Why it's framed this way.** It leads with a shipped Android artefact a judge can open
(FixingNation), then converts the architecture into evidence that the on-device port is
routine rather than speculative. Every claim here is checkable on GitHub in under a minute,
which is exactly what makes the confidence land.

---

## 7. LLM proficiency

**If there is a dropdown:** choose **Advanced**.

**PASTE (text box):**

```
Strong, and specifically on the parts that are hard to fake.

Retrieval. We built a four-route system — SQL over DuckDB for numeric questions, vector
search for facts, graph traversal for relationships, corpus-wide fan-out for "overall"
questions — behind a deterministic router with an LLM classifier as fallback. Numeric
answers are computed by a parameterised query, not recalled by a language model, so the
system cannot hallucinate a figure it computed.

Local inference under a hard budget. qwen3:4b-instruct-2507-q4_K_M on an RTX 2050 with
4 GB of VRAM, temperature 0, zero cloud calls — enforced by a test, not by a policy
document. Context window, chunk budget and model keep-alive are all tuned against that
ceiling. We rejected a 4096-token context window because it pushed latency to 55.5 s.

Evaluation. A 208-question benchmark over a 30-document corpus in which one world model
renders both the documents and the questions, so a gold answer cannot disagree with the
corpus. Multi-hop questions are machine-proven multi-hop: the validator locates the
bridge entity and the answer in disjoint documents. That validator rejected 15 of our
own questions. Answers are frozen to disk before scoring, so no scorer can be written
after seeing the numbers it judges. Every improvement was pre-registered against a
statistical rule on two independent runs, and two of four candidates were rejected by
our own gates.

Result: 88.9% (185/208), against 62.5% for naive RAG and 69.7% for a GraphRAG-style
design on the same corpus, model, hardware and scorer. Correct abstention 20/20. Tabular
21/22. Median latency 1.85 s. 280 tests across 50 files, including tests that test the
benchmark itself.
```

**Why it's framed this way.** "Strong at LLMs" is what every submission says. The four concrete
artefacts here — a custom router, a 4 GB inference budget with a documented *rejected*
optimisation, a validator that threw out our own work, and answers frozen before scoring —
cannot be written by someone who has only called an API. The rejected 4096 context and the 15
rejected questions are load-bearing: they are the kind of detail you only mention if it happened.

---

## 8. Prior builds & hackathons

*(1,158 characters)*

**PASTE:**

```
Rohan Gaikwad — Claude Hackathon National Winner (Rank 1), Claude Impact Labs, Mumbai. Selected for Claude for Startups. NASA OSDR contributor.

Open source: 66 public repositories and 3,044 contributions in the last year; GitHub Developer Program member. Project Admin at GirlScript Summer of Code, Social Summer of Code and Eliter Coders Winter of Code — running projects, triaging PRs and mentoring contributors through their first open-source commits. Author of VishwaGuru, an open civic-tech platform that uses AI to help citizens contact their representatives and file public grievances (12 stars, 41 forks), and FixingNation, a Flutter/Android app for reporting civic grievances to the local authority responsible. github.com/RohanExploit

On this project he built the four-route retrieval engine, the local-inference path that fits a quantised 4B model into 4 GB of VRAM, and the benchmark harness that produced every number in this submission: 88.9% on 208 questions, 280 automated tests, zero cloud calls.

Priyanka Jadhav — Avishkar Innovation Program Zonal Qualifier. Academic topper at YSPM's Yashoda Technical Campus. Owns the question set, the ground truth and the student-side problem definition — including the 15 questions our own validator threw out before they could flatter us.
```

**Why it's framed this way.** The award proves performance under a clock, which is the exact question a 30-hour event asks. The Project Admin roles prove you can run other people, not just yourself. FixingNation proves shipped Android, which pre-empts any doubt about the on-device port. Every claim is one click from verification.

---

## 9. What makes you and your team stand out

*Highest-leverage field on the form. Both variants are ordered the same way: measurement
discipline first, privacy/on-device thesis second, team composition third.*

### Tight version

**PASTE:**

```
Most submissions tell you what worked. We can tell you what didn't, and what it cost.

We measured our system against two rival architectures on the same corpus, the same
local 4B model and the same frozen scorer: naive RAG 62.5%, GraphRAG-style 69.7%, ours
88.9%. On multi-hop relational questions naive RAG gets 8 out of 54; we get 44. Our own
validator rejected 15 of our own benchmark questions. Our own gates rejected 2 of 4
proposed improvements. A prompt-injection hardening we built measurably cost 1.4 points,
so we reverted it and wrote down why.

The idea — your college's answers in your pocket — is obvious. The reason nobody shipped
it is that student records are PII, often minors', so no college will paste its results
database into a cloud LLM. That is why this has to run on the device, and it is why we
spent the build fitting the entire pipeline into 4 GB.

Rohan Gaikwad is Claude Hackathon National Winner (Rank 1), Claude Impact Labs, Mumbai,
and selected for Claude for Startups; he builds the system. Priyanka Jadhav is an
Avishkar Innovation Program Zonal Qualifier; she owns the questions and the ground
truth. Neither of us grades our own homework.
```

### Fuller version

**PASTE:**

```
1. We measure, and we publish what failed.

Most hackathon projects can show you a demo. We can show you a benchmark. Our system
scores 88.9% (185/208) on a 208-question benchmark; naive RAG scores 62.5% and a
GraphRAG-style design scores 69.7% on the same corpus, the same local 4B model, the same
hardware and the same frozen scorer. On multi-hop relational questions — the class that
actually matters for institutional data — naive RAG gets 8 out of 54 and we get 44, a
5.5x improvement.

Those numbers are trustworthy because of how they were produced, not because we assert
them. One world model renders both the documents and the questions, so a gold answer
cannot disagree with the corpus. The validator proves multi-hop questions are genuinely
multi-hop, and it rejected 15 of our own questions. Answers are frozen to disk before
scoring, so no scorer can be written after seeing what it judges. Every improvement was
pre-registered against a statistical rule and had to pass two independent runs — and two
of four candidates failed, including one that passed its first run and failed
replication. A prompt-injection hardening we built measurably cost 1.4 points, so we
reverted it and said so in writing. We publish what we have not measured, too. A team
that never reports a negative result has either been extraordinarily lucky or is not
looking.

2. The privacy constraint is the product, not a checkbox.

India has roughly 43,000 colleges and 4 crore students, and every one of those students
has a phone. The answers they need already exist inside the institution. Nobody has
shipped this because student records are PII — frequently minors' — and no principal is
going to authorise pasting a results database into a cloud LLM. So it has to run on the
device. We designed for that from day one: 4 GB of VRAM, zero cloud calls enforced by a
test rather than by a policy document, per-tenant isolation, and provenance on every
answer. That is also why an on-device port on the iQOO is a natural next step for us
rather than a pivot.

3. We know exactly what we have not built yet.

The retrieval engine — the half that usually kills projects like this — is built and
measured. The phone is not. Router classification is 54.3%. Cross-document arithmetic is
14 of 24. Of our 23 remaining failures, 18 are the system correctly declining to answer,
and in 13 of those the answer was sitting in the retrieved context, which makes it a
prompt problem and the cheapest win left. We can hand you that list because we generated
it ourselves.

4. The two of us are not the same person twice.

Rohan Gaikwad — Claude Hackathon National Winner (Rank 1), Claude Impact Labs, Mumbai;
selected for Claude for Startups — built the retrieval engine, the local inference path
and the benchmark harness. Priyanka Jadhav — Avishkar Innovation Program Zonal
Qualifier, academic topper at YSPM's Yashoda Technical Campus — owns the question set,
the ground truth and the student-side problem definition. One of us builds the thing;
the other decides whether it actually answered the question. Neither of us grades our
own homework.
```

**Why it's framed this way.** Every submission in this track will claim a working prototype and
an impressive accuracy figure. Almost none will volunteer a rejected improvement, a reverted
security fix, and a list of their own remaining failures — so those paragraphs are what
differentiate, and they go first while the reader is still fresh. The privacy argument sits
second because it doubles as the market argument: it explains the empty space rather than merely
asserting one exists. The team split lands last as the payoff — an evaluation-focused co-founder
is the structural reason the measurement discipline in paragraph 1 was possible at all.

---

## Pre-submit checklist

- [ ] Every number in the form appears in `docs/PITCH_METRICS.md`. Nothing rounded up, nothing invented.
- [ ] The description ends on the 30 hours, so "why do you need the hackathon?" is answered before it is asked.
- [ ] Android proficiency says Advanced, and cites FixingNation (shipped Flutter/Android app).
- [ ] Rohan's award reads exactly: **Claude Hackathon — National Winner (Rank 1), Claude Impact Labs, Mumbai**. No "runner-up" anywhere.
- [ ] Repo link is live and the README's first screen carries the benchmark table.
- [ ] `docs/pitch_iqoo.pptx` attached; `docs/30_HOUR_PLAN.md` linked or pasted into the deck.
- [ ] Video URL replaced or the field left blank — never submit the literal string "TBD".
