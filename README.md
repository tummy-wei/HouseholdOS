# HouseholdOS

HouseholdOS is a local-first household Chief-of-Staff MVP. Its multi-page operating
workspace combines family schedules, parent and church tasks, conversational queries,
event briefs, ministry communication drafts, transportation decisions, and explicit
approval for proposed external actions. An optional assistant uses the OpenAI Agents
SDK while deterministic workflows remain available without an API key.

## What is included

- Read-only ICS ingestion for the two TBCS and two LWFP calendars in `docs/`
- Unified monthly calendar view across school, soccer, recurring activities, and church events
- An editable JSON registry of fourteen recurring activities
- Deterministic timezone normalization, source-aware soccer deduplication, and
  same-person overlap detection
- A transportation board with a 15-minute arrival buffer and intentionally open
  weekly driver assignments
- A persistent parent, household, and church task board with weekly ministry templates
- A live chat window grounded in the selected week's schedule, conflicts, drivers,
  and task list, with an offline fallback for common questions
- Downloadable event one-pagers and editable Traditional Chinese announcement drafts
- Four human-supervised ministry workflows for fellowship, online prayer, Sunday
  forecast, and Bible cowork preparation, with persisted drafts and delivery results
- A searchable Bible-study material index backed by stable Google Drive links and a
  safe handoff contract for a Bible preparation agent
- Approval-gated LINE push and spreadsheet-to-calendar adapters that remain disabled
  until their credentials and destinations are configured
- Persistent date-specific cancellations, time/location changes, and driver overrides
- An approval queue that separates exact authorization from execution and verification
- A five-role capstone workflow with typed specialist outputs, permission-aware
  retrieval, one bounded critic revision, and a persisted run trace
- A complete `WeeklyBrief` contract covering schedule, logistics, meals, groceries,
  kids activities, church events, groceries, travel, house maintenance,
  evidence, assumptions, questions, and approvals
- Twenty repeatable benchmark scenarios with interpretable baseline results
- Network-free unit tests for ingestion, orchestration, retrieval, evaluation,
  persistence, and safety

External write adapters fail closed until explicitly configured. Approval by itself
does **not** execute an action; the administrator performs a separate recorded send or
sync step. Apple Calendar remains read/subscription-only in this release.

## Architecture

The product direction, target five-role architecture, safety invariants, data
contracts, evaluation plan, and incremental roadmap are documented in
[`docs/DESIGN.md`](docs/DESIGN.md).

The administrator procedure for the S&L spreadsheet-to-calendar sync, controlled
helper invitations, iPhone setup, and Apps Script maintenance is documented in
[`docs/ADMIN_SOP_CALENDAR_SYNC.md`](docs/ADMIN_SOP_CALENDAR_SYNC.md).
The approval-gated LINE, Bible-material, and app-initiated calendar workflows are in
[`docs/MINISTRY_OPERATIONS_SOP.md`](docs/MINISTRY_OPERATIONS_SOP.md).

```text
app.py                              Streamlit composition root
app_pages/                          Command center, chat, tasks, briefs, ministry,
                                    approvals, and source settings
householdos/
  domain/models.py                  Typed request, plan, and approval models
  domain/capstone.py                Brief, evidence, handoff, critic, and trace models
  domain/schedule.py                Event, activity, conflict, and transport models
  agents/capstone.py                Supervisor and four specialist roles
  ports/calendar.py                 Read-only calendar source interfaces
  ports/planning.py                 Planner and repository interfaces
  workflows/schedule_analysis.py    Merge, deduplication, exceptions, and validation
  workflows/capstone_weekly.py      Observable five-role golden workflow
  workflows/operations.py           Chat fallback, event brief, and ministry drafts
  workflows/weekly_planning.py      Use-case orchestration
  infrastructure/ics.py             Local ICS normalization
  infrastructure/activities.py      Editable JSON activity source
  infrastructure/openai_planner.py  OpenAI Agents SDK adapter
  infrastructure/openai_assistant.py Grounded conversational agent adapter
  infrastructure/sqlite.py          Plans, exceptions, and approvals
  safety/tool_policy.py             Read/write classification and approval gate
  retrieval/keyword.py              Permission-filtered top-four evidence retrieval
  evaluation/harness.py             Twenty deterministic benchmark scenarios
data/recurring_activities.json      Current recurring activity registry
data/knowledge_items.json           Controlled evidence with provenance metadata
evaluation/baseline_results.json    Repeatable capstone baseline
tests/                              Network-free unit tests
.streamlit/config.toml              Calm, accessible HouseholdOS theme
```

