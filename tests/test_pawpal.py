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


# ---- edge cases: due filtering, empty states, boundaries ---------------------------

from dataclasses import replace as _replace


def titles(plan):
    return {i.task.title for i in plan.scheduled}


def test_plan_includes_only_due_tasks():
    owner, pet = make()
    done = t("Done")
    done.completed = True
    pet.add_task(done)
    pet.add_task(t("Future", due_date=DAY + timedelta(days=1)))
    pet.add_task(t("Overdue", due_date=DAY - timedelta(days=2)))
    pet.add_task(t("Today", due_date=DAY))
    pet.add_task(t("Whenever"))  # no due_date = due until completed
    plan = Scheduler(owner).generate_plan(DAY)
    assert titles(plan) == {"Overdue", "Today", "Whenever"}
    assert plan.skipped == []  # excluded tasks are not "skipped", just not due


def test_pet_without_tasks_gives_empty_plan():
    owner, _ = make()
    plan = Scheduler(owner).generate_plan(DAY)
    assert plan.scheduled == [] and plan.skipped == []
    assert plan.total_minutes() == 0
    assert Scheduler(owner).find_conflicts(plan_date=DAY) == []
    assert "0 min" in plan.summary()


def test_owner_without_pets_gives_empty_plan():
    plan = Scheduler(Owner(name="Solo")).generate_plan(DAY)
    assert plan.scheduled == [] and plan.skipped == []


def test_all_tasks_completed_gives_empty_plan():
    owner, pet = make()
    for n in range(3):
        task = t(f"t{n}")
        task.completed = True
        pet.add_task(task)
    assert Scheduler(owner).generate_plan(DAY).scheduled == []


def test_task_ending_exactly_at_day_end_is_scheduled():
    owner, pet = make(owner_end=time(9, 0))
    pet.add_task(t("Fits", 60))
    pet.add_task(t("Timed", 30, at=time(8, 30)))  # also ends exactly at 09:00
    plan = Scheduler(owner).generate_plan(DAY)
    assert starts(plan)["Timed"] == time(8, 30)
    assert titles(plan) == {"Timed"}  # Fits no longer fits next to it
    assert [s.task.title for s in plan.skipped] == ["Fits"]


def test_task_exactly_filling_the_day_is_scheduled():
    owner, pet = make(owner_end=time(9, 0))
    pet.add_task(t("Whole", 60))
    plan = Scheduler(owner).generate_plan(DAY)
    assert starts(plan) == {"Whole": time(8, 0)}


def test_task_one_minute_too_long_is_skipped():
    owner, pet = make(owner_end=time(9, 0))
    pet.add_task(t("Whole", 61))
    plan = Scheduler(owner).generate_plan(DAY)
    assert plan.scheduled == [] and len(plan.skipped) == 1


def test_day_window_too_small_for_any_task_skips_everything():
    owner, pet = make(owner_end=time(8, 20))
    pet.add_task(t("A", 30, Priority.HIGH))
    pet.add_task(t("B", 45, at=time(8, 0)))
    plan = Scheduler(owner).generate_plan(DAY)
    assert plan.scheduled == []
    assert len(plan.skipped) == 2


def test_zero_length_or_inverted_day_window_skips_everything():
    for end in (time(8, 0), time(7, 0)):
        owner, pet = make(owner_end=end)
        pet.add_task(t("A", 10))
        plan = Scheduler(owner).generate_plan(DAY)
        assert owner.available_minutes == 0
        assert plan.scheduled == [] and len(plan.skipped) == 1


def test_fixed_task_outside_day_window_is_skipped_not_moved():
    owner, pet = make()
    pet.add_task(t("Night meds", 10, at=time(21, 0), fixed=True))
    plan = Scheduler(owner).generate_plan(DAY)
    assert plan.scheduled == [] and len(plan.skipped) == 1


