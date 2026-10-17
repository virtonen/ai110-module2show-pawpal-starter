from datetime import time

import streamlit as st

from pawpal_system import Category, Owner, Pet, Priority, Scheduler, Task

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")

st.markdown(
    """
Welcome to the PawPal+ starter app.

This file is intentionally thin. It gives you a working Streamlit app so you can start quickly,
but **it does not implement the project logic**. Your job is to design the system and build it.

Use this app as your interactive demo once your backend classes/functions exist.
"""
)

with st.expander("Scenario", expanded=True):
    st.markdown(
        """
**PawPal+** is a pet care planning assistant. It helps a pet owner plan care tasks
for their pet(s) based on constraints like time, priority, and preferences.

You will design and implement the scheduling logic and connect it to this Streamlit UI.
"""
    )

with st.expander("What you need to build", expanded=True):
    st.markdown(
        """
At minimum, your system should:
- Represent pet care tasks (what needs to happen, how long it takes, priority)
- Represent the pet and the owner (basic info and preferences)
- Build a plan/schedule for a day that chooses and orders tasks based on constraints
- Explain the plan (why each task was chosen and when it happens)
"""
    )

st.divider()

st.subheader("Owner and Pets")

# The vault: create the Owner once per session, then reuse the same object on every rerun.
if "owner" not in st.session_state:
    st.session_state.owner = Owner(name="Jordan")
owner = st.session_state.owner

owner.name = st.text_input("Owner name", value=owner.name)

col1, col2 = st.columns(2)
with col1:
    pet_name = st.text_input("Pet name", value="Mochi")
with col2:
    species = st.selectbox("Species", ["dog", "cat", "other"])

if st.button("Add pet"):
    if not pet_name.strip():
        st.error("Pet name must not be empty.")
    else:
        owner.add_pet(Pet(name=pet_name.strip(), species=species))

st.markdown("### Tasks")
st.caption("Tasks are stored on the pet they belong to, inside the Owner kept in session state.")

if not owner.pets:
    st.info("Add a pet first, then you can give it tasks.")
else:
    # selectbox returns a copy of object options, so select by id and look up the real Pet.
    pet_id = st.selectbox(
        "Pet",
        [p.id for p in owner.pets],
        format_func=lambda pid: f"{owner.get_pet(pid).name} ({owner.get_pet(pid).species})",
    )
    pet = owner.get_pet(pet_id)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        task_title = st.text_input("Task title", value="Morning walk")
    with col2:
        duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
    with col3:
        priority = st.selectbox("Priority", list(Priority), index=2, format_func=lambda p: p.name.lower())
    with col4:
        category = st.selectbox("Category", list(Category), format_func=lambda c: c.value)

    use_time = st.checkbox("Set a preferred time")
    preferred = st.time_input("Preferred time", value=time(9, 0)) if use_time else None

    if st.button("Add task"):
        try:
            new_task = Task(
                task_title, category, int(duration), priority, preferred_time=preferred
            )
            pet.add_task(new_task)
        except ValueError as err:
            st.error(str(err))
        else:
            # Lightweight check: warn about clashes with the new task, never block it.
            for c in Scheduler(owner).find_conflicts():
                if any(t is new_task for t in c.tasks):
                    st.warning(f"Time conflict: {c.message}")

    for p in owner.pets:
        st.write(f"**{p.name}**")
        if p.tasks:
            st.table(
                [
                    {
                        "title": t.title,
                        "category": t.category.value,
                        "duration_minutes": t.duration_minutes,
                        "priority": t.priority.name.lower(),
                        "preferred": f"{t.preferred_time:%H:%M}" if t.preferred_time else "-",
                    }
                    for t in p.tasks
                ]
            )
        else:
            st.caption("No tasks yet.")

st.divider()

st.subheader("Build Schedule")
st.caption("Plans today's due tasks across all of the owner's pets.")

for c in Scheduler(owner).find_conflicts():
    st.warning(f"Time conflict: {c.message}. The scheduler will move one of them.")

if st.button("Generate schedule"):
    if not owner.get_all_tasks():
        st.info("Add at least one task first.")
    else:
        plan = Scheduler(owner).generate_plan()
        st.session_state.plan = plan  # keep it so it survives the next rerun

plan = st.session_state.get("plan")
if plan is not None:
    st.success(
        f"{len(plan.scheduled)} task(s) scheduled for {plan.plan_date:%A, %B %d}, "
        f"{plan.total_minutes()} of {owner.available_minutes} available minutes."
    )
    if plan.scheduled:
        st.table(
            [
                {
                    "time": f"{item.start:%H:%M}-{item.end:%H:%M}",
                    "task": item.task.title,
                    "pet": item.pet_name,
                    "priority": item.task.priority.name.lower(),
                    "why": item.reason,
                }
                for item in plan.scheduled
            ]
        )
    if plan.skipped:
        st.warning("Skipped:")
        for skipped in plan.skipped:
            st.write(f"- **{skipped.task.title}**: {skipped.reason}")
