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

## Challenge 1: Advanced Song Features

**What task did you give the agent?**

The challenge was "Add Advanced Song Features": give the songs more attributes and use them in the score. I split the job between three agent roles, and I did the git work and the checks myself:

- Agent A built it.
- Agent B reviewed A's work, read-only.
- Agent C fixed B's findings and updated the docs and this log.

**Prompts used:**

- To Agent A (shortened): "Add at least 5 new song attributes to `data/songs.csv` (for example popularity, release decade, detailed mood tags), write the values yourself and say they are invented, and add scoring terms for them. Everything new must be opt-in: a profile without the new keys must score byte for byte as before. Add tests."
- Shared rule for all agents: "Default behavior must stay exactly the same. A regression guard compares the top 5 and the scores of the original 10 profiles and the CLI output of `all` and `adversarial` against saved files. New options are extras. Do not run git add, commit, or reset."
- To Agent B (shortened): "Review A's work read-only. Do not trust A's claims. Hand-compute scores for several songs and compare them with the code. Run a mutation test to see whether the tests really notice a changed weight. List findings as must-fix, should-fix, or nit."
- To Agent C (shortened): "Fix B's findings: add the missing tests, make `load_songs` read decades like a profile does, make blank extension values count as absent, give `UserProfile` the new optional fields. Fix every stale statement in README.md and model_card.md, add the 'Optional Extensions' section, and update this log."

**What did the agent generate or change?**

- `data/songs.csv`: six new columns for all 20 songs, with invented values: `popularity`, `release_decade`, `mood_tags`, `instrumentalness`, `speechiness`, `language`.
- `src/recommender.py`: six new opt-in scoring terms (tags 1.5, decade 1.0, popularity 1.0, instrumentalness 0.5, speechiness 0.5, language 0.5, so at most +5.0), six new defaulted fields on `Song`, and checks in `clean_prefs` for the new profile keys.
- `src/main.py`: `EXTENSION_PROFILES` (four profiles) and the `extensions` command.
- Agent C added six optional fields to `UserProfile`, so the object-style `Recommender` can use the new preferences too.
- `tests/test_recommender.py`: 11 original tests plus 34 new test cases (45 in total by `pytest --collect-only -q`).
- `README.md` (new "Optional Extensions" section and updated facts), `model_card.md`, and this file.

**What did you verify or fix manually?**

- **Guard and tests.** I re-ran the regression guard and `pytest` myself after each stage instead of trusting the agents' reports.
- **A wrong count.** Agent A reported "17 original tests plus 12 new". The real numbers were 11 original tests and 18 new cases (13 new test functions, one of them run six ways). B and I caught it by counting. The docs now use the number from `pytest --collect-only -q`.
- **Agent B's checks.** B hand-computed 7 scores and all matched the code. B also compared the old and new code on 59,840 profile and song pairs, and all results were identical.
- **A test gap found by mutation.** B showed the instrumentalness weight was almost untested, because the only case scored 0. I added cases with partial credit (Focus Flow with target 0.95 gives +0.475, and a speechiness case). Then I changed the weight to 0.6 in a copy of the repo and the new test failed, as it should. The real repo was not mutated.
- **A crash in `load_songs`.** A CSV cell such as "1990s" crashed `load_songs`, and "1994" was kept as 1994. It now uses the same decade parsing as profiles, so both load as 1990, and a blank cell stays empty. I added a test with a temporary CSV.
- **Blank and boolean values.** Blank extension values are now treated as absent, and `True` is rejected for popularity and the other extension numbers. The original keys (energy, valence, genre, mood) behave as before.
- **The object-style API.** `UserProfile` could not express the new preferences. I added the optional fields, and a test checks that `Recommender.recommend` matches `recommend_songs` for an extension profile.
- **Tests for the CLI.** I added tests for `EXTENSION_PROFILES` and for `python -m src.main extensions`.
- **Skipped on purpose.** I did not validate song-side values in the CSV. I wrote the limit in the model card instead. I did not change the CSV for odd tags, such as "melancholic" vs the mood "melancholy", or for the language value "instrumental" that overlaps instrumentalness. I noted both in the model card. These are small and changing data would add risk.
- **Docs.** I searched README.md and model_card.md for old counts, column lists, and the "maximum 8.0" statement, and fixed them.

---

## Design Pattern (SF10)

> Document how AI helped you choose or implement a design pattern.

**Which design pattern did you use?**

<!-- e.g., Strategy, Factory, Observer, etc. -->

**How did AI help you brainstorm or implement it?**

<!-- Describe the conversation or suggestions that led to your decision -->

**How does the pattern appear in your final code?**

<!-- Point to the relevant class or method -->
