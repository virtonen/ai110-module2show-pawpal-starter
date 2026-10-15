"""PawPal+ core system: class skeletons based on diagrams/uml.mmd."""

from __future__ import annotations

from dataclasses import dataclass, field
from dataclasses import replace
from datetime import date, datetime, time, timedelta
from enum import Enum, IntEnum
from uuid import uuid4


def _new_id() -> str:
    return uuid4().hex


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

    def __post_init__(self) -> None:
        """Validate fields (duration_minutes > 0, etc.)."""
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if self.duration_minutes <= 0:
            raise ValueError("duration_minutes must be positive")

    def is_due(self, on: date) -> bool:
        """Return True if the task is not completed and due on or before `on`."""
        return not self.completed and (self.due_date is None or self.due_date <= on)

    def mark_complete(self) -> Task | None:
        """Mark done; for DAILY/WEEKLY tasks return the next occurrence, else None."""
        self.completed = True
        if self.frequency is Frequency.ONCE:
            return None
        step = timedelta(days=1 if self.frequency is Frequency.DAILY else 7)
        return replace(
            self,
            id=_new_id(),
            completed=False,
            due_date=(self.due_date or date.today()) + step,
        )

    def update(self, changes: dict) -> None:
        """Apply a dict of field changes to this task (re-validating them)."""
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
        """Add a task to this pet and set task.pet_id."""
        if any(t.id == task.id for t in self.tasks):
            raise ValueError(f"task id already exists: {task.id}")
        task.pet_id = self.id
        self.tasks.append(task)

    def remove_task(self, task_id: str) -> None:
        """Remove the task with the given id."""
        for i, task in enumerate(self.tasks):
            if task.id == task_id:
                del self.tasks[i]
                return
        raise KeyError(f"no task with id {task_id}")

    def complete_task(self, task_id: str) -> Task | None:
        """Mark a task complete and add its next occurrence if it recurs."""
        task = next((t for t in self.tasks if t.id == task_id), None)
        if task is None:
            raise KeyError(f"no task with id {task_id}")
        next_task = task.mark_complete()
        if next_task is not None:
            self.add_task(next_task)
        return next_task

    def get_pending_tasks(self, on: date | None = None) -> list[Task]:
        """Return tasks that are not completed and due on `on` (default: today)."""
        on = on or date.today()
        return [t for t in self.tasks if t.is_due(on)]


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
        """Add a pet to this owner."""
        if self.get_pet(pet.id) is not None:
            raise ValueError(f"pet id already exists: {pet.id}")
        self.pets.append(pet)

    def remove_pet(self, pet_id: str) -> None:
        """Remove the pet with the given id."""
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
class DailyPlan:
    """The finished plan: scheduled tasks plus skipped tasks and why."""

    plan_date: date
    scheduled: list[ScheduledTask] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)  # task id -> reason

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
            lines.extend(f"  {task_id}: {why}" for task_id, why in self.skipped.items())
        return "\n".join(lines)


class Scheduler:
    """Builds a DailyPlan from an owner's tasks and constraints.

    Strategy: greedy by priority. Tasks are taken in `_sort_tasks` order and each
    is placed in the earliest free slot (honouring preferred_time when possible)
    inside the owner's day window. A task that no longer fits is skipped with a
    reason. Greedy is simple and explainable, but it is not optimal: one long
    high-priority task can crowd out several short ones.
    """

    def __init__(self, owner: Owner) -> None:
        self.owner = owner

    def generate_plan(self, plan_date: date | None = None) -> DailyPlan:
        """Build the plan for `plan_date` (default: today) within the owner's window."""
        plan_date = plan_date or date.today()
        plan = DailyPlan(plan_date=plan_date)
        busy: list[tuple[datetime, datetime]] = []

        # One call to the Owner gathers every pet's due tasks together.
        tasks = self.owner.get_all_tasks(pending_only=True, on=plan_date)
        for task in self._sort_tasks(tasks):
            start = self._find_slot(task, busy, plan_date)
            if start is None:
                plan.skipped[task.id] = self._explain_skipped(task)
                continue
            busy.append((start, start + timedelta(minutes=task.duration_minutes)))
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

    def _sort_tasks(self, tasks: list[Task]) -> list[Task]:
        """Order by priority (high first), then preferred_time (None last),
        then shorter duration, then title, so the order is deterministic."""
        return sorted(
            tasks,
            key=lambda t: (
                -int(t.priority),
                t.preferred_time is None,
                t.preferred_time or time.min,
                t.duration_minutes,
                t.title,
            ),
        )

    def _find_slot(
        self, task: Task, busy: list[tuple[datetime, datetime]], plan_date: date
    ) -> datetime | None:
        """Return the start of the earliest free slot that fits the task (trying
        preferred_time first), or None if it does not fit before day_end."""
        window_start = datetime.combine(plan_date, self.owner.day_start)
        window_end = datetime.combine(plan_date, self.owner.day_end)
        length = timedelta(minutes=task.duration_minutes)

        if task.preferred_time is not None:
            start = datetime.combine(plan_date, task.preferred_time)
            end = start + length
            fits = window_start <= start and end <= window_end
            if fits and not any(s < end and start < e for s, e in busy):
                return start

        cursor = window_start
        for s, e in sorted(busy):
            if s - cursor >= length:
                return cursor
            cursor = max(cursor, e)
        return cursor if window_end - cursor >= length else None

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
