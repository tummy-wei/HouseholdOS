# HouseholdOS capstone requirements traceability

This matrix treats the submitted capstone proposal and architecture updates as the
acceptance contract. It distinguishes implemented evidence from outcomes that require
an actual user trial.

## Deliverables

| Capstone deliverable | Implementation evidence | Status |
| --- | --- | --- |
| Working Streamlit prototype | `app.py`, thirteen modules under `app_pages/`, `.streamlit/config.toml` | Implemented |
| Chief-of-Staff plus three to four specialists | `householdos/agents/capstone.py`: supervisor, Schedule, Research, Planner, Critic | Implemented |
| Shared SQLite schema and controlled retrieval | `infrastructure/sqlite.py`, `retrieval/keyword.py`, `data/knowledge_items.json` | Implemented |
| Sample/read-only schedule, document, and research tools | Four ICS readers plus permission-filtered evidence retrieval | Implemented |
| Human approval workflow and audit record | SQLite approval requests separate authorization from execution; configured LINE and Apps Script adapters record success or failure | Implemented with fail-closed adapters |
| Evaluation harness with 15–25 scenarios and baseline | `evaluation/harness.py`, 20 scenarios, `evaluation/baseline_results.json` | Implemented: 20/20 baseline |
| Architecture documentation | `docs/DESIGN.md` and this matrix | Implemented |
| Demonstration script | `docs/DEMO_SCRIPT.md` | Implemented |
| Final presentation | `output/pptx/HouseholdOS_Capstone_Presentation.pptx` and the editable Google Slides source | Implemented |

## Definition of success

| Dimension | Verifiable criterion | Evidence |
| --- | --- | --- |
| Functionality | A request completes through a proposed weekly brief | Weekly brief page and `CapstoneWeeklyPlanningWorkflow` |
| Coordination | Supervisor selects specialists and reconciles outputs | Typed route and run steps displayed on Trace and evaluation |
| Grounding | Material evidence includes source identifiers | `EvidenceItem.source_id`, evidence panel, retrieval scenarios |
| Safety | No consequential external write bypasses approval | `ExternalToolPolicy`, approval queue, safety scenarios |
| Evaluation | Repeatable and interpretable benchmark | `python -m householdos.evaluation.run` |
| User value | Reduced planning effort and improved visibility | Requires weekly user-study responses; prompts remain in `docs/DESIGN.md` |
| Transferability | Maps to an organizational Chief-of-Staff | `docs/DESIGN.md`, Broader Impact section in proposal |

## Initial acceptance checklist

- [x] Application launches locally and displays HouseholdOS.
- [x] A request generates a structured seven-day household brief.
- [x] Supervisor routing is visible in a persisted run trace.
- [x] Four specialist roles contribute to the integrated workflow.
- [x] Calendar data is read without modification.
- [x] Retrieved evidence carries source identifiers, timestamps, owners, domains, and sensitivity.
- [x] SQLite persists confirmed preferences, plans, tasks, exceptions, traces, approvals, and evaluation results.
- [x] External writes are blocked until explicit approval.
- [x] Financial transactions are disabled; budget planning is deferred.
- [x] Twenty benchmark scenarios run from a repeatable harness.
- [x] Kids activities, church events, groceries, travel, and house maintenance each have an actionable UI and persisted workflow.
- [x] Results distinguish routing, retrieval, constraint, transportation, safety, grounding, and synthesis checks.
- [x] README, design, traceability, and demo documentation reproduce the prototype.
- [x] Complete the final presentation artifact.
- [ ] Collect real user-value ratings after privacy review and weekly use.

## Framework decision

The OpenAI Agents SDK remains the only model harness. Deterministic Python owns exact
calendar calculations, source filtering, validation, orchestration state, and approval
enforcement. The capstone does not combine LangChain and CrewAI as overlapping control
planes.