The domain and workflow layers do not import Streamlit or the OpenAI SDK. Exact dates,
overlaps, evidence permissions, scores, and approvals remain deterministic. Optional
conversational generation uses the OpenAI Agents SDK. When an external tool is
introduced, classify it with `ExternalTool`; reads are allowed, while writes must pass
a matching `Approval` and use `ExternalToolPolicy.sdk_needs_approval(...)` as the SDK
approval flag.

SQLite writes are local application persistence, not external actions. A generated
plan is stored only after the agent returns a valid seven-day result.

## Setup

Python 3.11 or newer is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

The weekly brief, conflict detection, transportation board, weekly changes, and
approval queue work without an API key. Export a key only to use the optional AI
planner. The application reads environment variables directly; it does not load
`.env` automatically.

```bash
export OPENAI_API_KEY="your-key"
streamlit run app.py
```

Configuration:

- `OPENAI_API_KEY` — optional; required only for the AI planner tab
- `OPENAI_MODEL` — defaults to `gpt-5.6-sol`
- `HOUSEHOLDOS_DB_PATH` — defaults to `data/householdos.db`

## Tests

Tests use Python's standard library runner and make no API calls:

```bash
python -m unittest discover -v
python -m householdos.evaluation.run
```

## Current data workflow

- Replace the four files in `docs/` with refreshed ICS snapshots when needed.
- Edit `data/recurring_activities.json` for durable recurring-schedule changes.
- Use **Weekly changes** in the app for one-date cancellations, rescheduling,
  location changes, or driver assignments. These overrides are stored in SQLite.
- Select **Queue the matching calendar update for approval** only when an external
  calendar change should eventually be reviewed. The MVP does not execute it.

Parent availability can be added later. Until then, off-site transportation remains
open and visible instead of being guessed.

## Interface

The active product scope is organized around five planning domains:

1. **Kids activities** — school and activity calendars, conflicts, weekly changes,
   arrival buffers, and driver assignments.
2. **Church events** — fellowship reminders, Bible-study teams and preparation,
   pastor-message drafts, read-only Gmail intake, and approval-controlled LINE actions.
3. **Groceries** — a week-scoped, categorized shopping list with quantities,
   purpose, shopper, and purchased state.
4. **Travel** — family trip dates, route, travelers, transportation, lodging,
   confirmation references, notes, and lifecycle status.
5. **House maintenance** — repair, recurring-care, seasonal, and service tasks
   using the shared owner, due-date, priority, and completion lifecycle.

Budget planning is intentionally deferred and is not part of the active weekly brief.

- **Command center** summarizes the week, schedule conflicts, open transportation,
  tasks, approvals, and source readiness.
- **Weekly brief** runs the Chief-of-Staff golden workflow and renders its complete,
  source-grounded, critic-validated output.
- **Ask HouseholdOS** provides a persistent chat for schedule, conflict, driver, task,
  and ministry questions. With no API key it uses deterministic answers.
- **Tasks** manages parent, household, and church work and can load the standard weekly
  ministry checklist.
- **Event briefs** creates a one-page Markdown operating brief and LINE announcement
  draft from any timed event.
- **Ministry** prepares fellowship announcements and extracts a pasted or uploaded
  pastor email into a Traditional Chinese LINE draft.
- **Approvals** records approve/reject decisions for proposed calendar and LINE actions.
- **Trace and evaluation** displays specialist routing, ordered run steps, evidence
  influence, critic results, and the live 20-scenario benchmark.
- **Sources and settings** shows source authority, recurring activities, weekly
  overrides, and agent readiness.

Capstone acceptance evidence is mapped in
[`docs/CAPSTONE_TRACEABILITY.md`](docs/CAPSTONE_TRACEABILITY.md). The reproducible
presentation flow is in [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md). The editable
capstone deck is exported at
[`output/pptx/HouseholdOS_Capstone_Presentation.pptx`](output/pptx/HouseholdOS_Capstone_Presentation.pptx).
The current product behavior and integration boundaries are specified in
[`docs/FIVE_DOMAIN_ACCEPTANCE.md`](docs/FIVE_DOMAIN_ACCEPTANCE.md).

## Safety boundary for future integrations

External integrations should be added as infrastructure adapters, not directly in
the Streamlit page or workflow. Search/list/get operations may be exposed as
read-only tools. Create/update/delete/send/purchase operations must remain unavailable
unless they are individually marked as writes and pause for explicit user approval.

Google Calendar and Google Sheets authentication are intentionally deferred. Add
read-only source adapters first. A later write adapter must consume one exact approved
request, verify the result, and record success or ambiguity without automatic retry.
