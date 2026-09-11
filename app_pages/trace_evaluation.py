from __future__ import annotations

from pathlib import Path

import streamlit as st

from householdos.evaluation.harness import BenchmarkSummary, run_capstone_benchmark
from householdos.ui.runtime import get_runtime


runtime = get_runtime()
root = Path(__file__).resolve().parents[1]

st.title("Trace and evaluation")
st.caption("Observable specialist routing, evidence influence, validation, and repeatable benchmarks")

latest = runtime.repository.latest_capstone_run()
if latest is None:
    st.info("Generate a Weekly brief first to create an agent run trace.")
else:
    request, brief, trace = latest
    trace_cols = st.columns(4)
    trace_cols[0].metric("Steps", len(trace.steps), border=True)
    trace_cols[1].metric("Specialist roles", len(set(trace.route)), border=True)
    trace_cols[2].metric("Critic score", brief.validation.score, border=True)
    trace_cols[3].metric("Revision loops", trace.revision_count, border=True)

    st.subheader("Supervisor route")
    st.markdown(" → ".join(f"`{role.value}`" for role in trace.route))
    st.subheader("Run timeline")
    st.dataframe(
        [
            {
                "Step": step.sequence,
                "Role": step.role.value,
                "Action": step.action,
                "Status": step.status,
                "Duration ms": step.duration_ms,
                "Evidence": ", ".join(step.evidence_refs),
            }
            for step in trace.steps
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(f"Run ID: {trace.run_id} · Request ID: {trace.request_id}")

st.subheader("Capstone benchmark")
st.write(
    "Twenty deterministic scenarios cover all five operating domains plus conflicts, "
    "transportation, retrieval permissions, grounding, routing, and approval safety."
)
if st.button("Run 20-scenario benchmark", icon=":material/science:", type="primary"):
    with st.status("Running benchmark...", expanded=True) as status:
        knowledge_path = root / "data/knowledge_items.json"
        if runtime.settings.demo_mode or not knowledge_path.exists():
            knowledge_path = root / "data/sample_knowledge_items.json"
        result = run_capstone_benchmark(str(knowledge_path))
        runtime.repository.save_evaluation_result(result.name, result.model_dump(mode="json"))
        st.session_state.capstone_benchmark = result.model_dump(mode="json")
        status.update(label="Benchmark complete", state="complete", expanded=False)

stored_result = st.session_state.get("capstone_benchmark")
if stored_result:
    result = BenchmarkSummary.model_validate(stored_result)
    bench_cols = st.columns(3)
    bench_cols[0].metric("Passed", f"{result.passed}/{result.total}", border=True)
    bench_cols[1].metric("Pass rate", f"{result.pass_rate:.0%}", border=True)
    bench_cols[2].metric("Unsafe-action rate", f"{result.unsafe_action_rate:.0%}", border=True)
    st.dataframe(
        [
            {
                "Scenario": item.name,
                "Category": item.category,
                "Result": "Pass" if item.passed else "Fail",
                "Check": item.detail,
            }
            for item in result.results
        ],
        hide_index=True,
        width="stretch",
    )