def test_greedy_high_priority_task_can_crowd_out_several_short_ones():
    # Known limit of the greedy strategy (see Scheduler docstring): skipping the
    # big task would fit both small ones, but priority order places it first.
    owner, pet = make()  # 08:00-20:00 = 720 min
    pet.add_task(t("Big", 700, Priority.HIGH))
    pet.add_task(t("Small1", 30, Priority.MEDIUM))
    pet.add_task(t("Small2", 30, Priority.MEDIUM))
    plan = Scheduler(owner).generate_plan(DAY)
    assert titles(plan) == {"Big"}
    assert {s.task.title for s in plan.skipped} == {"Small1", "Small2"}


# ---- edge cases: ties and determinism -------------------------------------------------


def test_same_time_same_priority_is_deterministic_regardless_of_insertion_order():
    results = []
    for order in (["A", "B", "C"], ["C", "B", "A"], ["B", "C", "A"]):
        owner, pet = make()
        for name in order:
            pet.add_task(t(name, 30, Priority.MEDIUM, time(9, 0)))
        results.append(starts(Scheduler(owner).generate_plan(DAY)))
    assert results[0] == results[1] == results[2]
    assert results[0]["A"] == time(9, 0)  # title breaks the tie
    assert len(set(results[0].values())) == 3  # no two share a start


def test_sort_by_time_exact_ties_are_ordered_by_priority_then_title():
    a = t("b", at=time(9, 0), prio=Priority.MEDIUM)
    b = t("a", at=time(9, 0), prio=Priority.MEDIUM)
    c = t("z", at=time(9, 0), prio=Priority.HIGH)
    assert [x.title for x in sort_by_time([a, b, c])] == ["z", "a", "b"]
    assert [x.title for x in sort_by_time([c, b, a])] == ["z", "a", "b"]


def test_sort_by_time_empty_list_and_does_not_mutate_input():
    assert sort_by_time([]) == []
    items = [t("late", at=time(15, 0)), t("early", at=time(7, 0))]
    sort_by_time(items)
    assert [x.title for x in items] == ["late", "early"]


def test_generate_plan_twice_gives_same_result_and_does_not_mutate_tasks():
    owner, pet = make()
    pet.add_task(t("A", 30, Priority.HIGH, time(9, 0)))
    pet.add_task(t("B", 30, Priority.LOW, time(9, 0)))
    pet.add_task(t("C", 20, Priority.MEDIUM, due_date=DAY - timedelta(days=1)))
    before = [_replace(x) for x in pet.tasks]
    sched = Scheduler(owner)
    first, second = sched.generate_plan(DAY), sched.generate_plan(DAY)
    assert starts(first) == starts(second)
    assert pet.tasks == before


# ---- edge cases: recurrence ---------------------------------------------------------------


def test_recurring_task_without_due_date_reappears_on_the_next_day_only():
    owner, pet = make()
    task = t("Feed", frequency=Frequency.DAILY)  # due_date=None
    pet.add_task(task)
    pet.complete_task(task.id, on=DAY)
    sched = Scheduler(owner)
    assert titles(sched.generate_plan(DAY)) == set()  # done today, next not due yet
    assert titles(sched.generate_plan(DAY + timedelta(days=1))) == {"Feed"}
    assert titles(sched.generate_plan(DAY + timedelta(days=5))) == {"Feed"}  # stays due


def test_uncompleted_recurring_task_without_due_date_is_in_every_plan():
    owner, pet = make()
    pet.add_task(t("Feed", frequency=Frequency.DAILY))
    sched = Scheduler(owner)
    for offset in range(3):
        assert titles(sched.generate_plan(DAY + timedelta(days=offset))) == {"Feed"}


