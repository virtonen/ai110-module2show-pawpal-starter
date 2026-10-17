"""PawPal+ core system: class skeletons based on diagrams/uml.mmd."""

from __future__ import annotations

import json
import os
from bisect import bisect_left, insort
from collections.abc import Iterator
from dataclasses import dataclass, field
from dataclasses import replace
from datetime import date, datetime, time, timedelta
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, NamedTuple
from uuid import uuid4


def _new_id() -> str:
    """Return a new unique id (random uuid hex string)."""
    return uuid4().hex


DATA_VERSION = 1  # bump if the saved format changes


class Priority(IntEnum):
    """Task priority. Higher value = more important (HIGH is scheduled first)."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3


class Category(Enum):
    """Kinds of pet care activity."""

    WALK = "walk"
    FEEDING = "feeding"
    MEDS = "meds"
    ENRICHMENT = "enrichment"
    GROOMING = "grooming"
    OTHER = "other"


class Frequency(Enum):
    """How often a task repeats once completed."""

    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass
class Task:
    """A single pet care activity."""

    title: str
    category: Category
    duration_minutes: int
    priority: Priority
    id: str = field(default_factory=_new_id)  # unique across ALL pets
    pet_id: str = ""  # set by Pet.add_task; ties the task back to its pet
    preferred_time: time | None = None
    frequency: Frequency = Frequency.ONCE
    due_date: date | None = None  # None = due whenever not completed
    completed: bool = False
    fixed: bool = False  # True = must happen at preferred_time (never moved)

    def __post_init__(self) -> None:
        """Validate fields (duration_minutes > 0, etc.)."""
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if self.duration_minutes <= 0:
            raise ValueError("duration_minutes must be positive")
        if self.fixed and self.preferred_time is None:
            raise ValueError("a fixed task needs a preferred_time")

    def is_due(self, on: date) -> bool:
        """Return True if the task is not completed and due on or before `on`."""
        return not self.completed and (self.due_date is None or self.due_date <= on)

    def is_overdue(self, on: date) -> bool:
        """Return True if the task is not completed and was due before `on`."""
        return not self.completed and self.due_date is not None and self.due_date < on

    def mark_complete(self, on: date | None = None) -> Task | None:
        """Mark done on `on` (default: today); for DAILY/WEEKLY tasks return the
        next occurrence, else None. Completing an already-completed task is a
        no-op, so it cannot spawn duplicate occurrences. The next due date counts
        from the later of the old due date and `on`, so an overdue recurring task
        does not stay overdue after being completed."""
        if self.completed:
            return None
        self.completed = True
        if self.frequency is Frequency.ONCE:
            return None
        on = on or date.today()
        step = timedelta(days=1 if self.frequency is Frequency.DAILY else 7)
        return replace(
            self,
            id=_new_id(),
            completed=False,
            due_date=max(self.due_date or on, on) + step,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly dict: enums as names or values, times and dates as ISO text."""
        return {
            "id": self.id,
            "pet_id": self.pet_id,
            "title": self.title,
            "category": self.category.value,
            "duration_minutes": self.duration_minutes,
            "priority": self.priority.name,
            "preferred_time": self.preferred_time.isoformat() if self.preferred_time else None,
            "frequency": self.frequency.value,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "completed": self.completed,
            "fixed": self.fixed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        """Rebuild a Task saved by `to_dict`; the constructor re-validates every field.
        Raises ValueError (or KeyError/TypeError) if the data is malformed."""
        preferred = data["preferred_time"]
        due = data["due_date"]
        return cls(
            title=data["title"],
            category=Category(data["category"]),
            duration_minutes=data["duration_minutes"],
            priority=Priority[data["priority"]],
            id=data["id"],
            pet_id=data["pet_id"],
            preferred_time=time.fromisoformat(preferred) if preferred else None,
            frequency=Frequency(data["frequency"]),
            due_date=date.fromisoformat(due) if due else None,
            completed=data["completed"],
            fixed=data["fixed"],
        )

    def update(self, changes: dict) -> None:
        """Apply a dict of field changes; raise ValueError (and keep old values) if invalid."""
        protected = {"id", "pet_id"}
        for key in changes:
            if key in protected or not hasattr(self, key):
                raise ValueError(f"cannot update field: {key}")
        backup = {key: getattr(self, key) for key in changes}
        for key, value in changes.items():
            setattr(self, key, value)
        try:
            self.__post_init__()
        except ValueError:
            for key, value in backup.items():  # roll back on invalid input
                setattr(self, key, value)
            raise


@dataclass(eq=False)  # compare pets by identity/id, not by every field
class Pet:
    """A pet and the care tasks assigned to it."""

    name: str
    species: str
    id: str = field(default_factory=_new_id)
    breed: str = ""
    age: int = 0
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Add a task to this pet and set task.pet_id; raise ValueError on a duplicate id."""
        if any(t.id == task.id for t in self.tasks):
            raise ValueError(f"task id already exists: {task.id}")
        task.pet_id = self.id
        self.tasks.append(task)

    def remove_task(self, task_id: str) -> None:
        """Remove the task with the given id; raise KeyError if there is none."""
        for i, task in enumerate(self.tasks):
            if task.id == task_id:
                del self.tasks[i]
                return
        raise KeyError(f"no task with id {task_id}")

    def complete_task(self, task_id: str, on: date | None = None) -> Task | None:
        """Mark a task complete and add its next occurrence if it recurs."""
        task = next((t for t in self.tasks if t.id == task_id), None)
        if task is None:
            raise KeyError(f"no task with id {task_id}")
        next_task = task.mark_complete(on)
        if next_task is not None:
            self.add_task(next_task)
        return next_task

    def get_pending_tasks(self, on: date | None = None) -> list[Task]:
        """Return tasks that are not completed and due on `on` (default: today)."""
        on = on or date.today()
        return [t for t in self.tasks if t.is_due(on)]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly dict of the pet and all of its tasks."""
        return {
            "id": self.id,
            "name": self.name,
            "species": self.species,
            "breed": self.breed,
            "age": self.age,
            "tasks": [t.to_dict() for t in self.tasks],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Pet:
        """Rebuild a Pet and its tasks saved by `to_dict`. Each task keeps its saved
        id, and `add_task` re-checks for duplicate ids and re-links `pet_id`."""
        pet = cls(
            name=data["name"],
            species=data["species"],
            id=data["id"],
            breed=data["breed"],
            age=data["age"],
        )
        for task_data in data["tasks"]:
            pet.add_task(Task.from_dict(task_data))
        return pet


@dataclass(eq=False)
class Owner:
    """The pet owner: profile, daily availability window, and their pets."""

    name: str
    id: str = field(default_factory=_new_id)
    day_start: time = time(8, 0)  # earliest the owner can start a task
    day_end: time = time(20, 0)  # tasks must finish by this time
    preferences: str = ""
    pets: list[Pet] = field(default_factory=list)

    @property
    def available_minutes(self) -> int:
        """Total minutes between day_start and day_end (single source of truth)."""
        start = datetime.combine(date.min, self.day_start)
        end = datetime.combine(date.min, self.day_end)
        return max(0, int((end - start).total_seconds() // 60))

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner; raise ValueError on a duplicate id."""
        if self.get_pet(pet.id) is not None:
            raise ValueError(f"pet id already exists: {pet.id}")
        self.pets.append(pet)

    def remove_pet(self, pet_id: str) -> None:
        """Remove the pet with the given id; raise KeyError if there is none."""
        pet = self.get_pet(pet_id)
        if pet is None:
            raise KeyError(f"no pet with id {pet_id}")
        self.pets.remove(pet)

    def get_pet(self, pet_id: str) -> Pet | None:
        """Look up a pet by id (used to resolve Task.pet_id)."""
        return next((p for p in self.pets if p.id == pet_id), None)

    def get_all_tasks(
        self, pending_only: bool = False, on: date | None = None
    ) -> list[Task]:
        """Return tasks across all pets; if pending_only, only those due on `on`."""
        tasks: list[Task] = []
        for pet in self.pets:
            tasks.extend(pet.get_pending_tasks(on) if pending_only else pet.tasks)
        return tasks

    def filter_tasks(
        self,
        pet_name: str | None = None,
        status: str | None = None,
        on: date | None = None,
    ) -> list[Task]:
        """Return tasks filtered by pet name (case-insensitive) and/or status.

        status is "pending" (not completed and due on `on`), "completed", or
        "overdue" (not completed, due before `on`). None means no filter."""
        if status not in (None, "pending", "completed", "overdue"):
            raise ValueError(f"unknown status: {status}")
        on = on or date.today()
        wanted = pet_name.strip().lower() if pet_name else None
        checks = {
            None: lambda t: True,
            "pending": lambda t: t.is_due(on),
            "completed": lambda t: t.completed,
            "overdue": lambda t: t.is_overdue(on),
        }
        return [
            task
            for pet in self.pets
            if wanted is None or pet.name.lower() == wanted
            for task in pet.tasks
            if checks[status](task)
        ]


    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly dict of the owner, their pets and every task."""
        return {
            "version": DATA_VERSION,
            "id": self.id,
            "name": self.name,
            "day_start": self.day_start.isoformat(),
            "day_end": self.day_end.isoformat(),
            "preferences": self.preferences,
            "pets": [p.to_dict() for p in self.pets],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Owner:
        """Rebuild an Owner saved by `to_dict`. Raises ValueError if the data is
        malformed, from a newer version, or fails any validation."""
        try:
            if data["version"] != DATA_VERSION:
                raise ValueError(f"unsupported data version: {data['version']}")
            owner = cls(
                name=data["name"],
                id=data["id"],
                day_start=time.fromisoformat(data["day_start"]),
                day_end=time.fromisoformat(data["day_end"]),
                preferences=data["preferences"],
            )
            for pet_data in data["pets"]:
                owner.add_pet(Pet.from_dict(pet_data))
        except (KeyError, TypeError, AttributeError) as err:
            raise ValueError(f"invalid saved data: {err!r}") from err
        return owner

    def save_to_json(self, path: str | Path = "data.json") -> None:
        """Write the owner, pets and tasks to `path` as readable JSON.

        The data goes to a temporary file first and is then moved into place, so a
        crash or a full disk mid-write cannot leave a half-written data file."""
        path = Path(path)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        os.replace(tmp, path)

    @classmethod
    def load_from_json(cls, path: str | Path = "data.json") -> Owner:
        """Read an owner saved by `save_to_json`.

        Raises FileNotFoundError if there is no file yet, and ValueError if the
        file is not valid JSON or does not hold valid PawPal+ data."""
        path = Path(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as err:
            raise ValueError(f"{path.name} is not valid JSON: {err}") from err
        if not isinstance(data, dict):
            raise ValueError(f"{path.name} does not hold a PawPal+ data object")
        return cls.from_dict(data)


def sort_by_time(tasks: list[Task]) -> list[Task]:
    """Order tasks by preferred_time (tasks without one last), then priority
    (high first), then title so the order is deterministic."""
    return sorted(
        tasks,
        key=lambda t: (
            t.preferred_time is None,
            t.preferred_time or time.min,
            -int(t.priority),
            t.title,
        ),
    )


@dataclass
class ScheduledTask:
    """A task placed at a specific time in the plan, with the reason why."""

    task: Task
    pet_name: str
    start: datetime  # datetime, so adding the duration can't wrap past midnight
    reason: str = ""

    @property
    def end(self) -> datetime:
        """Return start plus the task's duration."""
        return self.start + timedelta(minutes=self.task.duration_minutes)


@dataclass
class SkippedTask:
    """A task that could not be scheduled, with the reason."""

    task: Task
    reason: str


@dataclass
class Conflict:
    """A problem with the requested times: tasks that overlap, or a task that
    does not fit the owner's day window."""

    tasks: tuple[Task, ...]
    message: str


@dataclass
class DailyPlan:
    """The finished plan: scheduled tasks plus skipped tasks and why."""

    plan_date: date
    scheduled: list[ScheduledTask] = field(default_factory=list)
    skipped: list[SkippedTask] = field(default_factory=list)

    def total_minutes(self) -> int:
        """Return total scheduled minutes."""
        return sum(item.task.duration_minutes for item in self.scheduled)

    def summary(self) -> str:
        """Return a human-readable version of the plan."""
        lines = [f"Plan for {self.plan_date.isoformat()} ({self.total_minutes()} min)"]
        for item in self.scheduled:
            lines.append(
                f"  {item.start:%H:%M}-{item.end:%H:%M} {item.task.title} "
                f"({item.pet_name}, {item.task.priority.name.lower()}) - {item.reason}"
            )
        if self.skipped:
            lines.append("Skipped:")
            lines.extend(f"  {s.task.title}: {s.reason}" for s in self.skipped)
        return "\n".join(lines)


Interval = tuple[datetime, datetime]  # (start, end)


class _Day(NamedTuple):
    """The owner's availability window on one date."""

    start: datetime
    end: datetime

    @property
    def date(self) -> date:
        """Return the calendar date this window falls on."""
        return self.start.date()


def _free_gaps(blocked: list[Interval], day: _Day) -> Iterator[Interval]:
    """Yield the free (start, end) gaps inside the day; `blocked` must be sorted."""
    cursor = day.start
    for start, end in blocked:
        if cursor >= day.end:
            return
        if start > cursor:
            yield cursor, min(start, day.end)
        cursor = max(cursor, end)
    if cursor < day.end:
        yield cursor, day.end


def _is_free(start: datetime, end: datetime, busy: list[Interval]) -> bool:
    """Return True if [start, end) overlaps nothing in `busy`. `busy` must be
    sorted and non-overlapping, so binary search finds the only interval that
    could clash: the last one that starts before `end`."""
    i = bisect_left(busy, (end, datetime.min))
    return i == 0 or busy[i - 1][1] <= start


class Scheduler:
    """Builds a DailyPlan from an owner's tasks and constraints.

    Strategy: greedy by priority. Fixed tasks are placed first at their exact
    time. The rest are taken in `_sort_tasks` order; each goes at its preferred
    time if free, otherwise in the free slot nearest to it (earliest free slot
    if it has no preference). While searching for such a fallback slot, the
    preferred windows of tasks not yet placed are kept free when possible, so
    a task without a preference does not block a later task's preferred time.
    A task that no longer fits is skipped with a reason. Greedy is simple and
    explainable, but it is not optimal: one long high-priority task can crowd
    out several short ones.
    """

    def __init__(self, owner: Owner) -> None:
        """Create a scheduler that plans for the given owner (and all their pets)."""
        self.owner = owner

    def generate_plan(self, plan_date: date | None = None) -> DailyPlan:
        """Build the plan for `plan_date` (default: today) within the owner's window."""
        plan_date = plan_date or date.today()
        plan = DailyPlan(plan_date=plan_date)
        day = _Day(
            datetime.combine(plan_date, self.owner.day_start),
            datetime.combine(plan_date, self.owner.day_end),
        )
        busy: list[Interval] = []  # kept sorted; placed tasks never overlap

        # One call to the Owner gathers every pet's due tasks together.
        tasks = self.owner.get_all_tasks(pending_only=True, on=plan_date)
        ordered = self._sort_tasks(tasks)
        windows = [
            self._window(t, plan_date) if t.preferred_time is not None else None
            for t in ordered
        ]
        for i, task in enumerate(ordered):
            holds = [w for w in windows[i + 1 :] if w is not None]
            start = self._find_slot(task, busy, holds, day)
            if start is None:
                plan.skipped.append(SkippedTask(task, self._explain_skipped(task)))
                continue
            insort(busy, (start, start + timedelta(minutes=task.duration_minutes)))
            pet = self.owner.get_pet(task.pet_id)
            plan.scheduled.append(
                ScheduledTask(
                    task=task,
                    pet_name=pet.name if pet else "unknown pet",
                    start=start,
                    reason=self._explain_scheduled(task, start),
                )
            )
        plan.scheduled.sort(key=lambda item: item.start)
        return plan

    def find_conflicts(
        self, tasks: list[Task] | None = None, plan_date: date | None = None
    ) -> list[Conflict]:
        """Report problems with tasks' preferred times (default: all pending tasks).

        Two kinds are reported: a preferred window that is not inside the owner's
        day, and preferred windows that overlap each other (the owner is one
        person, so tasks for different pets clash too). Overlaps are found by
        sorting on start time and comparing each task with the one that ends
        latest so far: O(n log n). The scheduler still produces a valid plan; this
        tells the user which preferences it had to move."""
        plan_date = plan_date or date.today()
        if tasks is None:
            tasks = self.owner.get_all_tasks(pending_only=True, on=plan_date)
        window_start = datetime.combine(plan_date, self.owner.day_start)
        window_end = datetime.combine(plan_date, self.owner.day_end)
        conflicts: list[Conflict] = []

        timed = [t for t in tasks if t.preferred_time is not None]
        for t in timed:
            start, end = self._window(t, plan_date)
            if start < window_start or end > window_end:
                conflicts.append(
                    Conflict(
                        (t,),
                        f"{t.title} ({start:%H:%M}-{end:%H:%M}) is outside "
                        f"{self.owner.day_start:%H:%M}-{self.owner.day_end:%H:%M}",
                    )
                )

        timed.sort(key=lambda t: (t.preferred_time, -int(t.priority), t.title))
        latest: Task | None = None
        latest_end: datetime | None = None
        for t in timed:
            start, end = self._window(t, plan_date)
            if latest is not None and start < latest_end:
                conflicts.append(
                    Conflict(
                        (latest, t),
                        f"{latest.title} ({self._pet_name(latest)}) and {t.title} "
                        f"({self._pet_name(t)}) overlap at {start:%H:%M}",
                    )
                )
            if latest_end is None or end > latest_end:
                latest, latest_end = t, end
        return conflicts

    def next_available_slot(
        self,
        duration_minutes: int,
        plan_date: date | None = None,
        after: time | None = None,
    ) -> datetime | None:
        """Return the earliest start for a new task of this length, or None.

        The search runs on the plan `generate_plan` would build for `plan_date`
        (default: today), so the answer already accounts for every due task and
        for tasks that were moved. Only gaps at or after `after` (default: the
        start of the owner's day) are considered, and the slot must end by the
        owner's `day_end`. Adding a task at the returned time does not move any
        existing task, unlike adding it at a time that clashes."""
        if duration_minutes <= 0:
            raise ValueError("duration_minutes must be positive")
        plan_date = plan_date or date.today()
        plan = self.generate_plan(plan_date)
        day = _Day(
            datetime.combine(plan_date, self.owner.day_start),
            datetime.combine(plan_date, self.owner.day_end),
        )
        earliest = max(day.start, datetime.combine(plan_date, after or time.min))
        length = timedelta(minutes=duration_minutes)
        blocked = sorted((item.start, item.end) for item in plan.scheduled)
        for gap_start, gap_end in _free_gaps(blocked, day):
            start = max(gap_start, earliest)
            if gap_end - start >= length:
                return start
        return None

    def sort_by_time(self, tasks: list[Task] | None = None) -> list[Task]:
        """Return tasks (default: all pending tasks) ordered by preferred time.
        See the module-level `sort_by_time` for the ordering rules."""
        if tasks is None:
            tasks = self.owner.get_all_tasks(pending_only=True)
        return sort_by_time(tasks)

    def filter_tasks(
        self,
        pet_name: str | None = None,
        status: str | None = None,
        on: date | None = None,
    ) -> list[Task]:
        """Filter the owner's tasks by pet name and/or status; see `Owner.filter_tasks`."""
        return self.owner.filter_tasks(pet_name, status, on)

    def _pet_name(self, task: Task) -> str:
        """Return the name of the task's pet, or "unknown pet" if it has none."""
        pet = self.owner.get_pet(task.pet_id)
        return pet.name if pet else "unknown pet"

    @staticmethod
    def _window(task: Task, plan_date: date) -> tuple[datetime, datetime]:
        """Return the (start, end) of the task at its preferred time."""
        start = datetime.combine(plan_date, task.preferred_time or time.min)
        return start, start + timedelta(minutes=task.duration_minutes)

    def _sort_tasks(self, tasks: list[Task]) -> list[Task]:
        """Order fixed tasks first, then by priority (high first), then
        preferred_time (None last), then shorter duration, then title, so the
        order is deterministic."""
        return sorted(
            tasks,
            key=lambda t: (
                not t.fixed,
                -int(t.priority),
                t.preferred_time is None,
                t.preferred_time or time.min,
                t.duration_minutes,
                t.title,
            ),
        )

    def _find_slot(
        self, task: Task, busy: list[Interval], holds: list[Interval], day: _Day
    ) -> datetime | None:
        """Return a start time for the task, or None if it does not fit.

        `busy` is sorted; `holds` are other tasks' preferred windows. Tries, in
        order: the preferred time if free (a fixed task stops here); the nearest
        slot that also avoids `holds`; the nearest slot ignoring `holds`."""
        if task.preferred_time is not None:
            start, end = self._window(task, day.date)
            if day.start <= start and end <= day.end and _is_free(start, end, busy):
                return start
            if task.fixed:
                return None

        if holds:
            slot = self._nearest_slot(task, sorted(busy + holds), day)
            if slot is not None:
                return slot
        return self._nearest_slot(task, busy, day)

    @staticmethod
    def _nearest_slot(task: Task, blocked: list[Interval], day: _Day) -> datetime | None:
        """Return the start in a free gap closest to the preferred time (the
        earliest start if there is no preference), or None if no gap fits.
        `blocked` must be sorted."""
        length = timedelta(minutes=task.duration_minutes)
        target = (
            datetime.combine(day.date, task.preferred_time)
            if task.preferred_time is not None
            else day.start
        )
        starts = [
            min(max(target, gap_start), gap_end - length)  # clamp into the gap
            for gap_start, gap_end in _free_gaps(blocked, day)
            if gap_end - gap_start >= length
        ]
        return min(starts, key=lambda c: (abs(c - target), c), default=None)

    def _explain_scheduled(self, task: Task, start: datetime) -> str:
        """Return why the task was placed at `start`."""
        reason = f"{task.priority.name.lower()} priority"
        if task.preferred_time is None:
            return f"{reason}; placed in the earliest free slot"
        if start.time() == task.preferred_time:
            return f"{reason}; placed at its preferred time"
        return f"{reason}; preferred time {task.preferred_time:%H:%M} was unavailable"

    def _explain_skipped(self, task: Task) -> str:
        """Return why the task could not be scheduled."""
        return (
            f"{task.priority.name.lower()} priority, but no free {task.duration_minutes}-minute "
            f"slot left between {self.owner.day_start:%H:%M} and {self.owner.day_end:%H:%M}"
        )
