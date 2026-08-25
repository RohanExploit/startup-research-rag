# What we will build in 30 hours

**iQOO Hackathon · City Battle · Track: Smart Education · Team: Rohan Gaikwad, Priyanka Jadhav**

---

## Headline deliverable

> **Company Brain running on the iQOO itself — model on the phone's silicon, index in the app's
> assets, and a student asking a question out loud in Marathi or Hindi and getting the answer
> back with its source. Aeroplane mode on, the whole time.**

And, because it is the thing we would want to see from someone else: **the same 208-question
benchmark re-run on the device**, so the on-device number is directly comparable to the 88.9%
we measured on a laptop. Not "it feels fast on the phone" — a number, produced by the same
frozen scorer.

---

## Why this is 30 hours of work and not 300

We are not starting the hard half at the venue. The retrieval engine is built and benchmarked.
Three specific design decisions, all taken months before this hackathon existed, are what make
the port an evening rather than a project:

| What is already true | Why it collapses the port |
|---|---|
| **Generation is one interface with a swappable backend.** `generation/answer.py` exposes a single `generate_answer(query, context, qtype)`; today it posts to a local Ollama endpoint, with a gated fallback path behind it. | Swapping in llama.cpp or MediaPipe LLM Inference on Snapdragon means writing one adapter behind an existing signature. Routing, retrieval, prompting, provenance and abstention are untouched. This is the difference between an integration and a rewrite. |
| **Embeddings are MiniLM (`all-MiniLM-L6-v2`, ~90 MB) and the index is FAISS-flat** (`faiss.IndexFlatL2`), a few MB per college. | Both fit in app assets. Flat means no training step, no index-build on device, and exact search — nothing to tune under time pressure. |
| **The whole pipeline already fits a 4 GB budget** — RTX 2050, `qwen3:4b-instruct-2507-q4_K_M`, median 1.85 s end-to-end. | A phone's LLM budget is the same order of magnitude. We are not shrinking a cloud system down to a phone; we built to the phone's budget on a laptop and are now moving it across. That was a day-one constraint, not a lucky break. |

What genuinely remains, and is genuinely a day's work: the native inference adapter, Indian-language
speech in, the student-facing screens, and the measurement.

---

## Operating rules for the 30 hours

- **Both of us are never asleep at the same time.** Rotating 3-hour rest windows from hour 12.
  Whoever is awake owns the build; the other one hands over in writing.
- **Every block ends with something committed and runnable.** No block ends with "nearly working."
- **Fallbacks are decided in advance, not at hour 22.** Each block below names its fallback and
  the moment we take it. We take it when the clock says so, not when we feel like it.
- **The demo is rehearsed on the real device, on the venue network, before hour 29.**
- **Nothing goes in the demo that we have not measured.** If a number is not measured yet, we say
  "to be measured" out loud. That rule got us here; we are not abandoning it at the finish line.

---

## The blocks

### Block 0 · Hours 0–3 · Bring-up: first token on the iQOO

**Goal.** Get the phone to produce a token from a local model. Nothing else. This is the block
that decides whether the rest of the plan is real, so it happens first and it happens fast.

**Owner.** Rohan builds. Priyanka, in parallel, sets up the demo corpus on the device: the
policy documents, the results table and the 12 institutional documents, plus the shortlist of
questions a real student would ask.

**Definition of done.**
- Android project builds and installs on the iQOO.
- A quantised model file is on device and loads.
- A hardcoded prompt returns a completion, with the phone in aeroplane mode.
- Decode speed logged to the console — first datapoint, however bad.

**Fallback.** If the 4B q4 checkpoint will not load or is unusably slow on this device, drop
immediately to a smaller quantised model (3B, then 1.5B) *and record that we did*, because the
accuracy cost of that swap is something we will measure in Block 5 rather than assume. If the
native runtime itself fights us past hour 3, we fall back to running the existing server on a
laptop over a local hotspot — still zero internet, still no cloud — and treat the on-device port
as the stretch goal, not the spine. We would say so on stage.

---

### Block 1 · Hours 3–8 · The adapter: on-device generation behind the existing interface

**Goal.** `generate_answer()` served by the on-device runtime instead of an HTTP call to Ollama,
with every route (FACT / GLOBAL / LOCAL / TABULAR) producing the same shape of answer it produces
today, including provenance and abstention.

**Owner.** Rohan.

**Definition of done.**
- The same prompt templates, unchanged, run through the device runtime.
- All four route types answer end-to-end on device against the demo corpus.
- Abstention still works: a question the corpus cannot answer gets declined, not invented.
- A smoke set of ~20 questions passes on device, compared against the same 20 on the laptop.

**Fallback.** If prompt formatting or the chat template diverges enough to break the structured
GLOBAL output, we simplify the GLOBAL template for on-device only and note the divergence in the
results rather than quietly shipping two different systems and comparing them as one.

---

### Block 2 · Hours 8–13 · The rest of the pipeline on device: retrieval with no server

**Goal.** Kill the server. Embeddings, index, tabular store and graph all resident in the app, so
the phone answers with no network interface up at all.

