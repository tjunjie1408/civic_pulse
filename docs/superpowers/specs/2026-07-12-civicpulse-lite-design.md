# CivicPulse-lite Problem Audit and MVP Design

Date: 2026-07-12  
Status: Approved concept baseline, implementation not started

## 1. Problem

CivicPulse-lite should help a municipal operations officer turn fragmented citizen complaints into consolidated, reviewable civic incidents. A complaint contains multilingual text, latitude, longitude, a timestamp, and an optional photo. The system should:

1. validate and normalize the complaint;
2. identify complaints that may describe the same incident;
3. group matching complaints into incidents;
4. rank incidents with configurable, deterministic policy rules;
5. explain every grouping and priority recommendation;
6. present incidents through a map, queue, detail view, and live submission flow.

The primary safety objective is to avoid false merges. Merging different incidents can hide work, misroute evidence, and present a misleading report count. A false split is undesirable but recoverable through officer review.

### Scope

The MVP covers a synthetic dataset of 120-180 complaints in Bahasa Melayu, English, Manglish, and common code-switching patterns. It supports five categories:

- blocked drain;
- flooding;
- pothole;
- uncollected rubbish;
- broken street light.

The MVP is a Python-first system: Python 3.12 owns data processing, models, algorithms, SQLite persistence, and a FastAPI backend; Streamlit is the first dashboard client. Pydantic DTOs and FastAPI OpenAPI form the contract boundary so a later Next.js + TypeScript client can replace Streamlit without rewriting the algorithm layer. It is designed for a single-user hackathon demonstration, not concurrent production council use.

### Constraints

- The core submission, clustering, ranking, and dashboard flow must work without an OpenAI API key or internet connection after model assets are cached.
- Core Python modules must pass Pyright strict mode and Ruff; `Any`, `dict[str, object]`, and `# type: ignore` are prohibited unless a code comment records the external boundary and reason.
- Pydantic validates API/domain input and SQLite repeats critical range, nullability, enum, uniqueness, and referential-integrity constraints.
- Geographic distance, time difference, and category compatibility are hard constraints. They are not combined into an unexplained weighted similarity score.
- Priority rules and thresholds are prototype policy parameters, not objective measures of civic harm.
- Photo analysis is optional enrichment. Failure or absence must not block complaint submission, clustering, ranking, or dashboard rendering.
- The UI must use phrases such as `photo consistency` and `officer review required`; it must not claim a photo is verified, genuine, current, or captured at the reported location.

### Non-goals

- production integration with a council complaint system;
- citizen identity collection, authentication, or case-status messaging;
- automatic complaint rejection, closure, enforcement, or department dispatch;
- proof that an uploaded image is authentic or location-correct;
- production-scale Spark, Databricks, or GPU infrastructure;
- model fine-tuning;
- real-time multi-user updates;
- claims of production accuracy from synthetic data.

### Clarified terms

- **Complaint:** one submitted report.
- **Incident:** one connected component of complaints that pass every incident-matching constraint.
- **Semantic match:** text descriptions are compatible; this alone does not establish the same incident.
- **Incident match:** category, geography, time, and semantic checks all pass.
- **Hotspot:** the display location and density of consolidated incidents, not an independent predictive model.
- **Priority:** a configurable operational recommendation with reasons, not an objective severity truth.

## 2. Evidence

| Claim | Status | Source and interpretation |
| --- | --- | --- |
| The repository currently contains an embedding benchmark, 40 labelled pairs, and unit/integration tests, but no application, database, clustering engine, priority engine, or dashboard. | Observed | `scripts/run_embedding_benchmark.py`, `benchmarks/manglish_complaint_pairs.json`, `tests/`, and scoped file listing on 2026-07-12. |
| The environment is managed by uv and currently locks `sentence-transformers>=5.6.0`. | Observed | `pyproject.toml` and `uv.lock`. |
| On the expanded 40-pair benchmark, raw semantic scores overlap; the hybrid gate must therefore use category, geographic, temporal, and explicit-location constraints. | Observed | `uv run --offline python -m scripts.run_hybrid_benchmark` on 2026-07-12 using `intfloat/multilingual-e5-small`. |
| A conservative threshold of 0.950 produces zero false merges but 15 false splits and F1 0.211 on the current data. | Observed | Same benchmark run. |
| A single cosine threshold over raw complaint text is not sufficient for this benchmark. | Inferred, high confidence | The score distributions overlap completely and the negative mean is higher than the positive mean. |
| The model itself is not proven unsuitable for the project. | Unknown | Prompt prefixes, the small hand-authored dataset, category overlap, location words, and the absence of hard constraints may explain the failure. |
| Category, geographic, temporal, and explicit-location constraints can make the semantic signal useful. | Supported, medium confidence | The automation gate produced 3/4 clear-positive auto-matches (75%) with zero false automatic merges at the strong-entity threshold. |
| The project can operate on 120-180 complaints with an O(n²) pair comparison after embeddings are cached. | Assumed | The expected data volume is small. A timed integration test will confirm whether the assumption holds on the development machine. |
| Streamlit is sufficient for a single-user hackathon dashboard and live submission demo. | Assumed | It reduces integration scope, but the UI and rerun behavior have not yet been tested. |
| A FastAPI/OpenAPI boundary is worth adding before the dashboard. | Inferred, medium confidence | It isolates algorithm/service logic, enables contract testing, and preserves a path to a generated TypeScript client without forcing a two-language MVP immediately. |
| Python 3.12 is a safer project baseline than the current 3.14 environment. | Inferred, medium confidence | The attached architecture decision prioritizes mature ML/web package compatibility; a fresh `uv sync` and dependency smoke test must verify it. |

