from __future__ import annotations

from datetime import datetime

import streamlit as st

from householdos.infrastructure.external_actions import adapter_readiness, execute_approved_action
from householdos.ui.runtime import get_runtime


runtime = get_runtime()
requests = runtime.repository.list_approval_requests()
readiness = adapter_readiness(runtime.settings)

st.title("Approvals")
st.caption("Review the exact target and payload before authorizing an external action")
st.info("Approval authorizes only the exact payload shown. Delivery is a separate recorded step.", icon=":material/security:")

status_filter = st.segmented_control("Status", ["Proposed", "Approved", "Rejected", "All"], default="Proposed")
if status_filter != "All":
    requests = [item for item in requests if item.status == status_filter]

if not requests:
    st.info("No approval requests in this view.")

for request in requests:
    with st.container(border=True):
        top = st.container(horizontal=True, vertical_alignment="center")
        top.markdown(f"**#{request.id} · {request.action}**")
        top.badge(
            request.status,
            color={"Proposed": "orange", "Approved": "green", "Rejected": "red"}.get(request.status, "gray"),
        )
        st.write(request.target)
        st.caption(f"Tool: {request.tool_name} · Requested: {request.requested_at}")
        if request.execution_status:
            st.caption(f"Execution: {request.execution_status} · {request.execution_detail}")
        with st.expander("Review exact payload", icon=":material/data_object:"):
            st.json(request.payload)
        if request.status == "Proposed":
            with st.container(horizontal=True):
                if st.button("Approve", key=f"approve-{request.id}", icon=":material/check:", type="primary"):
                    runtime.repository.decide_external_action(request.id, True)
                    st.rerun()
                if st.button("Reject", key=f"reject-{request.id}", icon=":material/close:"):
                    runtime.repository.decide_external_action(request.id, False)
                    st.rerun()
        elif request.status == "Approved" and not request.executed_at:
            readiness_key = request.tool_name
            if request.tool_name == "line.send":
                destination_key = str(request.payload.get("destination_key") or "bible")
                readiness_key = f"line.send.{destination_key}"
            configured = readiness.get(readiness_key, False)
            scheduled_for = request.payload.get("scheduled_for")
            due_at = datetime.fromisoformat(str(scheduled_for)) if scheduled_for else None
            not_due = bool(due_at and due_at > datetime.now(due_at.tzinfo))
            if not_due:
                st.info(f"Approved and scheduled for {due_at.strftime('%A, %B %-d at %-I:%M %p')}. Execution unlocks at that time.")
            elif configured:
                if st.button("Execute approved action", key=f"execute-{request.id}", icon=":material/send:", type="primary"):
                    with st.spinner("Sending the exact approved payload…"):
                        result = execute_approved_action(request, runtime.settings)
                        runtime.repository.record_external_execution(request.id, result.success, result.detail)
                    if result.success:
                        st.success(result.detail)
                    else:
                        st.error(result.detail)
                    st.rerun()
            else:
                st.warning("Adapter setup is incomplete. This approved action cannot be executed yet.")
