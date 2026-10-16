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


def main() -> None:
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
    mia.add_task(Task("Clean litter box", Category.OTHER, 180, Priority.LOW))  # too long

    today = date.today()
    plan = Scheduler(owner).generate_plan(today)

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
        titles = {t.id: t.title for t in owner.get_all_tasks()}
        for task_id, reason in plan.skipped.items():
            print(f"  {titles[task_id]}: {reason}")


if __name__ == "__main__":
    main()
