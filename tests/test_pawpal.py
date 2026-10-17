"""Basic behaviour tests for the PawPal+ core classes."""

import pytest

from pawpal_system import Category, Pet, Priority, Task


@pytest.fixture
def task() -> Task:
    return Task("Morning walk", Category.WALK, 30, Priority.HIGH)


@pytest.fixture
def pet() -> Pet:
    return Pet(name="Rex", species="dog")


def test_mark_complete_changes_task_status(task):
    assert task.completed is False  # precondition: starts incomplete

    task.mark_complete()

    assert task.completed is True


def test_adding_task_increases_pet_task_count(pet, task):
    assert len(pet.tasks) == 0  # precondition: no tasks yet

    pet.add_task(task)

    assert len(pet.tasks) == 1
    assert task in pet.tasks


# ---- scheduling improvements -------------------------------------------------

from datetime import date, time, timedelta

from pawpal_system import Frequency, Owner, Scheduler, sort_by_time

DAY = date(2026, 1, 5)


def make(owner_end=time(20, 0)):
    owner = Owner(name="Sam", day_start=time(8, 0), day_end=owner_end)
    pet = Pet(name="Rex", species="dog")
    owner.add_pet(pet)
    return owner, pet


def t(title, minutes=30, prio=Priority.MEDIUM, at=None, **kw):
    return Task(title, Category.OTHER, minutes, prio, preferred_time=at, **kw)


def starts(plan):
    return {i.task.title: i.start.time() for i in plan.scheduled}


# 1. nearest slot
def test_clash_moves_to_nearest_slot_not_earliest():
    owner, pet = make()
    pet.add_task(t("Vet", 60, Priority.HIGH, time(15, 0)))
    pet.add_task(t("Play", 30, Priority.MEDIUM, time(15, 0)))
    plan = Scheduler(owner).generate_plan(DAY)
    assert starts(plan)["Vet"] == time(15, 0)
    assert starts(plan)["Play"] == time(14, 30)  # ends as Vet starts; not 08:00


def test_nearest_slot_can_be_after_preferred_time():
    owner, pet = make()
    pet.add_task(t("Vet", 60, Priority.HIGH, time(15, 0)))
    pet.add_task(t("Play", 30, Priority.MEDIUM, time(15, 30)))
    plan = Scheduler(owner).generate_plan(DAY)
    assert starts(plan)["Play"] == time(16, 0)  # 30 min away vs 60 before


# 2. conflicts
def test_find_conflicts_reports_overlap_across_pets():
    owner, rex = make()
    mia = Pet(name="Mia", species="cat")
    owner.add_pet(mia)
    rex.add_task(t("Walk", 45, at=time(9, 30)))
    mia.add_task(t("Meds", 5, at=time(9, 40)))
    conflicts = Scheduler(owner).find_conflicts(plan_date=DAY)
    assert len(conflicts) == 1
    assert {x.title for x in conflicts[0].tasks} == {"Walk", "Meds"}
    assert "Rex" in conflicts[0].message and "Mia" in conflicts[0].message


def test_find_conflicts_none_when_back_to_back():
    owner, pet = make()
    pet.add_task(t("A", 30, at=time(9, 0)))
    pet.add_task(t("B", 30, at=time(9, 30)))
    assert Scheduler(owner).find_conflicts(plan_date=DAY) == []


def test_find_conflicts_long_task_overlaps_two_later_ones():
    owner, pet = make()
    pet.add_task(t("Long", 120, at=time(9, 0)))
    pet.add_task(t("B", 10, at=time(9, 30)))
    pet.add_task(t("C", 10, at=time(10, 0)))
    assert len(Scheduler(owner).find_conflicts(plan_date=DAY)) == 2


def test_find_conflicts_flags_window_violation():
    owner, pet = make(owner_end=time(12, 0))
    pet.add_task(t("Late", 60, at=time(11, 30)))
    pet.add_task(t("Early", 30, at=time(7, 0)))
    assert len(Scheduler(owner).find_conflicts(plan_date=DAY)) == 2


