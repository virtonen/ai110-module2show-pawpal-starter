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

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