**Owner.** Rohan builds retrieval; Priyanka verifies answers against ground truth as each route
comes up, so we find a broken route within minutes rather than at the demo.

**Definition of done.**
- MiniLM embeddings computed on device.
- FAISS-flat index and the tabular store shipped as app assets and read at runtime.
- Aeroplane mode on for the entire block. If it needs a network, it is not done.
- The four routes answer from device-local data, with the source document shown.

**Fallback.** If on-device embedding is the bottleneck, we precompute query embeddings for the
demo question set and ship a small on-device cache — clearly labelled as a demo shortcut, not
claimed as the general path. If FAISS itself will not build for the target ABI, a flat
brute-force cosine scan over a few thousand vectors is a dozen lines and is fast enough at this
corpus size; the index type is an optimisation, not the product.

---

### Block 3 · Hours 13–18 · Marathi and Hindi voice input, answered on-device

**Goal.** A student holds the phone, asks in Marathi or Hindi, and gets a correct answer back
with its source. Speech and answer both on-device.

**Owner.** Rohan on speech-to-text and the query path; Priyanka writes and records the
Marathi/Hindi question set and grades the transcriptions — she owns whether the system heard the
question, not just whether it answered one.

**How it hangs together.** Our embeddings are English-only, so the language handling sits in
front of retrieval rather than inside it: speech-to-text produces the question in the spoken
language, the on-device model normalises it to English in a single short call, routing and
retrieval run exactly as they do today, and the answer is rendered back in the language the
student used. This keeps the measured retrieval path untouched — which also means we can measure
what the translation step costs us, instead of guessing.

**Definition of done.**
- Marathi and Hindi speech captured and transcribed on-device, with no network.
- At least 10 spoken questions per language answered correctly end-to-end.
- Answers returned in the language asked.
- Word-error-rate and end-to-end latency for the voice path logged. Both to be measured.

**Fallback ladder, in order.** (1) A small quantised on-device ASR model. (2) Android's own
on-device speech recogniser with the offline `mr-IN` / `hi-IN` language packs pre-downloaded —
lower ceiling, far lower risk. (3) Typed Devanagari input, with the translation-and-answer path
still fully on-device, and we demo voice in English only. Even at rung 3 the interesting claim
— *an Indian-language question answered on-device from the college's own private data* — still
holds; only the microphone drops out.

---

### Block 4 · Hours 18–22 · The student-facing app

**Goal.** Make it look like something a student would actually open, not a debug console.

**Owner.** Priyanka owns the screens and the wording — she is the one who knows what a student
asks and in what words. Rohan wires them.

**Definition of done.**
- Ask screen with the microphone as the primary control.
- Answer screen showing the answer, the source document and section, and a visible offline
  indicator.
- The "I don't have enough information" state is designed on purpose, not left as an error toast.
  Abstention is a feature we measured at 20/20; it should not look like a crash.
- Cold launch to first question in under a handful of taps.

**Fallback.** If native screens are eating the clock, we ship the existing PWA route (`/m`)
wrapped as the shell over the on-device engine. The engine is the claim; the chrome is not. We
will not lose the on-device port to a layout problem.

---

### Block 5 · Hours 22–26 · Measurement — the block we will not skip

**Goal.** Turn "it runs on the phone" into numbers a judge can check. This is the block that
distinguishes us from every other team demoing a phone app at hour 29, and it is scheduled with
four hours of clock in front of it precisely so it cannot be squeezed out.

**Owner.** Rohan runs the harness; Priyanka scores and checks the golds. Same division as the
laptop benchmark — the person who built it does not decide whether it was right.

**What we measure.**

| Metric | How | Comparable to |
|---|---|---|
| **Accuracy on device** | Re-run the same 208-question benchmark, same corpus, same frozen scorer, on the phone. Only the hardware and the inference backend change. | The 88.9% (185/208) laptop number, directly |
| **Decode throughput** | Tokens/sec on device, prompt-eval and generation reported separately | To be measured; no laptop equivalent is claimed |
| **Cold start** | App launch → first answer, cold model load; and again warm | To be measured |
| **End-to-end latency** | Median across the benchmark run | The 1.85 s laptop median |
| **Battery per 100 queries** | Battery percentage drain across a scripted 100-query run, device at a fixed brightness, from a known start charge | To be measured — this is the number that decides whether a student would actually keep the app |
| **Voice path** | Word error rate on Priyanka's Marathi/Hindi question set, plus the accuracy delta the translate-to-English step costs on a benchmark subset | The same subset run in English |

**Definition of done.** A results table with real figures in every row, or an explicit
"to be measured" where a run did not finish. No estimates presented as measurements.

**Fallback — and this one is pre-registered, on purpose.** If the full 208 will not finish on
device inside the block, we run a **stratified subset fixed before we look at any result** —
proportional across FACT / GLOBAL / LOCAL and including the abstention questions — and we run
*the same subset on the laptop* so the comparison stays apples-to-apples. We report it as a
subset, with its size, and we do not extrapolate it to 208. If we had to drop to a smaller model
in Block 0, this block is also where that decision gets its price tag: we report the on-device
number for the model that actually ran, next to the laptop 4B number, and we name the gap rather
than blurring it.

