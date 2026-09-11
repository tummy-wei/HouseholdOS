from __future__ import annotations

from pathlib import Path

import streamlit as st

from householdos.agents.capstone import (
    ChiefOfStaffSupervisor,
    CriticSafetyAgent,
    HouseholdPlanningAgent,
    ResearchKnowledgeAgent,
    ScheduleCommitmentsAgent,
)
from householdos.domain.capstone import CapstonePlanningRequest
from householdos.retrieval.keyword import KeywordKnowledgeRepository
from householdos.ui.runtime import get_runtime
from householdos.workflows.capstone_weekly import CapstoneWeeklyPlanningWorkflow


runtime = get_runtime()
root = Path(__file__).resolve().parents[1]

st.title("Weekly household brief")
st.caption("The capstone golden workflow: request → specialists → critic → reviewable brief")

with st.form("capstone-weekly-request"):
    objective = st.text_input(
        "Objective", value="Plan the family week and ministry preparation"
    )
    priorities_text = st.text_area(
        "Priorities",
        value="Resolve schedule and transportation conflicts\nPrepare Friday fellowship responsibilities",
        height=100,
    )
    constraints_text = st.text_area(
        "Constraints",
        value="Do not assign a parent driver without confirmation\nDo not send messages or edit calendars without approval",
        height=100,
    )
    st.caption(
        "Core domains: kids activities · church events · groceries · travel · house maintenance"
    )
    generate = st.form_submit_button(
        "Run capstone workflow", icon=":material/play_arrow:", type="primary"
    )

if generate:
    request = CapstonePlanningRequest(
        week_start=runtime.week_start,
        objective=objective.strip() or "Plan the household week",
        priorities=[line.strip() for line in priorities_text.splitlines() if line.strip()],
        constraints=[line.strip() for line in constraints_text.splitlines() if line.strip()],
    )
    workflow = CapstoneWeeklyPlanningWorkflow(
        ScheduleCommitmentsAgent(),
        ResearchKnowledgeAgent(
            KeywordKnowledgeRepository(
                root / "data" / (
                    "sample_knowledge_items.json"
                    if runtime.settings.demo_mode or not (root / "data/knowledge_items.json").exists()
                    else "knowledge_items.json"
                )
            )
        ),
        HouseholdPlanningAgent(),
        CriticSafetyAgent(),
        ChiefOfStaffSupervisor(),
        repository=runtime.repository,
    )
    with st.status("Coordinating specialists...", expanded=True) as status:
        st.write("Schedule and Commitments: normalizing events and constraints")
        st.write("Research and Knowledge: retrieving authorized evidence")
        st.write("Household Planner: synthesizing the weekly candidate")
        st.write("Critic and Safety: validating grounding and approvals")
        brief, trace = workflow.run(
            request,
            runtime.analysis,
            runtime.repository.list_tasks(include_done=False),
            runtime.repository.list_preferences(),
            runtime.repository.list_grocery_items(runtime.week_start, include_purchased=False),
            runtime.repository.list_travel_plans(),
        )
        status.update(label="Weekly brief ready", state="complete", expanded=False)
    st.session_state.latest_capstone_run_id = trace.run_id
    st.rerun()

latest = runtime.repository.latest_capstone_run()
if latest is None:
    st.info("Run the workflow to create the first complete weekly brief.")
    st.stop()

request, brief, trace = latest
if request.week_start != runtime.week_start:
    st.warning(
        f"The latest saved brief is for the week of {request.week_start}. Run again for the selected week.",
        icon=":material/date_range:",
    )

header = st.container(horizontal=True, vertical_alignment="center")
header.subheader(brief.title)
header.badge(
    f"Critic {brief.validation.score}/100",
    color="green" if brief.validation.passed else "red",
)
st.write(brief.summary)

st.subheader("Priorities")
for item in brief.priorities:
    st.markdown(f"- {item}")

if brief.schedule_findings:
    st.subheader("Schedule findings")
    for item in brief.schedule_findings:
        st.warning(item, icon=":material/event_busy:" if "overlap" in item else ":material/info:")

st.subheader("Daily operating plan")
for day in brief.days:
    with st.container(border=True):
        st.markdown(f"#### {day.date.strftime('%A, %B %-d')}")
        if day.commitments:
            for item in day.commitments:
                st.markdown(f"- {item}")
        else:
            st.caption("No commitments")
        st.markdown(f"**Dinner:** {day.dinner_plan}")
        for item in day.preparation:
            st.markdown(f"- {item}")

domain_tabs = st.tabs(
    ["Kids activities", "Church events", "Groceries", "Travel", "House maintenance"]
)
for tab, items in zip(
    domain_tabs,
    [
        brief.kids_activity_actions,
        brief.church_actions,
        brief.grocery_list,
        brief.travel_actions,
        brief.maintenance_actions,
    ],
    strict=True,
):
    with tab:
        for item in items:
            st.markdown(f"- {item}")

st.subheader("Local transportation")
for item in brief.logistics:
    st.markdown(f"- {item}")

st.subheader("Evidence")
if brief.evidence:
    for item in brief.evidence:
        with st.container(border=True):
            st.markdown(f"**{item.title}** · `{item.source_id}`")
            st.write(item.excerpt)
            st.caption(f"{item.owner} · {item.timestamp} · {item.sensitivity}")
else:
    st.warning("No supporting evidence was retrieved.")

question_cols = st.columns(2, gap="large")
with question_cols[0]:
    st.subheader("Assumptions")
    for item in brief.assumptions:
        st.markdown(f"- {item}")
with question_cols[1]:
    st.subheader("Open questions")
    for item in brief.open_questions:
        st.markdown(f"- {item}")

st.download_button(
    "Download structured brief",
    data=brief.model_dump_json(indent=2),
    file_name=f"householdos-{brief.days[0].date.isoformat()}.json",
    mime="application/json",
    icon=":material/download:",
)
