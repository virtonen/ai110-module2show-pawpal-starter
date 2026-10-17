"""Temporary testing ground: build a small household and print today's schedule."""

from datetime import date, time

from pawpal_system import (
    Category,
    Frequency,
    Owner,
    Pet,
    Priority,
    Scheduler,
    Task,
)


def show(label: str, tasks: list[Task]) -> None:
    """Print a one-line-per-task list under a label."""
    print(f"\n{label}:")
    for t in tasks:
        when = f"{t.preferred_time:%H:%M}" if t.preferred_time else "--:--"
        state = "done" if t.completed else "todo"
        print(f"  {when}  {t.title:<20} {t.priority.name.lower():<6} {state}")
    if not tasks:
        print("  (none)")


def main() -> None:
    """Build a small household, demo sorting, filtering and conflicts, print the plan."""
    owner = Owner(name="Sam", day_start=time(8, 0), day_end=time(12, 0))

    rex = Pet(name="Rex", species="dog", breed="Labrador", age=4)
    mia = Pet(name="Mia", species="cat", breed="Tabby", age=2)
    owner.add_pet(rex)
    owner.add_pet(mia)

    rex.add_task(Task("Morning walk", Category.WALK, 45, Priority.HIGH,
                      preferred_time=time(8, 30)))
    rex.add_task(Task("Brush coat", Category.GROOMING, 20, Priority.LOW,
                      preferred_time=time(11, 0)))
    mia.add_task(Task("Breakfast", Category.FEEDING, 10, Priority.HIGH,
                      preferred_time=time(8, 0), frequency=Frequency.DAILY))
    mia.add_task(Task("Medication", Category.MEDS, 5, Priority.HIGH,
                      preferred_time=time(9, 30), frequency=Frequency.DAILY))
    mia.add_task(Task("Laser pointer play", Category.ENRICHMENT, 30, Priority.MEDIUM,
                      preferred_time=time(9, 30)))  # clashes with the medication
    rex.add_task(Task("Training", Category.ENRICHMENT, 20, Priority.MEDIUM,
                      preferred_time=time(9, 40)))  # clashes with Mia's laser play (another pet)
    mia.add_task(Task("Clean litter box", Category.OTHER, 180, Priority.LOW))  # too long

    today = date.today()
    scheduler = Scheduler(owner)

    # Tasks above were added out of time order; show the sorting and filtering.
    show("All tasks, as added", owner.get_all_tasks())
    show("Sorted by time", scheduler.sort_by_time())
    show("Mia's tasks, sorted", scheduler.sort_by_time(scheduler.filter_tasks("Mia")))

    # Complete the recurring Breakfast so there is a completed task and a next one.
    breakfast = next(t for t in mia.tasks if t.title == "Breakfast")
    nxt = mia.complete_task(breakfast.id, on=today)
    print(f"\nCompleted Breakfast; next one is due {nxt.due_date}")
    show("Completed", scheduler.filter_tasks(status="completed"))
    show("Pending today, sorted",
         scheduler.sort_by_time(scheduler.filter_tasks(status="pending", on=today)))
    show("Rex, pending today, sorted",
         scheduler.sort_by_time(scheduler.filter_tasks("Rex", "pending", today)))

    print("\nConflict check:")
    conflicts = scheduler.find_conflicts(plan_date=today)
    for conflict in conflicts:
        print(f"  WARNING: {conflict.message}")
    if not conflicts:
        print("  no conflicts")

    plan = scheduler.generate_plan(today)

    print(f"Today's Schedule for {owner.name} ({today:%A, %B %d})")
    print(f"Available: {owner.day_start:%H:%M}-{owner.day_end:%H:%M} "
          f"({owner.available_minutes} min), scheduled: {plan.total_minutes()} min")
    print("-" * 60)
    for item in plan.scheduled:
        print(f"{item.start:%H:%M}-{item.end:%H:%M}  {item.task.title:<20} "
              f"{item.pet_name:<5} [{item.task.priority.name.lower()}]")
        print(f"             {item.reason}")

    if plan.skipped:
        print("\nSkipped:")
        for skipped in plan.skipped:
            print(f"  {skipped.task.title}: {skipped.reason}")


if __name__ == "__main__":
    main()
