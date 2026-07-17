# CivicPulse README Design

## Goal

Create a polished, dual-audience README that helps Hackathon reviewers understand the CivicPulse product story quickly and gives developers enough verified information to run, test, and extend the repository.

## Audience and tone

- Primary audience: Hackathon reviewers and technical evaluators.
- Secondary audience: contributors and future maintainers.
- Tone: confident, concrete, concise, and evidence-led.
- Visual language: restrained civic-operations aesthetic using headings, compact tables, badges, callouts, and one Mermaid workflow diagram.

## Information architecture

1. Hero section
   - CivicPulse title and one-line positioning.
   - Badges for Python, FastAPI, Streamlit, tests, and license/status only where verified.
   - Short statement that this is an offline-first civic incident intelligence prototype.

2. Product story
   - Explain the operational problem: duplicate, multilingual, spatially and temporally related complaints are difficult to triage.
   - Show the closed loop: submit complaint → normalize/match → confirmed or review-required evidence → officer resolution → snapshot/priority refresh.
   - State the uncertainty boundary explicitly: candidates are not counted as confirmed incidents or operational priority.

3. Demo experience
   - Describe the synthetic Shah Alam-inspired municipal district.
   - Identify the five synthetic zones and the upstream-drain/downstream-flood narrative.
   - Clearly label all locations and complaints as synthetic.
   - Describe Dashboard capabilities: ranked queue, incident detail, hotspot map, complaint submission, review evidence/actions, and safe deterministic reset.

4. Architecture
   - Include a Mermaid flow showing Streamlit Dashboard → typed HTTP gateway → FastAPI API → application service → SQLite/read models.
   - Call out that the Dashboard never imports service, repository, SQLite, or backend domain internals.
   - Explain snapshot identity and API-owned sorting/priority.

5. Quick start
   - Use the repository's actual Python 3.12 and uv workflow.
   - Include offline dependency setup, API start, Dashboard start, and browser URLs.
   - Keep seed/model assumptions explicit and point to readiness checks.

6. Verification
   - Include the verified commands for tests, Pyright, Ruff, and hybrid benchmark.
   - Report the current known FastAPI/Starlette/httpx deprecation warning without presenting it as a product failure.

7. Repository map and API surface
   - Summarize `src/civicpulse`, `src/civicpulse/api`, `src/civicpulse_dashboard`, tests, config, data, and scripts.
   - List representative read and mutation endpoints without duplicating the full OpenAPI document.

8. Safety, limitations, and roadmap
   - Explain synthetic data, offline model assumptions, no authentication framework, reset deployment caution, and no causal SCM claim.
   - Point to Phase 9 reliability/performance work and future photo/risk-propagation work as non-current scope.

## Source-of-truth constraints

- Do not claim deployment, authentication, cloud hosting, real municipal data, or causal risk prediction unless present in the repository.
- Use `180 passed`, Pyright 0 errors, Dashboard Ruff passing, and the existing benchmark evidence only when describing current verification.
- Keep the API boundary and uncertainty semantics consistent with the frozen v1 contract.
- Do not include secrets, generated databases, model caches, or untracked tool metadata.

## Acceptance criteria

- A reviewer can understand the product, demo geography, and differentiator from the first screenful.
- A developer can start the API and Dashboard from the documented commands.
- Every command and path is present in the repository or clearly marked as environment-dependent.
- The README distinguishes confirmed, review-required, and conflict states.
- The README is readable on GitHub without external assets.
- Markdown structure is valid and the file contains no placeholder text.