---

### Block 6 · Hours 26–29 · Demo rehearsal and the failure drill

**Goal.** Rehearse until the demo is boring. A demo that has never been run end-to-end on the
venue floor is not a demo; it is a hope.

**Owner.** Both. Priyanka drives the device — she asks the questions, because she wrote them and
because the person who built the system should not be the person operating it on stage.

**Definition of done.**
- Three full run-throughs on the actual iQOO, on the actual venue network conditions, timed to
  the allotted slot.
- The aeroplane-mode moment rehearsed as a deliberate beat, not an afterthought.
- One deliberate failure rehearsed: we ask something the corpus cannot answer, it declines, and
  we say the abstention number out loud. Owning a limitation on stage is worth more than a
  fourth successful query.
- A recorded backup video of the working demo, on the device, saved locally.
- Answers ready for the three questions we know are coming: *how is this different from
  ChatGPT?*, *why does it need to be offline?*, and *what doesn't work yet?* We answer the third
  one with the actual list.

**Fallback.** If the device fails at the venue, we play the recorded run and narrate the
measurements live. If the projector fails, we hand the phone to the judge — which is arguably the
better demo anyway.

---

### Block 7 · Hours 29–30 · Buffer and submission

**Goal.** Land it. Final commit, README and metrics pack updated with the on-device numbers,
deck's last slide replaced with the measured results, submission uploaded with time to spare.

**Owner.** Rohan commits and submits; Priyanka proofreads every number against the run logs.

**Definition of done.** Submitted. Not "submitting."

**Fallback.** This hour exists to be spent on the block that slipped. If nothing slipped, we use
it to widen the benchmark subset from Block 5 — more measurement, never more features.

---

## What we will deliberately NOT build in these 30 hours

Scope discipline is the reason the list above is deliverable. Each of these is a real thing we
want; none of them is a thing we will start at a hackathon.

| Not doing | Why not |
|---|---|
| **Fixing router classification (currently 54.3%)** | It is our most quotable weakness and it would be tempting to fix on stage. But we already measured that both destination routes were repaired, so router accuracy is now worth close to zero accuracy points — it matters for latency and cost. Spending hackathon hours on a number that looks bad but buys nothing would be theatre. |
| **Cross-document arithmetic (14/24)** | This is a model-capability gap, not an engineering gap. The fix is a compute step or a bigger model, and neither is a 30-hour job on a phone. We will state the number rather than paper over it. |
| **The prompt-injection hardening we reverted** | We built it, measured that it cost 1.4 accuracy points, and reverted it. The real fix is an input classifier, which is a research task with its own evaluation. Re-adding the reverted version to have something to say about security would be exactly the behaviour our own gates exist to prevent. |
| **A native iOS build** | One platform, done properly, on the device in the room. |
| **Multi-college sync, accounts, admin portal** | The operator dashboard already exists on the server side. None of it is on the critical path to the on-device claim, and all of it is a week of polish that would eat the measurement block. |
| **Text-to-speech for answers** | Voice *in* is the hard, differentiated half — it is what makes the app reachable for a student who would not type an English question. Voice *out* is a solved commodity and can be added any time after the clock stops. |
| **Retraining or fine-tuning anything** | Every number we have is comparable precisely because the model, corpus and scorer are held fixed. Fine-tuning mid-hackathon would invalidate our own baseline and leave us with a phone app and no evidence. |
| **Widening the benchmark corpus** | Adding documents would change the denominator and break comparability with the 88.9%. If we add corpus, we add it after, and we re-run everything. |

The unifying rule: **nothing that breaks comparability with the numbers we already published, and
nothing that trades the measurement block for a feature.** We would rather arrive at hour 30 with
a slightly smaller app and a results table than with a bigger app and an anecdote.

---

## Risk register

| Risk | Likelihood | What we do |
|---|---|---|
| 4B q4 too slow or too large for the device | Medium | Step down model size in Block 0, and price the accuracy cost in Block 5 rather than hide it |
| On-device runtime toolchain fights the build | Medium | Hard cutover at hour 3 to laptop-over-hotspot; still offline, port becomes the stretch goal |
| Marathi/Hindi ASR quality poor on-device | Medium | Three-rung fallback ladder in Block 3; the on-device Indian-language *answer* claim survives even at rung 3 |
| Full 208-question run will not finish on device | High | Pre-registered stratified subset, run on both device and laptop |
| Device unavailable or shared at the venue | Low | Backup Android device; recorded demo video as the last resort |
| We run out of time | Certain, in some form | Blocks are ordered so that everything after Block 2 is independently droppable, and Block 5 sits before the polish, not after it |

---

## What a judge can check, at any hour

- The repo, with the benchmark harness and all 280 tests, re-runnable from a clean checkout.
- `docs/PITCH_METRICS.md`, including the section listing what we have **not** measured.
- The device, in aeroplane mode, answering a question they choose.
- Our on-device results table, next to the laptop one, with the same scorer on both.