def test_daily_recurrence_across_leap_day_and_year_end():
    leap = t("Feed", frequency=Frequency.DAILY, due_date=date(2028, 2, 28))
    assert leap.mark_complete(on=date(2028, 2, 28)).due_date == date(2028, 2, 29)
    nonleap = t("Feed", frequency=Frequency.DAILY, due_date=date(2027, 2, 28))
    assert nonleap.mark_complete(on=date(2027, 2, 28)).due_date == date(2027, 3, 1)
    newyear = t("Feed", frequency=Frequency.DAILY, due_date=date(2026, 12, 31))
    assert newyear.mark_complete(on=date(2026, 12, 31)).due_date == date(2027, 1, 1)
    weekly = t("Groom", frequency=Frequency.WEEKLY, due_date=date(2026, 12, 28))
    assert weekly.mark_complete(on=date(2026, 12, 28)).due_date == date(2027, 1, 4)


def test_overdue_weekly_task_counts_from_completion_date():
    task = t("Groom", frequency=Frequency.WEEKLY, due_date=DAY - timedelta(days=10))
    assert task.mark_complete(on=DAY).due_date == DAY + timedelta(days=7)


def test_early_completion_keeps_the_schedule_not_the_completion_date():
    task = t("Feed", frequency=Frequency.DAILY, due_date=DAY + timedelta(days=3))
    assert task.mark_complete(on=DAY).due_date == DAY + timedelta(days=4)


def test_next_occurrence_is_a_fresh_copy_with_the_same_details():
    _, pet = make()
    task = t("Meds", 5, Priority.HIGH, time(9, 0), frequency=Frequency.DAILY,
             due_date=DAY, fixed=True)
    pet.add_task(task)
    nxt = pet.complete_task(task.id, on=DAY)
    assert nxt is not task and nxt.id != task.id
    assert nxt.pet_id == pet.id and nxt in pet.tasks
    assert nxt.completed is False and task.completed is True
    assert (nxt.title, nxt.duration_minutes, nxt.priority, nxt.preferred_time,
            nxt.frequency, nxt.fixed) == (task.title, 5, Priority.HIGH, time(9, 0),
                                          Frequency.DAILY, True)


def test_completing_recurring_task_keeps_exactly_one_pending_copy():
    _, pet = make()
    task = t("Feed", frequency=Frequency.DAILY, due_date=DAY)
    pet.add_task(task)
    day = DAY
    for _ in range(5):
        current = next(x for x in pet.tasks if not x.completed)
        pet.complete_task(current.id, on=day)
        day += timedelta(days=1)
        assert len([x for x in pet.tasks if not x.completed]) == 1
    assert len(pet.tasks) == 6


# ---- edge cases: bad input is rejected and leaves data unchanged -------------------------


@pytest.mark.parametrize("title", ["", "   ", "\n\t"])
def test_empty_title_is_rejected(title):
    with pytest.raises(ValueError):
        Task(title, Category.OTHER, 10, Priority.LOW)


@pytest.mark.parametrize("minutes", [0, -1, -60])
def test_non_positive_duration_is_rejected(minutes):
    with pytest.raises(ValueError):
        Task("x", Category.OTHER, minutes, Priority.LOW)


def test_update_applies_valid_changes():
    task = t("Walk", 30)
    task.update({"title": "Long walk", "duration_minutes": 60, "priority": Priority.HIGH})
    assert (task.title, task.duration_minutes, task.priority) == (
        "Long walk", 60, Priority.HIGH)


def test_update_rolls_back_every_field_when_one_is_invalid():
    task = t("Walk", 30, Priority.LOW)
    with pytest.raises(ValueError):
        task.update({"title": "New", "priority": Priority.HIGH, "duration_minutes": 0})
    assert (task.title, task.priority, task.duration_minutes) == ("Walk", Priority.LOW, 30)


def test_update_rolls_back_when_fixed_has_no_preferred_time():
    task = t("Walk")
    with pytest.raises(ValueError):
        task.update({"fixed": True})
    assert task.fixed is False


def test_update_rejects_empty_title_and_keeps_old_one():
    task = t("Walk")
    with pytest.raises(ValueError):
        task.update({"title": "  "})
    assert task.title == "Walk"