Official OpenAI documentation confirms that current Responses API requests can include `input_image` content and that the Python SDK supports Pydantic-backed structured outputs. Those capabilities justify a later provider adapter, but do not change the core MVP dependency boundary:

- https://developers.openai.com/api/docs/guides/images-vision
- https://developers.openai.com/api/docs/guides/structured-outputs

## 3. Assumptions and Unknowns

### Assumptions accepted for the MVP

- A council officer prefers conservative grouping and can manually review false splits.
- Five categories are sufficient to demonstrate the product concept.
- A 500-metre radius and seven-day time window are acceptable initial prototype limits.
- Unknown-category complaints are not auto-merged.
- Synthetic sensitive-location points for schools and hospitals are acceptable for the priority demo.
- SQLite is used by one application process during the demonstration.
- The first Streamlit client may use the typed in-process service facade for a one-command demo, but its request/response DTOs must be identical to the FastAPI contract.
- Next.js, MapLibre/Leaflet, TanStack Query, Zod, and a generated TypeScript client are a post-MVP frontend decision, not parallel MVP work.

### Decision-relevant unknowns

- Real Malaysian council complaint language and location distributions are unavailable.
- The best semantic threshold after hard constraints is unknown.
- The 40 hand-authored pairs may overstate or understate Manglish difficulty.
- Priority weights have no historical outcome or council-policy calibration.
- The final OpenAI vision model and activity credits are unknown.
- Venue network reliability and deployment environment are unknown.

### Smallest checks for the unknowns

- Add category, coordinates, timestamps, and incident labels to every benchmark pair.
- Split the dataset into fixed calibration and holdout partitions before tuning.
- Compare raw text against normalized text while holding the model and partition constant.
- Run the full matcher on the holdout set and report false merges and false splits separately.
- Keep priority values in a versioned JSON policy file and expose reasons in the UI.
- Run the complete demo with network access disabled after model prewarming.

## 4. Competing Explanations

### Explanation A: lexical overlap dominates raw embedding similarity

Supporting evidence:

- The strongest non-matches reuse the same category words while changing block, landmark, or incident purpose.
- The pure embedding benchmark omits hard geographic and time filtering.

Contradicting evidence:

- Some weak positive pairs are also direct bilingual paraphrases, so hard constraints alone may not recover them.

Falsifier:

- Run a fixed holdout benchmark using category, 500-metre radius, seven-day window, normalized semantic similarity, and explicit-location tri-state decisions. Reject this explanation if false automatic merges remain or any positive holdout pair is forced to `no_match`.

### Explanation B: the benchmark design is too small or internally inconsistent

Supporting evidence:

- It contains 40 hand-authored pairs, including 10 added adversarial holdout pairs for blocks, streets, landmarks, units, and generic locations.
- Two pairs are semantic matches but incident non-matches due to time, and most records lack full incident metadata.

Contradicting evidence:

- The overlap is large enough that a raw-text threshold is demonstrably unusable on the current examples, even if they are not representative.

Falsifier:

- Complete incident labels and metadata for all 40 pairs, freeze the split, and report the expanded holdout result without selecting a more favorable subset.

### Explanation C: the selected model or E5 query/passage formulation is the main cause

Supporting evidence:

- The benchmark uses one model and one prefix formulation.
- Manglish abbreviations and local landmarks may be underrepresented in pretraining.

Contradicting evidence:

- Many false merges are events that text alone should not distinguish; changing the encoder cannot replace geography and time.

Falsifier:

- Only if the hybrid matcher misses its holdout gate, compare one alternate multilingual encoder using the same frozen data and constraints. Do not expand to a multi-model survey before that failure.

## 5. Failure Model

### Input boundary

