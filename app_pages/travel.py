from __future__ import annotations

from datetime import timedelta

import streamlit as st

from householdos.domain.operations import NewTravelPlan, TripStatus
from householdos.ui.runtime import get_runtime


runtime = get_runtime()
repository = runtime.repository
plans = repository.list_travel_plans()

st.title("Travel planning")
st.caption("Track family trips, dates, travelers, transportation, lodging, and confirmations")

with st.expander("Add a trip", icon=":material/add_location_alt:"):
    with st.form("add-travel-plan"):
        title = st.text_input("Trip name", placeholder="Family weekend in Portland")
        date_cols = st.columns(2)
        depart = date_cols[0].date_input("Departure", value=runtime.week_start + timedelta(days=5))
        return_date = date_cols[1].date_input("Return", value=runtime.week_start + timedelta(days=6))
        route_cols = st.columns(2)
        origin = route_cols[0].text_input("Origin", value="Home")
        destination = route_cols[1].text_input("Destination")
        travelers = st.text_input("Travelers", value="Family")
        mode = st.selectbox("Transportation", ["Car", "Flight", "Train", "Other"], accept_new_options=True)
        lodging = st.text_input("Lodging")
        confirmations = st.text_area("Confirmation references", height=70)
        notes = st.text_area("Planning notes", height=90)
        add = st.form_submit_button("Create trip plan", icon=":material/save:", type="primary")
    if add:
        if not title.strip() or not destination.strip():
            st.warning("Trip name and destination are required.")
        elif return_date < depart:
            st.warning("Return date cannot be before departure.")
        else:
            repository.create_travel_plan(
                NewTravelPlan(
                    title=title.strip(), depart_date=depart, return_date=return_date,
                    origin=origin.strip() or "Home", destination=destination.strip(),
                    travelers=travelers.strip() or "Family", transport_mode=mode,
                    lodging=lodging.strip(), confirmation_refs=confirmations.strip(), notes=notes.strip(),
                )
            )
            st.toast("Trip plan created", icon=":material/check_circle:")
            st.rerun()

if not plans:
    st.info("No active trips. Add an idea now and fill in details as they become available.")
for plan in plans:
    with st.container(border=True):
        header = st.container(horizontal=True, vertical_alignment="center")
        header.markdown(f"**{plan.title}**")
        header.badge(plan.status.value, color="green" if plan.status is TripStatus.CONFIRMED else "orange")
        st.write(f"{plan.origin} → {plan.destination}")
        st.caption(
            f"{plan.depart_date.strftime('%b %-d')}–{plan.return_date.strftime('%b %-d, %Y')} · "
            f"{plan.travelers} · {plan.transport_mode}"
        )
        if plan.lodging:
            st.write(f"Lodging: {plan.lodging}")
        if plan.confirmation_refs:
            st.write(f"Confirmations: {plan.confirmation_refs}")
        if plan.notes:
            st.write(plan.notes)
        next_status = {
            TripStatus.IDEA: TripStatus.PLANNING,
            TripStatus.PLANNING: TripStatus.CONFIRMED,
            TripStatus.CONFIRMED: TripStatus.COMPLETED,
        }.get(plan.status)
        if next_status and st.button(
            f"Move to {next_status.value}", key=f"trip-{plan.id}", icon=":material/arrow_forward:"
        ):
            repository.update_travel_status(plan.id, next_status)
            st.rerun()