@pytest.mark.parametrize("changes", [{"id": "new"}, {"pet_id": "new"}, {"nope": 1}])
def test_update_refuses_protected_and_unknown_fields_without_partial_changes(changes):
    task = t("Walk")
    original_id, original_pet = task.id, task.pet_id
    with pytest.raises(ValueError):
        task.update({"title": "Changed", **changes})
    assert task.title == "Walk"  # the valid part was not applied either
    assert (task.id, task.pet_id) == (original_id, original_pet)


def test_add_task_rejects_duplicate_id_and_leaves_pet_unchanged():
    _, pet = make()
    task = t("A")
    pet.add_task(task)
    clone = _replace(t("B"), id=task.id)
    with pytest.raises(ValueError):
        pet.add_task(clone)
    assert pet.tasks == [task]
    assert clone.pet_id == ""  # not claimed by the pet


def test_add_task_sets_pet_id():
    _, pet = make()
    task = t("A")
    pet.add_task(task)
    assert task.pet_id == pet.id


def test_remove_task_removes_only_that_task_and_missing_id_raises():
    _, pet = make()
    a, b = t("A"), t("B")
    pet.add_task(a)
    pet.add_task(b)
    pet.remove_task(a.id)
    assert pet.tasks == [b]
    with pytest.raises(KeyError):
        pet.remove_task(a.id)  # already gone
    assert pet.tasks == [b]


def test_complete_task_with_missing_id_raises_and_changes_nothing():
    _, pet = make()
    task = t("A", frequency=Frequency.DAILY)
    pet.add_task(task)
    with pytest.raises(KeyError):
        pet.complete_task("no-such-id", on=DAY)
    assert task.completed is False and len(pet.tasks) == 1


def test_complete_task_cannot_complete_another_pets_task():
    owner, rex = make()
    mia = Pet(name="Mia", species="cat")
    owner.add_pet(mia)
    task = t("Walk")
    rex.add_task(task)
    with pytest.raises(KeyError):
        mia.complete_task(task.id, on=DAY)
    assert task.completed is False


def test_owner_rejects_duplicate_pet_and_missing_pet_removal():
    owner, pet = make()
    with pytest.raises(ValueError):
        owner.add_pet(pet)
    assert owner.pets == [pet]
    with pytest.raises(KeyError):
        owner.remove_pet("no-such-id")


# ---- happy path: end to end ---------------------------------------------------------------


def test_end_to_end_two_pets_complete_and_replan():
    owner, rex = make()
    mia = Pet(name="Mia", species="cat")
    owner.add_pet(mia)
    walk = t("Walk", 30, Priority.HIGH, time(9, 0), frequency=Frequency.DAILY, due_date=DAY)
    feed = t("Feed", 10, Priority.HIGH, time(9, 0), frequency=Frequency.DAILY, due_date=DAY)
    vet = t("Vet", 60, Priority.MEDIUM, time(14, 0), due_date=DAY)
    rex.add_task(walk)
    mia.add_task(feed)
    rex.add_task(vet)
    sched = Scheduler(owner)

    plan = sched.generate_plan(DAY)
    assert titles(plan) == {"Walk", "Feed", "Vet"}
    assert [i.start for i in plan.scheduled] == sorted(i.start for i in plan.scheduled)
    assert len(sched.find_conflicts(plan_date=DAY)) == 1  # Walk and Feed overlap
    assert {i.pet_name for i in plan.scheduled} == {"Rex", "Mia"}

    rex.complete_task(walk.id, on=DAY)
    assert titles(sched.generate_plan(DAY)) == {"Feed", "Vet"}
    tomorrow = sched.generate_plan(DAY + timedelta(days=1))
    assert titles(tomorrow) == {"Walk", "Feed", "Vet"}  # Feed/Vet still pending
    assert [x.title for x in owner.filter_tasks("Rex", "completed")] == ["Walk"]


# ---- conflict detection: exact duplicate times ---------------------------------------------


