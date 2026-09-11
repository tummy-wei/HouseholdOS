# HouseholdOS five-domain acceptance contract

The active release must produce a reviewable result for every domain below. A domain
may return “nothing active” when there is no work, but it must not disappear silently.
Budget planning is deferred.

| Domain | Working behavior | Persisted state | External boundary |
| --- | --- | --- | --- |
| Kids activities | Reads school, soccer, and recurring activities; shows conflicts, arrival buffers, open drivers, cancellations, and weekly overrides | Recurring activities and `schedule_exceptions` | Calendar updates are proposed for approval; local overrides work immediately |
| Church events | Drafts fellowship, online-prayer, Sunday-forecast, and cowork-preparation messages; indexes Bible materials; creates event one-pagers | Church tasks, ministry drafts, Bible material metadata, approval requests, delivery records, evidence, and run traces | LINE sending and spreadsheet/calendar writes require exact approval; adapters fail closed until configured |
| Groceries | Creates a week-scoped list with category, quantity, purpose, shopper, and Needed/Purchased lifecycle | `grocery_items` | No purchasing or payment action is available |
| Travel | Captures trip dates, route, travelers, transport, lodging, confirmation references, notes, and Idea/Planning/Confirmed/Completed lifecycle | `travel_plans` | Booking and purchasing are unavailable; confirmations are recorded only when entered by a user |
| House maintenance | Creates repair, recurring-care, seasonal, and service tasks with owner, due date, priority, and completion state | `household_tasks` with Maintenance scope | Contractor contact, booking, and payment are not executed |

## Integrated weekly brief

The Chief-of-Staff workflow always returns exactly seven days plus explicit sections for
kids activities, church events, groceries, travel, house maintenance, and local
transportation. The critic rejects a result when a domain section is absent. Evidence,
assumptions, unresolved questions, and approval boundaries remain visible.

## Verification evidence

- `tests/test_schedule_analysis.py` covers conflicts, cancellations, and driver overrides.
- `tests/test_operations.py` covers event one-pagers, household queries, and pastor-email extraction.
- `tests/test_domain_planning.py` covers grocery, travel, and maintenance persistence and lifecycle changes.
- `tests/test_tool_policy.py` confirms unapproved writes fail closed.
- `householdos/evaluation/harness.py` runs 20 deterministic scenarios, including an explicit check for every active domain.
- Streamlit interaction checks create a driver override, church reminder, grocery item,
  trip plan, maintenance task, and complete five-domain weekly brief using temporary databases.

## Deferred scope

- Budget planning and spending limits
- Purchases, payments, bookings, or contractor engagement
- Automatic Gmail, Google Calendar, and LINE production execution
- Background autonomy without a user-initiated run and approval
