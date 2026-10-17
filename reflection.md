# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Identify three core actions a user should be able to perform (e.g., add a pet, schedule a walk, see today's tasks).

1. Enter owner and pet info. The user sets up a profile with the owner's name, the pet's name and species or breed, and any constraints, such as how much time they have available each day.

2. Add and edit care tasks. The user creates tasks like walks, feeding, meds, enrichment and grooming. Each task needs at least a duration and a priority, and the user can change or remove it later.

3. Generate and view a daily plan with an explanation. The app schedules the tasks within the owner's constraints, putting higher-priority tasks first and dropping them. It then shows the plan clearly and explains why it chose that order and what it left out.

- Briefly describe your initial UML design.
- What classes did you include, and what responsibilities did you assign to each?

Initial UML design: four classes. `Owner` holds the profile and daily constraints and owns the pets. `Pet` holds pet info and its tasks. `Task` holds one care activity (duration, priority). `Scheduler` takes an owner and builds a `DailyPlan`, which lists the scheduled tasks, the skipped tasks, and the reasoning for each decision.

**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.

Yes. The design changed after I reviewed the class skeleton. Changes:

- **Task now knows its pet.** `Task` has a `pet_id`, so a plan can say whose task it is. Before, `Owner.get_all_tasks()` returned a list and that link was lost.
- **Ids and identity.** `Pet` and `Owner` got ids and are compared by identity, because dataclass equality on every field made two pets with identical fields equal. Task ids are generated, so they are unique across all pets.
- **Day window instead of a single number.** `Owner` has `day_start` and `day_end`, and `available_minutes` is derived from them. A bare minutes budget could not place a task at a real start time or detect overlaps.
- **Recurring tasks.** `Task` got `frequency` and `due_date`. A single `completed` flag cannot represent a task that's been completed twice.
- **Scheduler details.** `generate_plan` takes a date, a `_find_slot` step handles preferred times and conflicts, and the explanation method is split into scheduled and skipped versions. `ScheduledTask` uses `datetime` so end times cannot wrap past midnight.
- **Smaller cleanups.** Priority, category and frequency are enums, and duration is validated.


---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

The scheduler is greedy by priority: it places tasks one at a time, highest priority first, and never rearranges. When two tasks want overlapping times, the higher-priority one keeps its slot and the other moves to the nearest free slot. It checks overlap using start time plus duration. The cost is that the plan is not optimal. One long high-priority task can take the time that would have fit several short ones, and a moved task can end up away from its preferred time (just like in real life). I accepted this because it is fast, deterministic and easy to explain, and every placement comes with a reason. For a few dozen daily pet tasks, a plan the owner can follow at a glance matters more than the last few saved minutes. `find_conflicts` makes up for the lost preferences by warning the owner which tasks were moved. Tasks marked `fixed` are the exception: they are never moved.

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

I used Claude Sonnet 5.5 for design review and for writing code. I wrote the UML and the class skeleton first, then asked it to review the skeleton for missing relationships and logic bottlenecks. After that I had it implement the four classes, write `main.py`, draft two pytest tests, and add missing docstrings and README text. The most helpful prompt was the review one: asking "what is missing or will bottleneck?" before writing any logic surfaced important problems, like tasks not knowing their pet.

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

Claude's skeleton review suggested adding a pet link, ids, a day window, recurrence, and more. I accepted those design changes, because each one fixed a problem I could see in the skeleton. I did not accept its wording as-is: I cut the long "System design" section it wrote for the README down to a shorter implementation summary, and I reworded its bullets in this reflection to match what I understood. I also kept the greedy scheduler instead of trying for an optimal one. Claude pointed out that a long high-priority task can crowd out several short ones, and I decided to document that limit. Claude also added a `Pet.complete_task` method I had not asked for, so I checked it before keeping it.

To verify the result, I ran `main.py` myself in the terminal and checked the plan by hand: the 09:30 medication kept its slot over the lower-priority play session, and the 3-hour task was skipped with a reason. Claude's two pytest tests passed, and it also broke the code on purpose to show the tests fail when the behavior is wrong. I would trust the tests more once they cover the scheduler itself.

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

With Claude's help I wrote 118 pytest tests in `tests/test_pawpal.py`, grouped around the behaviors where a bug would hurt the owner most:

- **Sorting.** Tasks come back in chronological order, tasks with no time go last, and ties are broken by priority and then title, so the order is the same on every run.
- **Recurrence.** Completing a daily or weekly task creates exactly one new copy, due 1 or 7 days later. I covered overdue and early completion, leap days and year ends. Completing a task twice makes no duplicate, and a one-time task makes none.
- **Conflict detection.** The scheduler flags overlapping times, including two tasks at exactly the same time and tasks for different pets. It ignores completed, untimed and not-yet-due tasks.
- **Plan generation.** Only due tasks are planned. The higher-priority task keeps its time, the other moves to the nearest free slot, and fixed tasks never move. A randomized test checks 200 plans for overlaps and tasks outside the day.
- **Edge cases.** A pet with no tasks, an owner with no pets, a task ending exactly at the end of the day, and a day too short for any task.
- **Next available slot.** The earliest free gap of a given length: empty day, gaps between tasks, exact fits, no free slot, a search start time, and that a task placed at the suggested time moves nothing else.
- **Bad input.** Empty titles, non-positive durations, duplicate or missing ids, and `Task.update` rolling back every field when one value is invalid.

These mattered because the scheduler's output looks plausible even when it is wrong. A plan that double-books the owner, or a missed recurring task, does not crash anything, so only a test would catch it. The `generate_plan` tests with future-dated and completed tasks were the most important ones to add, since a mistake there would put the wrong tasks in the plan without any error.

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

I give it 4 out of 5. All 118 tests pass, and they cover the core rules: plans never overlap or leave the day, priority wins a clash, recurrence dates are right, and bad input is rejected without changing data. The tests did not turn up any bugs in the scheduler itself, so I treat that as good news but not proof, because I did not break the code on purpose to check that the new tests fail when they should.

I stop at 4 because:

- The scheduler is greedy. A test documents that one long high-priority task can crowd out several short ones, but that behavior is a known limit, not a fix.
- The tests cover `pawpal_system.py` only. The Streamlit app has no automated tests in the suite.
- Times are plain local times, with no time zones, daylight saving or tasks that run past midnight.
- I have not measured test coverage.

With more time I would test: tasks that run past midnight and a day window that crosses it; changing the owner's day window after tasks are planned; very large numbers of tasks, to check the speed of the slot search; completing a recurring task from the Streamlit app, to test the UI as well as the logic; and a weekly task completed on different weekdays, to check whether "7 days later" is what an owner expects.

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

The explainable scheduler (every placement and every skip has a reason, and conflict warnings say who moves and where), and the layering between `Owner`, `Scheduler` and the app.

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

- A smarter placement step for the greedy crowding problem.
- The missing edit and delete controls in the UI, plus saving data. Those are real gaps: the backend has `Task.update` and `Pet.remove_task`, but the app can only add and complete tasks. The owner and pets also live only in session state, so a refresh loses them.
- Midnight and time zone handling.
- UI tests and coverage.

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?

Design the structure and rules first, then use AI to challenge them. AI output appears right, so you need something that can verify it in a more robust way, such as running `main.py` and the tests yourself.

**d. Working with the AI coding assistant**

- Which AI coding assistant features were most effective for building your scheduler?

Three things helped most. First, **design review before coding**: asking the assistant to review the UML and class skeleton for gaps. Second, **working directly in the codebase**: it could read `pawpal_system.py`, write many tests at once, run `pytest` and `main.py`, and fix what failed, so I saw results instead of guesses. Third, **keeping the documents consistent with the code**: it compared the README, the UML diagram and the app against the final implementation and listed what was out of date, such as the missing `fixed` field and the new `SkippedTask` and `Conflict` classes. It also checked claims before repeating them, for example that `pytest --cov` would not work here.

- Give one example of an AI suggestion you rejected or modified to keep your system design clean.

The assistant pointed out that the greedy scheduler is not optimal, since one long high-priority task can crowd out several short ones. I did not accept the idea of replacing it with an optimal scheduler. That would have made the placement logic much harder to read and to explain, and the plan's reasons are the point of the app. I kept the greedy approach, added a test that documents the limit, and wrote the limit into the README. In the same spirit, I kept the conflict explanation for the app in `app.py` (it uses a preview plan from `generate_plan`) instead of adding display text to the `Scheduler` class, so the backend stays free of UI wording. I also read the unrequested `Pet.complete_task` method carefully before keeping it, and I trimmed generated README text.

- How did using separate chat sessions for different phases help you stay organized?

I kept the phases apart: design and skeleton, implementation, then testing, the app, and the documents. Each session started from the files as they were, not from a long history of earlier ideas, so the assistant worked from the real code and not from a design I had since changed. A session with one goal also made it easy to check the result against that goal (tests passing, the UI showing the warning, the README matching the code), and a wrong turn in one phase did not bleed into the next. The cost was that I had to re-state context at the start of each session, so the README, the UML file and the tests became the shared memory between them.