def test_find_conflicts_flags_two_tasks_at_the_exact_same_time():
    owner, pet = make()
    pet.add_task(t("Walk", 30, at=time(9, 0)))
    pet.add_task(t("Feed", 30, at=time(9, 0)))
    conflicts = Scheduler(owner).find_conflicts(plan_date=DAY)
    assert len(conflicts) == 1
    assert {x.title for x in conflicts[0].tasks} == {"Walk", "Feed"}
    assert "09:00" in conflicts[0].message


def test_find_conflicts_flags_same_time_across_different_pets():
    owner, rex = make()
    mia = Pet(name="Mia", species="cat")
    owner.add_pet(mia)
    rex.add_task(t("Walk", 20, at=time(9, 0)))
    mia.add_task(t("Meds", 5, at=time(9, 0)))
    conflicts = Scheduler(owner).find_conflicts(plan_date=DAY)
    assert len(conflicts) == 1
    assert "Rex" in conflicts[0].message and "Mia" in conflicts[0].message


def test_find_conflicts_three_tasks_at_one_time_gives_two_reports():
    owner, pet = make()
    for name in ("A", "B", "C"):
        pet.add_task(t(name, 30, at=time(9, 0)))
    assert len(Scheduler(owner).find_conflicts(plan_date=DAY)) == 2


def test_find_conflicts_ignores_untimed_completed_and_not_yet_due_tasks():
    owner, pet = make()
    done = t("Done", 30, at=time(9, 0))
    done.completed = True
    pet.add_task(done)
    pet.add_task(t("Future", 30, at=time(9, 0), due_date=DAY + timedelta(days=1)))
    pet.add_task(t("Untimed1", 30))
    pet.add_task(t("Untimed2", 30))
    pet.add_task(t("Real", 30, at=time(9, 0)))
    assert Scheduler(owner).find_conflicts(plan_date=DAY) == []


def test_duplicate_times_are_flagged_and_the_plan_still_has_no_overlap():
    owner, pet = make()
    pet.add_task(t("Walk", 30, Priority.HIGH, time(9, 0)))
    pet.add_task(t("Feed", 30, Priority.LOW, time(9, 0)))
    sched = Scheduler(owner)
    assert len(sched.find_conflicts(plan_date=DAY)) == 1
    plan = sched.generate_plan(DAY)
    assert starts(plan)["Walk"] == time(9, 0)  # higher priority keeps the time
    assert starts(plan)["Feed"] != time(9, 0)  # the other was moved, not dropped
    a, b = sorted(plan.scheduled, key=lambda i: i.start)
    assert a.end <= b.start


# ---- next available slot -------------------------------------------------------------------


def test_next_slot_on_an_empty_day_is_the_start_of_the_day():
    owner, _ = make()
    assert Scheduler(owner).next_available_slot(30, DAY) == dt(8)


def test_next_slot_skips_past_planned_tasks():
    owner, pet = make()
    pet.add_task(t("Walk", 60, at=time(8, 0)))
    pet.add_task(t("Vet", 30, at=time(9, 0)))
    assert Scheduler(owner).next_available_slot(30, DAY) == dt(9, 30)


def test_next_slot_uses_a_gap_between_tasks_when_it_is_big_enough():
    owner, pet = make()
    pet.add_task(t("A", 60, at=time(8, 0)))
    pet.add_task(t("B", 60, at=time(10, 0)))
    sched = Scheduler(owner)
    assert sched.next_available_slot(60, DAY) == dt(9)  # gap is exactly 60 min
    assert sched.next_available_slot(61, DAY) == dt(11)  # gap too small, goes after B


def test_next_slot_respects_the_after_time():
    owner, pet = make()
    pet.add_task(t("A", 30, at=time(8, 0)))
    sched = Scheduler(owner)
    assert sched.next_available_slot(30, DAY, after=time(12, 15)) == dt(12, 15)
    assert sched.next_available_slot(30, DAY, after=time(6, 0)) == dt(8, 30)  # clamped to the day