- empty, whitespace-only, excessively long, malformed Unicode, or control-character text;
- non-numeric, non-finite, or out-of-range coordinates;
- timestamps without time zones, implausible future timestamps, and invalid formats;
- unclassified/`other` category signals and mixed-category descriptions;
- duplicate form submissions caused by Streamlit reruns;
- malformed or incompatible FastAPI request/response payloads and OpenAPI drift;
- oversized, renamed, malformed, or unsupported image uploads.

### Model and dependency boundary

- missing local model files when offline;
- model-load failure or incompatible cached artifacts;
- embedding dimension/model mismatch in persisted cache;
- OpenAI API key absence, timeout, rate limit, malformed structured response, or provider outage;
- photo analysis returning a confident but incorrect observation.

### State boundary

- complaint stored but incident memberships not updated;
- cluster replacement interrupted mid-write;
- stale embeddings after normalization or model version changes;
- duplicate complaints from repeated submission;
- database locked or corrupted;
- reset operation leaving a mixed seed/live state.

### Resource and timing boundary

- cold model load delaying the demo;
- repeated all-pairs calculation after each submission;
- image payload memory growth;
- map rendering too many raw points;
- network unavailability during the photo enhancement.

### Required invariants

- Every stored complaint belongs to exactly one current incident after a successful recluster.
- Incident membership replacement is atomic.
- Identical idempotency keys return the original complaint and do not create duplicates.
- A photo-analysis failure never rolls back or hides a successfully submitted complaint.
- A known category mismatch, distance over 500 metres, or time gap over seven days can never auto-merge.
- Every priority band has at least one human-readable reason.

## 6. Proposed Approach

### Recommended architecture

Use a local-first modular monolith:

```text
Streamlit MVP UI
    -> typed client/service facade using API DTOs
FastAPI delivery adapter
    -> generated OpenAPI contract
Both
    -> CivicPulseService
        -> input validation
        -> normalization and category detection
        -> local embedding provider and cache
        -> hard-constrained pair matcher
        -> connected-component clustering
        -> deterministic priority policy
        -> SQLite repository

Optional photo action after submission
    -> PhotoAnalyzer interface
        -> OpenAI adapter when configured
        -> unavailable/error result without affecting the core incident
```

The dataset is small enough to recompute all incident components after a submission. Recomputing is easier to reason about than incremental merge/split mutation and allows incident tables to be replaced atomically in one transaction.

Python is intentionally used for the ML/data/backend path, but the architecture is not Python-only. Domain and API contracts are strict, versioned, and serializable. A future TypeScript frontend must consume generated OpenAPI types rather than manually duplicating Python DTOs.

### Matching decision

Two complaints auto-match only when all conditions pass:

```text
known categories are equal
AND Haversine distance <= 500 metres
AND absolute timestamp gap <= 7 days
AND explicit location entities are compatible
AND normalized-text cosine similarity >= strong-entity threshold
```

If location entities are missing or ambiguous, the pair is `review_required`; if explicit entities conflict, it is `no_match`. If either category is `other`, the pair is `review_required` and is not auto-merged in the MVP.

### Initial normalization boundary

Normalization performs Unicode NFKC normalization, lowercase conversion, whitespace compaction, punctuation separation, and a versioned local alias map such as:

```text
jln -> jalan
skolah -> sekolah
dpn -> depan
longkang sumbat -> longkang tersumbat
lampu jln -> lampu jalan
```

It must not translate complete complaints, remove landmark tokens, or generate new facts.

### SCM-inspired priority policy

Priority is a deterministic policy graph, not an empirically identified causal model. It uses confirmed incident evidence only. The configurable rules include medium/high/critical confirmed-report thresholds, high/critical unresolved-hour thresholds, sensitive-location radius, critical/high safety signal names, and an evidence-completeness threshold.

`REVIEW_REQUIRED` candidates never increase confirmed report count or trigger safety rules. Conflict incidents receive `review_required` status rather than a normal operational band.

The output exposes normalized signals, triggered rules, policy version, and human-readable reasons. The prototype does not claim that blocked drains cause flooding; it encodes transparent domain assumptions for operational triage.

### Incident identity and candidate references

Phase 3 `incident_id` values are deterministic membership-derived snapshot identifiers: the same confirmed membership yields the same UUID5, but adding a complaint can produce a new snapshot ID. Persistence must not present this as a permanent case identity until a separate record/reconciliation layer exists.

`review_candidate_ids` is a convenience index. When full `review_candidates` evidence is present, the domain validator requires the IDs to be derived from those relationship objects; the two fields are not independent sources of truth.

### Photo consistency boundary

Photo analysis is a separate officer-triggered action after submission. It returns:

```text
status: likely_consistent | unclear | likely_inconsistent | unavailable | error
observed_category: one of the five categories or other
observation: short factual image description
officer_review_required: always true
```

The analysis result does not alter incident matching, priority, or complaint authenticity. This preserves the CV differentiator without introducing a single point of failure.

## 7. Verification Plan

