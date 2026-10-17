# AI Interactions Log

> **Stretch features only.** Only fill in the sections that apply to stretch features you attempted. If you did not attempt a stretch feature, leave its section blank or delete it. This file is not required for the core project.

---

## Agent Workflow (SF7)

> Document your experience using an AI agent (e.g., Cursor Agent, Claude, Copilot) to make multi-step changes autonomously.

**What task did you give the agent?**

I asked the agent to add a third algorithmic capability beyond the basic requirements, to test it, and to document the work. The agent proposed a **next available slot** finder: given a task length, return the earliest start time that fits in the day without moving any existing task. I also asked it to show the feature in the Streamlit app and to bring the README, UML diagram and reflection up to date.

**What did the agent do?**

Files modified:

| File | Change |
|------|--------|
| `pawpal_system.py` | Added `Scheduler.next_available_slot(duration_minutes, plan_date=None, after=None)`. It builds the real plan with `generate_plan`, treats the scheduled tasks as busy, and returns the first free gap with room for the task, starting at or after `after`. It returns `None` when nothing fits and raises `ValueError` for a non-positive duration. It reuses the existing `_free_gaps` and `_Day` helpers. |
| `tests/test_pawpal.py` | Added 13 tests (73 to 86 in total): empty day, gaps between tasks, exact fits, a slot ending at `day_end`, no free slot, `after` handling, tasks moved by the planner, completed and future tasks ignored, bad duration, no mutation, and a test that adding a task at the suggested time moves nothing else. |
| `app.py` | Added a **Suggest a free time** button next to **Add task**. It shows the slot and its end time, or says that nothing is left today. |
| `README.md` | New Features bullet, a row and a paragraph in "Smarter Scheduling", the Demo Walkthrough, and updated test counts and sample test output. |
| `diagrams/uml_final.mmd` | Added `next_available_slot` to `Scheduler`. |
| `reflection.md` | Updated the test count and added the new tests to "What you tested". |
| `ai_interactions.md` | This section. |

Steps it took: read `pawpal_system.py` and the existing tests first, wrote the method, wrote the tests, ran `pytest` (86 passed), ran the app headlessly with Streamlit's `AppTest` to press the new button on an empty day and a day with one task, and then updated the documents.

**What did you have to verify or fix manually?**

- **Corrected during the work:** the first version of the button text used an `__import__('datetime')` shortcut to add minutes to the slot. That worked but was ugly, so it was replaced with a normal `timedelta` import. The documents also still said "73 tests"; the counts and the sample test output were updated.
- **Checked by running it:** the key claim ("a task at the suggested time moves nothing else") has its own test, which adds a task at the suggested slot and compares the plan before and after. In the app, a 240-minute request on a day with a 09:00-09:20 walk correctly returned 09:20, because the 60-minute gap before the walk is too small.
- **Limits I kept in mind:** the finder uses today's plan only (due tasks), it does not reserve the slot, and two people pressing the button would get the same answer.
- **My own review:** I read the method and the tests before keeping them. Add here anything you change by hand.

---

## Prompt Comparison (SF11)

> Compare two different prompts (or two different models) on the same task.

| | Option A | Option B |
|-|----------|----------|
| **Model / tool used** | | |
| **Prompt** | | |
| **Response summary** | | |
| **What was useful** | | |
| **Problems noticed** | | |
| **Decision** | | |

**Which approach did you use in your final implementation and why?**

<!-- Your conclusion -->