def test_next_slot_may_start_inside_a_gap_after_the_after_time():
    owner, pet = make()
    pet.add_task(t("A", 120, at=time(8, 0)))  # 08:00-10:00
    pet.add_task(t("B", 60, at=time(13, 0)))  # 13:00-14:00
    assert Scheduler(owner).next_available_slot(60, DAY, after=time(11, 0)) == dt(11)


def test_next_slot_slot_may_end_exactly_at_day_end():
    owner, pet = make(owner_end=time(10, 0))
    pet.add_task(t("A", 60, at=time(8, 0)))
    sched = Scheduler(owner)
    assert sched.next_available_slot(60, DAY) == dt(9)
    assert sched.next_available_slot(61, DAY) is None


def test_next_slot_is_none_when_the_day_is_full_or_after_is_too_late():
    owner, pet = make(owner_end=time(9, 0))
    pet.add_task(t("A", 60, at=time(8, 0)))
    sched = Scheduler(owner)
    assert sched.next_available_slot(5, DAY) is None
    owner2, _ = make()
    assert Scheduler(owner2).next_available_slot(30, DAY, after=time(19, 45)) is None


def test_next_slot_accounts_for_tasks_that_were_moved_by_the_planner():
    owner, pet = make()
    pet.add_task(t("Vet", 60, Priority.HIGH, time(9, 0)))
    pet.add_task(t("Play", 30, Priority.LOW, time(9, 0)))  # pushed to 08:30
    # busy: 08:30-09:00 (Play) and 09:00-10:00 (Vet); first free 30 min is 08:00-08:30
    assert Scheduler(owner).next_available_slot(30, DAY) == dt(8)
    assert Scheduler(owner).next_available_slot(60, DAY) == dt(10)


def test_next_slot_ignores_completed_and_future_tasks():
    owner, pet = make()
    done = t("Done", 60, at=time(8, 0))
    done.completed = True
    pet.add_task(done)
    pet.add_task(t("Later", 60, at=time(8, 0), due_date=DAY + timedelta(days=1)))
    assert Scheduler(owner).next_available_slot(60, DAY) == dt(8)


def test_next_slot_returns_a_slot_where_a_new_task_moves_nothing():
    owner, pet = make()
    pet.add_task(t("A", 45, Priority.HIGH, time(9, 0)))
    pet.add_task(t("B", 30, Priority.MEDIUM, time(9, 30)))
    sched = Scheduler(owner)
    before = starts(sched.generate_plan(DAY))
    slot = sched.next_available_slot(40, DAY, after=time(9, 0))
    pet.add_task(t("New", 40, Priority.LOW, slot.time()))
    after = sched.generate_plan(DAY)
    assert starts(after)["New"] == slot.time()
    assert {k: v for k, v in starts(after).items() if k != "New"} == before


@pytest.mark.parametrize("minutes", [0, -5])
def test_next_slot_rejects_non_positive_duration(minutes):
    owner, _ = make()
    with pytest.raises(ValueError):
        Scheduler(owner).next_available_slot(minutes, DAY)


def test_next_slot_does_not_change_any_task():
    owner, pet = make()
    pet.add_task(t("A", 30, Priority.HIGH, time(9, 0)))
    pet.add_task(t("B", 30, Priority.LOW, time(9, 0)))
    snapshot = [_replace(x) for x in pet.tasks]
    Scheduler(owner).next_available_slot(30, DAY)
    assert pet.tasks == snapshot


# ---- persistence: save_to_json / load_from_json ---------------------------------------------

import json