# 3. filter + sort
def test_filter_by_pet_and_status():
    owner, rex = make()
    mia = Pet(name="Mia", species="cat")
    owner.add_pet(mia)
    done = t("Done")
    done.completed = True
    old = t("Old", due_date=DAY - timedelta(days=2))
    rex.add_task(done)
    rex.add_task(old)
    mia.add_task(t("Feed"))
    assert {x.title for x in owner.filter_tasks(pet_name="mia")} == {"Feed"}
    assert [x.title for x in owner.filter_tasks(status="completed")] == ["Done"]
    assert [x.title for x in owner.filter_tasks(status="overdue", on=DAY)] == ["Old"]
    assert {x.title for x in owner.filter_tasks("Rex", "pending", DAY)} == {"Old"}
    with pytest.raises(ValueError):
        owner.filter_tasks(status="bogus")


def test_sort_by_time_puts_untimed_last_and_breaks_ties_by_priority():
    a = t("a", at=time(10, 0), prio=Priority.LOW)
    b = t("b", at=time(9, 0))
    c = t("c")
    d = t("d", at=time(10, 0), prio=Priority.HIGH)
    assert [x.title for x in sort_by_time([a, b, c, d])] == ["b", "d", "a", "c"]


# 4. recurrence
def test_completing_twice_creates_one_next_occurrence():
    _, pet = make()
    task = t("Feed", frequency=Frequency.DAILY, due_date=DAY)
    pet.add_task(task)
    first = pet.complete_task(task.id, on=DAY)
    second = pet.complete_task(task.id, on=DAY)
    assert first.due_date == DAY + timedelta(days=1)
    assert second is None
    assert len(pet.tasks) == 2


def test_overdue_recurring_task_next_due_counts_from_completion_date():
    task = t("Feed", frequency=Frequency.DAILY, due_date=DAY - timedelta(days=3))
    assert task.mark_complete(on=DAY).due_date == DAY + timedelta(days=1)


def test_weekly_on_time_counts_from_due_date():
    task = t("Groom", frequency=Frequency.WEEKLY, due_date=DAY)
    assert task.mark_complete(on=DAY).due_date == DAY + timedelta(days=7)


def test_once_task_has_no_next_occurrence():
    assert t("x").mark_complete(on=DAY) is None


# 5. skipped carries the task; soft holds; fixed
def test_skipped_carries_task_and_summary_uses_title():
    owner, pet = make(owner_end=time(9, 0))
    pet.add_task(t("Big", 120))
    plan = Scheduler(owner).generate_plan(DAY)
    assert plan.skipped[0].task.title == "Big"
    assert "Big:" in plan.summary()


def test_untimed_high_priority_does_not_block_lower_priority_preferred_time():
    owner, pet = make()
    pet.add_task(t("Groom", 60, Priority.HIGH))
    pet.add_task(t("Vet call", 30, Priority.MEDIUM, time(8, 15)))
    s = starts(Scheduler(owner).generate_plan(DAY))
    assert s["Vet call"] == time(8, 15)
    assert s["Groom"] == time(8, 45)


def test_holds_are_dropped_when_nothing_else_fits():
    owner, pet = make(owner_end=time(9, 0))
    pet.add_task(t("Groom", 60, Priority.HIGH))
    pet.add_task(t("Vet call", 30, Priority.MEDIUM, time(8, 15)))
    plan = Scheduler(owner).generate_plan(DAY)
    assert starts(plan) == {"Groom": time(8, 0)}
    assert plan.skipped[0].task.title == "Vet call"


def test_fixed_task_is_placed_first_and_never_moved():
    owner, pet = make()
    pet.add_task(t("Walk", 60, Priority.HIGH, time(9, 0)))
    pet.add_task(t("Dose", 10, Priority.LOW, time(9, 30), fixed=True))
    plan = Scheduler(owner).generate_plan(DAY)
    assert starts(plan)["Dose"] == time(9, 30)
    assert starts(plan)["Walk"] != time(9, 0)


