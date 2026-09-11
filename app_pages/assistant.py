from __future__ import annotations

import streamlit as st

from householdos.infrastructure.openai_assistant import OpenAIHouseholdAssistant
from householdos.ui.runtime import get_runtime, household_context
from householdos.workflows.operations import answer_household_query


runtime = get_runtime()
st.session_state.setdefault("household_chat_messages", [])
messages = st.session_state.household_chat_messages

st.title("Ask HouseholdOS")
mode = "OpenAI agent" if runtime.settings.has_api_key else "Offline schedule assistant"
st.caption(f"Live queries grounded in the selected week · {mode}")

suggestions = {
    "What conflicts do we have?": "What conflicts do we have this week?",
    "Who still needs a driver?": "Which driver assignments are still open?",
    "What happens on Friday?": "What is scheduled on Friday?",
    "Show church tasks": "Show me the open church tasks.",
}
queued_prompt = None
if not messages:
    selected = st.pills(
        "Suggested questions",
        list(suggestions),
        label_visibility="collapsed",
    )
    if selected:
        queued_prompt = suggestions[selected]

for message in messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = queued_prompt or st.chat_input(
    "Ask about schedules, conflicts, drivers, tasks, or ministry preparation",
    submit_mode="disable",
)
if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)
    recent = messages[-8:]
    if runtime.settings.has_api_key:
        try:
            with st.chat_message("assistant"):
                with st.spinner("Checking the household plan..."):
                    response = OpenAIHouseholdAssistant(runtime.settings).answer(
                        prompt, household_context(runtime), recent
                    )
                st.markdown(response)
        except Exception as exc:
            response = answer_household_query(
                prompt, runtime.analysis, runtime.repository.list_tasks()
            )
            with st.chat_message("assistant"):
                st.warning(f"Agent unavailable; using the offline planner. {exc}")
                st.markdown(response)
    else:
        response = answer_household_query(
            prompt, runtime.analysis, runtime.repository.list_tasks()
        )
        with st.chat_message("assistant"):
            st.markdown(response)
    messages.extend(
        [{"role": "user", "content": prompt}, {"role": "assistant", "content": response}]
    )
    st.session_state.household_chat_messages = messages
    if queued_prompt:
        st.rerun()

if messages and st.button("Clear conversation", icon=":material/delete_sweep:", type="tertiary"):
    st.session_state.household_chat_messages = []
    st.rerun()