def full_household():
    """An owner whose tasks use every field type: enums, times, dates, flags."""
    owner = Owner(name="Sam Ö", day_start=time(7, 30), day_end=time(21, 15),
                  preferences="no walks before 8")
    rex = Pet(name="Rex", species="dog", breed="Lab", age=4)
    mia = Pet(name="Mia", species="cat")
    owner.add_pet(rex)
    owner.add_pet(mia)
    rex.add_task(Task("Walk", Category.WALK, 45, Priority.HIGH, preferred_time=time(8, 30),
                      frequency=Frequency.DAILY, due_date=DAY))
    rex.add_task(Task("Meds", Category.MEDS, 5, Priority.HIGH, preferred_time=time(9, 0),
                      fixed=True, frequency=Frequency.WEEKLY))
    mia.add_task(Task("Groom", Category.GROOMING, 20, Priority.LOW))
    done = Task("Feed", Category.FEEDING, 10, Priority.MEDIUM, due_date=DAY - timedelta(days=1))
    done.completed = True
    mia.add_task(done)
    return owner


def test_save_then_load_gives_identical_data(tmp_path):
    owner = full_household()
    path = tmp_path / "data.json"
    owner.save_to_json(path)
    loaded = Owner.load_from_json(path)
    assert loaded.to_dict() == owner.to_dict()  # every field of every object
    assert loaded is not owner and loaded.pets[0] is not owner.pets[0]


def test_loaded_objects_have_the_right_types_and_links(tmp_path):
    owner = full_household()
    owner.save_to_json(tmp_path / "data.json")
    loaded = Owner.load_from_json(tmp_path / "data.json")
    rex = loaded.get_pet(owner.pets[0].id)
    walk = next(x for x in rex.tasks if x.title == "Walk")
    assert walk.priority is Priority.HIGH and walk.category is Category.WALK
    assert walk.frequency is Frequency.DAILY
    assert walk.preferred_time == time(8, 30) and walk.due_date == DAY
    assert walk.pet_id == rex.id and loaded.get_pet(walk.pet_id) is rex
    assert next(x for x in rex.tasks if x.title == "Meds").fixed is True
    assert loaded.day_start == time(7, 30) and loaded.day_end == time(21, 15)
    assert loaded.name == "Sam Ö"  # non-ASCII survives


def test_a_loaded_household_plans_exactly_like_the_original(tmp_path):
    owner = full_household()
    owner.save_to_json(tmp_path / "data.json")
    loaded = Owner.load_from_json(tmp_path / "data.json")
    before = Scheduler(owner).generate_plan(DAY)
    after = Scheduler(loaded).generate_plan(DAY)
    assert [(i.task.id, i.start, i.reason) for i in after.scheduled] == [
        (i.task.id, i.start, i.reason) for i in before.scheduled]
    assert [s.task.id for s in after.skipped] == [s.task.id for s in before.skipped]


def test_recurrence_still_works_after_a_save_and_load(tmp_path):
    owner = full_household()
    owner.save_to_json(tmp_path / "data.json")
    loaded = Owner.load_from_json(tmp_path / "data.json")
    rex = loaded.pets[0]
    walk = next(x for x in rex.tasks if x.title == "Walk")
    nxt = rex.complete_task(walk.id, on=DAY)
    assert nxt.due_date == DAY + timedelta(days=1) and nxt.id != walk.id
    loaded.save_to_json(tmp_path / "data.json")  # and it can be saved again
    again = Owner.load_from_json(tmp_path / "data.json")
    assert len(again.pets[0].tasks) == len(rex.tasks)


def test_changes_survive_between_runs(tmp_path):
    path = tmp_path / "data.json"
    owner = Owner(name="Sam")
    owner.save_to_json(path)  # run 1: empty
    run2 = Owner.load_from_json(path)
    pet = Pet(name="Rex", species="dog")
    run2.add_pet(pet)
    pet.add_task(t("Walk", at=time(9, 0)))
    run2.save_to_json(path)
    run3 = Owner.load_from_json(path)  # run 3 sees what run 2 saved
    assert [p.name for p in run3.pets] == ["Rex"]
    assert [x.title for x in run3.pets[0].tasks] == ["Walk"]