### Algorithm gate before application work

Freeze a 20-pair calibration set and a 10-pair holdout set with five incident matches and five incident non-matches in the holdout. Proceed to clustering only if the hybrid matcher achieves:

- zero false merges on the holdout;
- zero positive holdout pairs forced to `no_match` (auto-match or review-required are acceptable);
- at least 75% `auto_match` on holdout positives explicitly labelled `clear`;
- ambiguous positives may remain `review_required`;
- every rejection includes the failed hard constraint or semantic score;
- the selected threshold and benchmark version are recorded.

The benchmark distinguishes three graph layers: confirmed incident edges use only `auto_match`; review-candidate edges use `review_required` and are not confirmed incidents; `no_match` pairs are rejected.

If the gate fails, stop application expansion and inspect the smallest set of misclassified pairs. Apply only one remediation at a time: alias normalization, category lexicon correction, or one alternate encoder comparison.

### Normal tests

- valid multilingual complaint validation;
- normalization and category extraction;
- Haversine distance and time-window boundaries;
- semantic threshold at below/equal/above values;
- deterministic clustering and priority reasons;
- SQLite add/read/recluster transaction;
- FastAPI request validation, response schema, error mapping, and OpenAPI snapshot;
- dashboard seed load, queue, map, detail, filters, and submission.

### Negative and boundary tests

- invalid text, coordinate, timestamp, category, and photo input;
- `other`-category no-auto-merge behavior;
- distance exactly 500 metres and just above it;
- time gap exactly seven days and one second above it;
- duplicate idempotency key;
- model cache unavailable while offline;
- database exception during cluster replacement;
- photo analyzer timeout, structured-output error, and missing API key.

### Property and regression tests

- cluster membership is independent of complaint input order;
- every complaint appears in exactly one cluster;
- no cluster contains a pair that violates a hard constraint path without an alternate connected path being visible in the explanation;
- normalization is idempotent;
- priority output is deterministic for the same incident and policy version;
- current 40 benchmark pairs remain versioned regression cases, with clear and ambiguous positives reported separately.

### Resource and demo tests

- cached reclustering of 180 complaints completes within three seconds on the development machine;
- warm live submission updates the dashboard within five seconds without photo analysis;
- the complete core demo runs with network access disabled;
- reset restores the exact seed complaint count and checksum;
- image upload rejects payloads above 5 MiB before provider invocation.

## 8. Risks

| Risk | Consequence | Control | Residual uncertainty |
| --- | --- | --- | --- |
| Synthetic benchmark overfitting | Demo metrics do not generalize | Frozen holdout, explicit synthetic-data label, no production claim | Real council performance remains unknown. |
| Connected-component chaining | A-B and B-C links can place A and C together despite weak direct similarity | Show contributing edges; test hard constraints per edge; allow officer inspection | Policy may later require stricter cluster cohesion. |
| Arbitrary priority parameters | Misleading urgency | Versioned config, reason display, policy disclaimer | Real calibration requires council data and policy owners. |
| Streamlit reruns | Duplicate writes or repeated model work | Idempotency key, resource caching, service-layer tests | Multi-user concurrency is out of scope. |
| API/DTO drift | Streamlit and future TypeScript clients interpret incidents differently | Shared Pydantic DTOs, OpenAPI snapshot, contract tests | Generated TypeScript client is post-MVP. |
| Offline model cache missing | Core matching unavailable | Prewarm and startup health check; cached fallback dataset for demo | First installation still needs network. |
| Photo API failure or hallucination | Delayed or misleading enrichment | Separate action, bounded timeout, structured schema, never affects core, officer review always required | Visual observations remain probabilistic. |
| Python runtime compatibility | Installation or runtime failure | Pin Python 3.12 with uv, lock dependencies, and run FastAPI/Streamlit/model import smoke tests first | Future runtime upgrades require a new lock and full verification. |

Current robustness verdict: `CONDITIONALLY READY` for matching evidence. The safety gate and automation gate pass, but the application does not yet exist and the benchmark remains synthetic.

## 9. Stop Condition

Problem exploration ends and full MVP implementation may proceed when all of the following are true:

1. all benchmark pairs have category, coordinates, timestamps, semantic labels, and incident labels;
2. calibration and holdout IDs are frozen in source control;
3. the hybrid matcher passes zero false automatic merges, zero positive `no_match` decisions, and at least 75% auto-match rate on clear positive holdout pairs;
4. the selected threshold, normalization version, model name, and benchmark version are recorded;
5. the project owner accepts that priority parameters are configurable prototype values and that photo analysis is optional, post-submission enrichment.

If item 3 fails, the implementation may scaffold review UI but must stop before confirmed clustering, cluster-based priority, or claims that complaints were automatically consolidated. The next action is one controlled remediation experiment, not additional product surface.
