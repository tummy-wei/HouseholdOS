# HouseholdOS capstone demonstration script

Target length: 6–8 minutes.

## 1. State the problem (45 seconds)

Open **Command center**. Explain that household and ministry commitments are fragmented
across school calendars, soccer feeds, recurring activities, documents, email, and group
communications. HouseholdOS turns them into one human-supervised operating plan.

Point out the live week metrics, the planted Student A overlap, and unresolved driver
assignments. Emphasize that the system shows missing information instead of guessing.

## 2. Run the golden workflow (2 minutes)

Open **Weekly brief** and select **Run capstone workflow**.

Narrate the visible roles:

1. Schedule and Commitments normalizes exact events and detects conflicts.
2. Research and Knowledge retrieves authorized household and ministry evidence.
3. Household Planner synthesizes kids activities, church events, groceries, travel,
   house maintenance, and local transportation.
4. Critic and Safety validates completeness, evidence use, feasibility, and approvals.
5. Chief of Staff reconciles the final brief.

Show the seven days, five domain tabs, local transportation, evidence source IDs,
assumptions, and open questions. State that budget is deferred from this release.

## 3. Show live interaction and artifacts (90 seconds)

Open **Ask HouseholdOS** and ask:

> What conflicts do we have, and which drivers are still open on Friday?

Then open **Event briefs**, select a soccer or fellowship-related event, show the generated
one-pager, and download the Markdown artifact.

## 4. Show ministry workflow and approval (90 seconds)

Open **Ministry**. Paste a synthetic pastor email with `From`, `Subject`, and a short body.
Generate the Traditional Chinese LINE draft. Explain that the original meaning and
attribution are preserved and that stale or missing content produces a warning.

Queue the draft, open **Approvals**, inspect the exact destination and payload, and approve
or reject it. State clearly that the capstone records authorization but does not execute a
real LINE send.

## 5. Show observability and evaluation (90 seconds)

Open **Trace and evaluation**. Show the five-role route, ordered run steps, evidence IDs,
durations, critic score, and bounded revision count.

Run the 20-scenario benchmark. Show the pass rate and zero unsafe-action rate. Explain that
the cases cover all five planning domains, planted conflicts, missing travel data, driver
overrides, retrieval failure, sensitivity filtering, grounding, routing, synthesis, and
approval enforcement.

## 6. Close with boundaries and transferability (30 seconds)

Explain that Gmail, live Google Calendar/Sheets, and LINE delivery are adapters, not the
orchestration core. The same supervisor, evidence, planning, validation, trace, and approval
patterns can support an organizational Chief-of-Staff with different domain tools.