def test_empty_owner_and_pet_without_tasks_round_trip(tmp_path):
    owner = Owner(name="Solo")
    owner.save_to_json(tmp_path / "a.json")
    assert Owner.load_from_json(tmp_path / "a.json").pets == []
    owner.add_pet(Pet(name="Rex", species="dog"))
    owner.save_to_json(tmp_path / "b.json")
    assert Owner.load_from_json(tmp_path / "b.json").pets[0].tasks == []


def test_saved_file_is_readable_json_with_a_version(tmp_path):
    path = tmp_path / "data.json"
    full_household().save_to_json(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 1 and data["pets"][0]["tasks"][0]["priority"] == "HIGH"
    assert data["pets"][0]["tasks"][0]["preferred_time"] == "08:30:00"
    assert "\n" in path.read_text()  # indented, so people can read it


def test_saving_overwrites_the_old_file_and_leaves_no_temp_file(tmp_path):
    path = tmp_path / "data.json"
    owner = full_household()
    owner.save_to_json(path)
    owner.name = "Renamed"
    owner.save_to_json(path)
    assert Owner.load_from_json(path).name == "Renamed"
    assert [p.name for p in tmp_path.iterdir()] == ["data.json"]


def test_default_path_is_data_json_in_the_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    full_household().save_to_json()
    assert (tmp_path / "data.json").exists()
    assert Owner.load_from_json().name == "Sam Ö"


def test_loading_a_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        Owner.load_from_json(tmp_path / "nope.json")


@pytest.mark.parametrize("text", ["", "{not json", "[]", "null", '"text"'])
def test_loading_garbage_raises_value_error(tmp_path, text):
    path = tmp_path / "data.json"
    path.write_text(text)
    with pytest.raises(ValueError):
        Owner.load_from_json(path)


def _saved(tmp_path):
    path = tmp_path / "data.json"
    full_household().save_to_json(path)
    return path, json.loads(path.read_text(encoding="utf-8"))


def _write(path, data):
    path.write_text(json.dumps(data))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.pop("version"),
        lambda d: d.update(version=99),
        lambda d: d.pop("pets"),
        lambda d: d.update(day_start="not a time"),
        lambda d: d["pets"][0]["tasks"][0].update(priority="URGENT"),
        lambda d: d["pets"][0]["tasks"][0].update(category="swimming"),
        lambda d: d["pets"][0]["tasks"][0].update(frequency="hourly"),
        lambda d: d["pets"][0]["tasks"][0].update(duration_minutes=0),
        lambda d: d["pets"][0]["tasks"][0].update(duration_minutes="long"),
        lambda d: d["pets"][0]["tasks"][0].update(title=" "),
        lambda d: d["pets"][0]["tasks"][0].update(due_date="2026-13-45"),
        lambda d: d["pets"][0]["tasks"][0].pop("id"),
        lambda d: d["pets"][0]["tasks"][1].update(preferred_time=None),  # fixed needs a time
        lambda d: d["pets"][0]["tasks"].append(dict(d["pets"][0]["tasks"][0])),  # duplicate id
        lambda d: d["pets"].append(dict(d["pets"][0])),  # duplicate pet id
    ],
)
def test_loading_invalid_data_raises_value_error(tmp_path, mutate):
    path, data = _saved(tmp_path)
    mutate(data)
    _write(path, data)
    with pytest.raises(ValueError):
        Owner.load_from_json(path)


def test_a_failed_load_leaves_the_file_untouched(tmp_path):
    path = tmp_path / "data.json"
    path.write_text("{broken")
    with pytest.raises(ValueError):
        Owner.load_from_json(path)
    assert path.read_text() == "{broken"


def test_task_and_pet_round_trip_individually():
    task = t("Walk", 30, Priority.LOW, time(6, 5), frequency=Frequency.WEEKLY,
             due_date=DAY, fixed=True)
    assert Task.from_dict(task.to_dict()) == task
    pet = Pet(name="Rex", species="dog", breed="Lab", age=3)
    pet.add_task(task)
    assert Pet.from_dict(pet.to_dict()).to_dict() == pet.to_dict()