def test_overlapping_fixed_tasks_second_is_skipped_and_reported():
    owner, pet = make()
    pet.add_task(t("A", 30, Priority.HIGH, time(9, 0), fixed=True))
    pet.add_task(t("B", 30, Priority.HIGH, time(9, 15), fixed=True))
    sched = Scheduler(owner)
    plan = sched.generate_plan(DAY)
    assert len(plan.scheduled) == 1 and len(plan.skipped) == 1
    assert len(sched.find_conflicts(plan_date=DAY)) == 1


def test_fixed_requires_preferred_time():
    with pytest.raises(ValueError):
        t("x", fixed=True)


def test_scheduler_sort_by_time_method():
    owner, pet = make()
    pet.add_task(t("late", at=time(14, 0)))
    pet.add_task(t("none"))
    pet.add_task(t("early", at=time(9, 5)))
    assert [x.title for x in Scheduler(owner).sort_by_time()] == ["early", "late", "none"]


def test_scheduler_filter_tasks_combines_pet_and_status():
    owner, rex = make()
    mia = Pet(name="Mia", species="cat")
    owner.add_pet(mia)
    done = t("Done")
    done.completed = True
    mia.add_task(done)
    mia.add_task(t("Feed"))
    rex.add_task(t("Walk"))
    sched = Scheduler(owner)
    assert [x.title for x in sched.filter_tasks("Mia", "completed")] == ["Done"]
    assert [x.title for x in sched.filter_tasks("Mia", "pending", DAY)] == ["Feed"]
    assert sched.filter_tasks("Nobody") == []


# ---- refactored slot-finding helpers ------------------------------------------

import random
from datetime import datetime

from pawpal_system import _Day, _free_gaps, _is_free


def dt(h, m=0):
    return datetime(2026, 1, 5, h, m)


def test_free_gaps_between_and_around_busy_intervals():
    day = _Day(dt(8), dt(12))
    blocked = [(dt(9), dt(10)), (dt(11), dt(11, 30))]
    assert list(_free_gaps(blocked, day)) == [
        (dt(8), dt(9)), (dt(10), dt(11)), (dt(11, 30), dt(12))
    ]


def test_free_gaps_ignores_overlaps_and_intervals_outside_the_day():
    day = _Day(dt(8), dt(12))
    blocked = [(dt(7), dt(9)), (dt(8, 30), dt(10)), (dt(11, 30), dt(13))]
    assert list(_free_gaps(blocked, day)) == [(dt(10), dt(11, 30))]
    assert list(_free_gaps([(dt(7), dt(13))], day)) == []
    assert list(_free_gaps([], day)) == [(dt(8), dt(12))]


def test_is_free_matches_brute_force_overlap_check():
    rng = random.Random(1)
    for _ in range(300):
        busy, cursor = [], 0
        for _ in range(rng.randint(0, 6)):  # sorted, non-overlapping
            start = cursor + rng.randint(0, 60)
            end = start + rng.randint(5, 60)
            busy.append((dt(8) + timedelta(minutes=start), dt(8) + timedelta(minutes=end)))
            cursor = end
        s = dt(8) + timedelta(minutes=rng.randint(0, 400))
        e = s + timedelta(minutes=rng.randint(5, 90))
        assert _is_free(s, e, busy) == (not any(bs < e and s < be for bs, be in busy))


def test_random_plans_never_overlap_and_stay_inside_the_day():
    rng = random.Random(7)
    for _ in range(200):
        owner, pet = make(owner_end=time(14, 0))
        for n in range(rng.randint(1, 10)):
            at = time(rng.randint(7, 14), rng.choice([0, 15, 30, 45])) if rng.random() < .7 else None
            pet.add_task(t(f"t{n}", rng.choice([10, 20, 45, 90]), rng.choice(list(Priority)), at))
        plan = Scheduler(owner).generate_plan(DAY)
        items = sorted(plan.scheduled, key=lambda i: i.start)
        assert all(a.end <= b.start for a, b in zip(items, items[1:]))
        assert all(dt(8) <= i.start and i.end <= dt(14) for i in items)
        assert len(items) + len(plan.skipped) == len(pet.tasks)
