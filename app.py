from datetime import date, time

import streamlit as st

from pawpal_system import (
    Category,
    Frequency,
    Owner,
    Pet,
    Priority,
    Scheduler,
    Task,
)

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")
st.markdown(
    "A pet care planner. Add your pets and their tasks, check for time clashes, "
    "and build a day plan that explains why each task is where it is."
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
    day_start = st.time_input("Day starts", value=owner.day_start)
with col2:
    day_end = st.time_input("Day ends", value=owner.day_end)
if day_end > day_start:
    owner.day_start, owner.day_end = day_start, day_end
else:
    st.error("The day must end after it starts. Using the previous window.")

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

scheduler = Scheduler(owner)


def _describe_conflict(conflict, plan) -> str:
    """Say what the clash means for the owner: who keeps the time, who moves, and where to.

    `plan` is a preview from generate_plan(), so the text matches what Generate schedule
    will actually do."""
    if len(conflict.tasks) != 2:
        return conflict.message  # e.g. a task outside the owner's day
    placed = {item.task.id: item for item in plan.scheduled}
    parts = []
    for task in conflict.tasks:
        item = placed.get(task.id)
        who = f"**{task.title}** ({owner.get_pet(task.pet_id).name})"
        if item is None:
            parts.append(f"{who} will not fit and would be skipped")
        elif item.start.time() == task.preferred_time:
            parts.append(f"{who} keeps {task.preferred_time:%H:%M}")
        else:
            parts.append(f"{who} moves to {item.start:%H:%M}")
    wanted = conflict.tasks[1].preferred_time
    return f"Both want {wanted:%H:%M}: " + "; ".join(parts) + "."


st.markdown("### Add a task")

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

    col1, col2 = st.columns(2)
    with col1:
        frequency = st.selectbox(
            "Repeats", list(Frequency), format_func=lambda f: f.value,
            help="Daily and weekly tasks get a new copy when completed.",
        )
    with col2:
        use_time = st.checkbox("Set a preferred time")
        preferred = st.time_input("Preferred time", value=time(9, 0)) if use_time else None
    fixed = st.checkbox(
        "Fixed time (never moved by the scheduler)", disabled=not use_time,
        help="For things like medication. Needs a preferred time.",
    )

    if st.button("Add task"):
        try:
            new_task = Task(
                task_title, category, int(duration), priority,
                preferred_time=preferred, frequency=frequency, fixed=fixed and use_time,
            )
            pet.add_task(new_task)
        except ValueError as err:
            st.error(str(err))
        else:
            st.success(f"Added {new_task.title} for {pet.name}.")
            # Lightweight check: warn about clashes with the new task, never block it.
            preview = scheduler.generate_plan()
            for c in scheduler.find_conflicts():
                if any(t is new_task for t in c.tasks):
                    st.warning(_describe_conflict(c, preview), icon="⚠️")

st.markdown("### Your tasks")


def _complete(task_id: str, pet_id: str) -> None:
    """Button callback: complete a task and remember what happened for the next run."""
    done_pet = owner.get_pet(pet_id)
    title = next(t.title for t in done_pet.tasks if t.id == task_id)
    next_task = done_pet.complete_task(task_id)
    st.session_state.flash = (
        f"Completed {title}. Next one is due {next_task.due_date:%A, %B %d}."
        if next_task
        else f"Completed {title}."
    )


if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

if not owner.get_all_tasks():
    st.caption("No tasks yet.")
else:
    col1, col2 = st.columns(2)
    with col1:
        pet_filter = st.selectbox("Show pet", ["All pets"] + [p.name for p in owner.pets])
    with col2:
        status_filter = st.selectbox("Show status", ["all", "pending", "overdue", "completed"])

    shown = scheduler.sort_by_time(
        scheduler.filter_tasks(
            pet_name=None if pet_filter == "All pets" else pet_filter,
            status=None if status_filter == "all" else status_filter,
        )
    )
    st.caption(f"{len(shown)} task(s), sorted by preferred time (untimed last).")
    if shown:
        today = date.today()
        st.table(
            [
                {
                    "time": f"{t.preferred_time:%H:%M}" if t.preferred_time else "-",
                    "task": t.title,
                    "pet": owner.get_pet(t.pet_id).name,
                    "min": t.duration_minutes,
                    "priority": t.priority.name.lower(),
                    "repeats": t.frequency.value,
                    "fixed": "yes" if t.fixed else "",
                    "status": (
                        "done" if t.completed
                        else "overdue" if t.is_overdue(today)
                        else "due" if t.is_due(today)
                        else f"due {t.due_date:%b %d}"
                    ),
                }
                for t in shown
            ]
        )
        pending = [t for t in shown if not t.completed]
        if pending:
            st.markdown("**Mark a task done**")
            for t in pending:
                st.button(
                    f"✓ {t.title} ({owner.get_pet(t.pet_id).name})",
                    key=f"done-{t.id}",
                    on_click=_complete,
                    args=(t.id, t.pet_id),
                )

st.divider()

st.subheader("Build Schedule")
st.caption("Plans today's due tasks across all of the owner's pets.")

conflicts = scheduler.find_conflicts()
if conflicts:
    preview = scheduler.generate_plan()
    noun = "clash" if len(conflicts) == 1 else "clashes"
    st.warning(
        f"{len(conflicts)} time {noun} found. Nothing is lost: the scheduler "
        "keeps one task at its time (higher priority wins) and moves the other. "
        "Change a task's time if you want a different outcome.",
        icon="⚠️",
    )
    for c in conflicts:
        st.markdown(f"- {_describe_conflict(c, preview)}")
else:
    st.success("No time conflicts among today's due tasks.")

if st.button("Generate schedule"):
    if not owner.get_all_tasks(pending_only=True):
        st.info("Nothing is due today. Add a task or check the task list above.")
        st.session_state.pop("plan", None)
    else:
        st.session_state.plan = scheduler.generate_plan()  # survives the next rerun

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
        st.warning("Some tasks did not fit and were skipped:")
        for skipped in plan.skipped:
            st.write(f"- **{skipped.task.title}**: {skipped.reason}")
