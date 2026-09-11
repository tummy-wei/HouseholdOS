# HouseholdOS capstone presentation script

Target: 8:30-9:30 at a measured technical presentation pace. The words below are a recording guide, not text to read mechanically. Pause briefly after each slide title and spend about 45 seconds on the optional live demonstration after slide 5.

## Slide 1 - HouseholdOS (0:00-0:50)

Hello. I am Kang Wei, and this is HouseholdOS, an approval-gated AI Chief of Staff for family and ministry operations. I built the project around a real coordination problem in my family and church work. Important commitments are spread across school calendars, soccer feeds, recurring lessons, church spreadsheets, email, and LINE. HouseholdOS brings those sources into one operating view, produces a weekly brief, and keeps people in control of every consequential action. The completed prototype covers five operating domains. Its current automated evidence includes 31 passing unit tests, 20 passing benchmark scenarios, and a zero percent unsafe-action rate in that benchmark. I will explain the problem, system boundary, architecture, design evolution, evaluation, and what remains before production use.

## Slide 2 - The coordination problem (0:50-1:45)

The problem begins with fragmentation. Each source is useful, but none understands the full household plan. Parents still reconcile dates, time zones, travel buffers, changing drivers, volunteer assignments, and communication deadlines. The same issue appears in ministry work. A spreadsheet may contain the correct Bible-study leader, while a public calendar must hide helper details, and a LINE reminder must include the current chapter without exposing irrelevant information. A missed handoff can mean a late pickup, an unprepared leader, a wrong assignment, or an unreviewed message. Ordinary calendars record events. They do not tell us what preparation is due, who must decide, which fact is uncertain, or whether an external action has permission to occur.

## Slide 3 - System goal and operating boundary (1:45-2:35)

The goal is one reviewable weekly brief across kids activities, church events, groceries, travel, and house maintenance. Each domain also has a focused workspace. Success requires factual preservation, conflict detection, visible missing information, actionable tasks, and explicit approval for external writes. The system can draft a LINE announcement, propose a spreadsheet or calendar change, organize a grocery list, and track a trip. It cannot purchase groceries, book travel, hire a contractor, or send a message without the configured approval path. Budget support is deferred. For this capstone, I added synthetic grocery, Portland travel, and maintenance records. They demonstrate the data lifecycles without publishing private household details.

## Slide 4 - Architecture and major components (2:35-3:45)

The architecture follows ports and adapters. Streamlit is the operating console. Read-only sources include four ICS calendar feeds, Gmail, Google Sheets, and manual input. Deterministic Python normalizes dates, expands recurrences, calculates transportation, filters evidence by sensitivity, and enforces tool policy. SQLite stores tasks, exceptions, preferences, weekly briefs, evidence, run traces, ministry drafts, approvals, and delivery outcomes. The agent workflow uses one supervisor plus Schedule, Research, Planner, and Critic specialists with typed Pydantic inputs and outputs. The OpenAI Agents SDK supports model-assisted routing and synthesis, while deterministic fallbacks keep the demo usable without an API key. At the action boundary, Apps Script updates the sheet and synchronizes two Google calendars. The LINE Messaging API sends an approved draft. A Cloudflare Worker receives LINE webhook events and helps identify the destination group.

## Slide 5 - Human-in-the-loop action flow (3:45-4:55)

Human oversight is implemented as application state, not as a reminder inside a prompt. First, the system prepares a draft. Second, the user previews the exact facts and wording. Third, approval binds to the specific tool, destination, and payload. Fourth, the adapter executes only when credentials and scheduling conditions are valid. Finally, the outcome enters an audit record. Approved future actions remain locked until their scheduled time. Missing credentials, a missing destination, a mismatched approval, or an early execution attempt produces a closed failure. This flow protects church communications and calendar mutations while allowing useful automation. In a live demonstration, I would open a fellowship reminder, review the Traditional Chinese draft, approve it, and then show the separate execution and delivery status.

## Slide 6 - Key design decisions (4:55-6:00)

Five design decisions were especially important. Google Sheets remains the church system of record because leader and helper availability changes frequently. Public and Helpers calendars are derived views. Typed Pydantic contracts validate domain state, while deterministic Python owns exact date, permission, and constraint logic. SQLite provides local-first memory with inspectable approvals and traces. I chose the OpenAI Agents SDK as the only model harness instead of combining LangChain and CrewAI control planes. This keeps orchestration understandable. Finally, synthetic data supports reproducibility and safe publication. Across the course checkpoints, these decisions narrowed a broad personal-assistant concept into one testable Chief-of-Staff workflow with explicit boundaries.

## Slide 7 - Evaluation approach and results (6:00-7:10)

Evaluation combines unit tests with a deterministic benchmark. The 31 unit tests cover persistence lifecycles, malformed calendar-duration repair, overlap detection, cancellations, driver overrides, ministry drafting, pastor-email extraction, event one-pagers, permission-filtered retrieval, and fail-closed adapters. All passed on September ninth, 2026. The twenty-scenario benchmark plants known requirements and checks routing, constraints, missing information, transportation, retrieval, grounding, safety, synthesis, and each of the five domains. It passed 20 of 20. The unsafe-action rate was zero because an unapproved LINE send was blocked, while only an exact matching approval could proceed to the adapter. The Critic also returned a completeness score of 100 for the benchmark brief. These figures demonstrate correctness against the current suite. They do not prove production reliability, and the planned longitudinal user study has not yet measured time saved or trust.

## Slide 8 - Public repository and reproducibility (7:10-8:00)

The public repository is available at github dot com slash tummy-wei slash HouseholdOS. Before final publication, I will verify that API tokens, OAuth files, private email content, personal addresses, and live LINE group identifiers are excluded. The repository will include the README and architecture, the Streamlit application, domain models and workflows, sanitized adapters and sample inputs, all 31 tests, the twenty-scenario baseline, setup instructions, and the demonstration guide. A technical reviewer should be able to launch Streamlit, run the tests, rerun the benchmark, inspect the approval policy, and reproduce the synthetic five-domain demonstration.

## Slide 9 - Strengths, limitations, and next steps (8:00-9:05)

HouseholdOS is strongest where agent systems often become difficult to trust: it preserves provenance, uses typed state, keeps exact constraints deterministic, and fails closed at external boundaries. It also connects five practical domains through one weekly brief while retaining focused workspaces. The current limitations are significant. The app runs locally, has no durable background scheduler, uses rule-based calendar logic, and relies mostly on synthetic evaluation shaped by one household. The next steps are a managed deployment with protected secrets, a durable job queue, sandbox integration tests, and a four-week user study. That study should measure planning time, missed commitments, correction rate, and trust. Later work can add semantic retrieval for Bible-study materials, richer route planning, and budget functions after privacy and authorization controls mature. The capstone result is a reusable Chief-of-Staff pattern that coordinates complex work while keeping decisions human-owned. Thank you.

## Recording checklist

- Verify that https://github.com/tummy-wei/HouseholdOS is public and contains the sanitized submission files.
- Record with PowerPoint's Record feature, Google Slides plus Loom, or another screen recorder.
- Use your own voice and show your face only if the course requires it.
- Keep the microphone close, silence notifications, and record at 1080p.
- Export as MP4 and verify that the duration is between 8 and 10 minutes.
