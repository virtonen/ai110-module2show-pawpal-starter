# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Implementation summary

The core logic lives in [pawpal_system.py](pawpal_system.py) and follows the diagram in [diagrams/uml.mmd](diagrams/uml.mmd). It runs from the terminal with `python main.py`.

How the classes work together:

- An **Owner** has one or more **Pets** and a daily availability window (for example 08:00 to 12:00).
- Each **Pet** keeps its own list of **Tasks**: a walk, a feeding, a medication. A task has a duration, a priority, an optional preferred time, and can repeat daily or weekly.
- The **Scheduler** takes an owner and asks it for every pet's due tasks in one call (`owner.get_all_tasks`), so it plans for the whole household.
- It sorts those tasks by priority, then tries to give each one its preferred time, falling back to the nearest free slot in the owner's window. Tasks that don't fit are skipped.
- The result is a **DailyPlan**: the scheduled tasks (each with a start and end time and a plain-English reason) and the skipped tasks with the reason they were left out.

The approach is greedy, so it is simple and easy to explain, but not optimal: a long high-priority task can use up time that several short ones needed.

Tests for the core classes and the scheduling features below are in [tests/test_pawpal.py](tests/test_pawpal.py).

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

Output of `python main.py`, which builds one owner with two pets (Rex the dog and Mia the cat) and six tasks, then prints the schedule for today:

```
Today's Schedule for Sam (Friday, October 16)
Available: 08:00-12:00 (240 min), scheduled: 110 min
------------------------------------------------------------
08:00-08:10  Breakfast            Mia   [high]
             high priority; placed at its preferred time
08:30-09:15  Morning walk         Rex   [high]
             high priority; placed at its preferred time
09:30-09:35  Medication           Mia   [high]
             high priority; placed at its preferred time
09:35-10:05  Laser pointer play   Mia   [medium]
             medium priority; preferred time 09:30 was unavailable
11:00-11:20  Brush coat           Rex   [low]
             low priority; placed at its preferred time

Skipped:
  Clean litter box: low priority, but no free 180-minute slot left between 08:00 and 12:00
```

## 🧪 Testing PawPal+

```bash
# Run the full test suite:
pytest

# Run with coverage:
pytest --cov
```

Sample test output:

```
# Paste your pytest output here
```

## 📐 Smarter Scheduling

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Sorting | `Scheduler.sort_by_time()`, `sort_by_time()` | By preferred time, untimed last, then priority |
| Filtering | `Scheduler.filter_tasks()`, `Owner.filter_tasks()` | By pet name and/or status |
| Conflict detection | `Scheduler.find_conflicts()` | Overlapping windows; returns warnings |
| Recurring tasks | `Task.mark_complete()`, `Pet.complete_task()` | Daily and weekly; creates the next occurrence |
| Slot placement | `Scheduler.generate_plan()`, `_find_slot()` | Nearest free slot; fixed tasks never move |

**Sorting.** `Scheduler.sort_by_time(tasks=None)` returns tasks ordered by `preferred_time`. Tasks without one go last. Ties are broken by priority (high first), then title. With no argument it sorts all pending tasks.

**Filtering.** `Scheduler.filter_tasks(pet_name, status, on)` returns tasks for one pet (case-insensitive) and/or one status: `"pending"` (not completed and due on `on`), `"completed"`, or `"overdue"` (not completed, due before `on`). Both filters can be combined, and an unknown status raises `ValueError`. Sorting and filtering compose: `scheduler.sort_by_time(scheduler.filter_tasks("Mia", "pending"))`.

**Conflict detection.** `Scheduler.find_conflicts()` is a lightweight check: it returns a list of `Conflict` objects with a readable `message` and never raises. It compares each task's preferred window (start plus duration), across pets as well as within one pet, because the owner is one person. It sorts by start time and sweeps once, comparing each task with the window that ends latest so far (O(n log n)). It also flags a window outside the owner's day. Tasks that only touch, such as one ending at 10:00 and another starting at 10:00, are not conflicts. `generate_plan()` still resolves the clash by moving the lower-priority task, so the warning tells the owner what moved. The Streamlit app shows these warnings when a task is added and above the schedule button.

**Recurring tasks.** `Task.mark_complete(on=None)` marks a task done. For a `DAILY` or `WEEKLY` task it returns a new copy with a new id, not completed, and due 1 or 7 days after the later of the old due date and the completion date. `Pet.complete_task()` adds that copy to the pet. Completing a task twice does not create a second copy, and a `ONCE` task creates none.

**Slot placement.** `generate_plan()` places `fixed` tasks first at their exact time, then the rest by priority. A task that cannot have its preferred time goes to the free slot nearest to it. Tasks with no preference avoid other tasks' preferred windows when they can. Tasks that do not fit are skipped with a reason (`DailyPlan.skipped` holds `SkippedTask(task, reason)`).

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:

1. <!-- Describe this step -->
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
