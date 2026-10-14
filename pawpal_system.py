"""PawPal+ core system: class skeletons based on diagrams/uml.mmd."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time


@dataclass
class Task:
    """A single pet care activity."""

    id: str
    title: str
    category: str
    duration_minutes: int
    priority: int
    preferred_time: time | None = None
    completed: bool = False

    def mark_complete(self) -> None:
        """Mark this task as done."""
        pass

    def update(self, changes: dict) -> None:
        """Apply a dict of field changes to this task."""
        pass


@dataclass
class Pet:
    """A pet and the care tasks assigned to it."""

    name: str
    species: str
    breed: str = ""
    age: int = 0
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Add a task to this pet."""
        pass

    def remove_task(self, task_id: str) -> None:
        """Remove the task with the given id."""
        pass

    def get_pending_tasks(self) -> list[Task]:
        """Return tasks that are not yet completed."""
        pass


@dataclass
class Owner:
    """The pet owner: profile, daily time budget, and their pets."""

    name: str
    available_minutes: int
    preferences: str = ""
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner."""
        pass

    def remove_pet(self, pet: Pet) -> None:
        """Remove a pet from this owner."""
        pass

    def get_all_tasks(self) -> list[Task]:
        """Return every task across all of this owner's pets."""
        pass


@dataclass
class ScheduledTask:
    """A task placed at a specific time in the plan, with the reason why."""

    task: Task
    start_time: time
    reason: str = ""

    def end_time(self) -> time:
        """Return start_time plus the task's duration."""
        pass


@dataclass
class DailyPlan:
    """The finished plan: scheduled tasks plus skipped tasks and why."""

    plan_date: date
    scheduled: list[ScheduledTask] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)  # task id -> reason

    def total_minutes(self) -> int:
        """Return total scheduled minutes."""
        pass

    def summary(self) -> str:
        """Return a human-readable version of the plan."""
        pass


class Scheduler:
    """Builds a DailyPlan from an owner's tasks and constraints."""

    def __init__(self, owner: Owner) -> None:
        self.owner = owner

    def generate_plan(self) -> DailyPlan:
        """Build today's plan within the owner's available time."""
        pass

    def _sort_tasks(self, tasks: list[Task]) -> list[Task]:
        """Order tasks by priority (and preferred time)."""
        pass

    def _explain_choice(self, task: Task) -> str:
        """Return the reason a task was scheduled or skipped."""
        pass
