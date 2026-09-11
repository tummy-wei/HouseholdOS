from __future__ import annotations

import streamlit as st

from householdos.domain.operations import GroceryStatus, NewGroceryItem
from householdos.ui.runtime import get_runtime


runtime = get_runtime()
repository = runtime.repository
items = repository.list_grocery_items(runtime.week_start)

st.title("Grocery planning")
st.caption("Build one weekly list tied to meals, events, and household needs")

metrics = st.columns(3)
metrics[0].metric("Items", len(items), border=True)
metrics[1].metric(
    "Still needed", sum(item.status is GroceryStatus.NEEDED for item in items), border=True
)
metrics[2].metric(
    "Purchased", sum(item.status is GroceryStatus.PURCHASED for item in items), border=True
)

with st.expander("Add grocery item", icon=":material/add_shopping_cart:"):
    with st.form("add-grocery-item"):
        name = st.text_input("Item", placeholder="Milk")
        cols = st.columns(3)
        category = cols[0].selectbox(
            "Category", ["Produce", "Dairy", "Protein", "Pantry", "Frozen", "Household", "Other"]
        )
        quantity = cols[1].text_input("Quantity", value="1")
        assigned_to = cols[2].selectbox(
            "Shopper", ["Unassigned", "Kang", "Jessie"], accept_new_options=True
        )
        needed_for = st.text_input("Needed for", value="Weekly household")
        add = st.form_submit_button("Add to list", icon=":material/add:", type="primary")
    if add:
        if not name.strip():
            st.warning("Enter an item name.")
        else:
            repository.create_grocery_item(
                NewGroceryItem(
                    week_start=runtime.week_start,
                    name=name.strip(),
                    category=category,
                    quantity=quantity.strip() or "1",
                    needed_for=needed_for.strip() or "Weekly household",
                    assigned_to=assigned_to,
                )
            )
            st.toast("Grocery item added", icon=":material/check_circle:")
            st.rerun()

show_purchased = st.toggle("Show purchased items", value=True)
visible = items if show_purchased else [item for item in items if item.status is GroceryStatus.NEEDED]
if not visible:
    st.info("No grocery items in this view. Add the first item above.")
for item in visible:
    with st.container(border=True):
        row = st.container(horizontal=True, vertical_alignment="center")
        row.markdown(f"**{item.name}** · {item.quantity}")
        row.badge(item.category, color="blue")
        row.badge(item.status.value, color="green" if item.status is GroceryStatus.PURCHASED else "orange")
        st.caption(f"For: {item.needed_for} · Shopper: {item.assigned_to}")
        if item.status is GroceryStatus.NEEDED:
            if st.button("Mark purchased", key=f"buy-{item.id}", icon=":material/check:"):
                repository.update_grocery_status(item.id, GroceryStatus.PURCHASED)
                st.rerun()
        elif st.button("Return to list", key=f"unbuy-{item.id}", type="tertiary"):
            repository.update_grocery_status(item.id, GroceryStatus.NEEDED)
            st.rerun()
