# AI Interactions Log

> **Stretch features only.** Only fill in the sections that apply to stretch features you attempted. If you did not attempt a stretch feature, leave its section blank or delete it. This file is not required for the core project.

---

## Agentic Workflow (SF8)

> Document your experience using an AI agent (e.g., Cursor Agent, Claude, Copilot) to make multi-step changes autonomously.

**What task did you give the agent?**

I used Claude Code as an agent across all six phases to plan, build, test, and document a small content-based music recommender. I gave it one phase step at a time. For bigger or riskier jobs I had it open separate sub-agent sessions, each with a narrow written brief:

- critique my taste profile
- design six "adversarial" profiles and run them against the real code
- explain, from the code, why one song ranked first
- apply a weight-shift experiment (energy doubled, genre halved) and check that the math stayed valid
- find out why two TODOs were still in `recommender.py`, then implement them and check completeness

**Prompts used:**

- "Suggest adversarial or edge-case user profiles... a user with conflicting preferences like energy 0.9 and mood sad."
- "Explain WHY Pulse Garden ranks first based on the current weights. Do the arithmetic term by term, and verify it by actually running `score_song`."
- "Double the importance of energy and halve genre in `recommender.py`... and verify that the math remains valid." (The sub-agent was told not to commit or revert; I reverted it myself.)
- "Open a sub agent to check why there are still two TODO in `recommender.py`, are those logic implemented somewhere else, open another sub agent to implement and check completeness."

**What did the agent generate or change?**

- `src/recommender.py`: `load_songs`, `score_song`, `recommend_songs`, the `Recommender` class methods (thin adapters over the functions), and `clean_prefs`.
- `src/main.py`: named profiles, formatted output, and the `all` and `adversarial` options.
- `data/songs.csv`: 10 added songs.
- `tests/test_recommender.py`: 9 added tests.
- `README.md`, `model_card.md`, and this file.
- Commands run: `pytest`, `python -m src.main`, and scratch simulation scripts that compared weights and profiles.

**What did you verify or fix manually?**

- **Weights.** A simulation overturned the common starting weights (genre 2, mood 1): an intense gym song beat a happy indie-pop song for a happy pop listener.
- **A wrong claim in my own docs.** I had written that labels "cannot easily outvote a very wrong energy level". The extreme-energy profile disproved it, so I corrected the README.
- **Tests that proved nothing.** The starter tests passed only because of list order while two methods were empty stubs. I replaced them with order-independent tests.
- **Sub-agent numbers.** I re-ran every number a sub-agent reported. They matched. One sentence in a report was garbled, so I did not use it.
- **Invented data.** The numbers for the 10 songs I added were AI-written. The model card says they are guesses, not measurements.
- **Stale docs.** Correlations, a "planned" field, and "starter tests" went out of date after changes. I audited and fixed them.
- **The experiment.** After the weight-shift test I reverted the code and confirmed the rankings matched my saved baseline byte for byte.

---

## Design Pattern (SF10)

> Document how AI helped you choose or implement a design pattern.

**Which design pattern did you use?**

<!-- e.g., Strategy, Factory, Observer, etc. -->

**How did AI help you brainstorm or implement it?**

<!-- Describe the conversation or suggestions that led to your decision -->

**How does the pattern appear in your final code?**

<!-- Point to the relevant class or method -->
