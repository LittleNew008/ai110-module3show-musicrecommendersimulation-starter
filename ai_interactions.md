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

## Challenge 2: Multiple Scoring Modes

**What task did you give the agent?**

The challenge was "Create Multiple Scoring Modes": let the user pick between named scoring modes, such as genre-first or energy-focused, and show how the rankings change. I used the same three agent roles as in Challenge 1 and did the git work and the checks myself:

- Agent A built it and weighed several designs first.
- Agent B reviewed A's work, read-only.
- Agent C fixed B's findings and updated the docs and this log.

I prototyped the work on a branch called `experiment/scoring-modes`. After the checks passed, I merged it into `main`.

**Prompts used:**

- To Agent A (shortened): "Add scoring modes (for example genre-first, mood-first, energy-focused) that change the weights, and let the user choose one from the command line. Before you code, brainstorm at least three designs, compare them, and pick one. The default mode must stay byte-for-byte identical to today's output."
- Shared rule for all agents (same as Challenge 1): "Default behavior must stay exactly the same. A regression guard compares the top 5 and the scores of the original 10 profiles and the CLI output of `all` and `adversarial` against saved files. New options are extras. Do not run git add, commit, or reset."
- To Agent B (shortened): "Review A's work read-only. Verify every demo claim by running it. Hand-compute scores in every mode. Run 5 or more mutations on a copy of the repo to see whether the tests notice. Try adding a fifth mode and see what breaks."
- To Agent C (shortened): "Fix B's findings: pin the weight table and the tie-breaking in tests, make the tests count modes from `MODES`, validate `ScoringMode`, and change the `--list-modes` text to 'base max'. Add the Challenge 2 section to the README, update the model card, and fill in this log."

**What did the agent generate or change?**

- `src/recommender.py`: a frozen dataclass `ScoringMode` (four weights, plus the energy curve width and the partial mood credit), a registry `MODES`, `DEFAULT_MODE`, and `resolve_mode`. `score_song`, `recommend_songs` and `Recommender` take an optional `mode`.
- Four modes: `balanced` (the default, the original recipe), `genre-first`, `mood-first` and `energy-focused`. Each one has base weights that add up to 8.0.
- `src/main.py`: `--mode`, `--list-modes`, and `argparse` with an optional profile name.
- `tests/test_recommender.py`: 40 new test cases from Agent A (85 in total), then 32 more from Agent C (117 in total by `pytest --collect-only -q`).
- `README.md` (new Challenge 2 subsection, plus "default mode" qualifiers), `model_card.md`, and this file.

**What did you verify or fix manually?**

- **Guard and tests.** I re-ran the regression guard and `pytest` myself after each stage. Default output of the original 10 profiles is unchanged.
- **Agent B's checks.** B hand-computed 56 scores (7 songs, 4 modes, 2 profiles) and found 0 mismatches. B compared the old and new code on 24,000 profile and song pairs, and all results were identical. B also verified every claim in the demo output.
- **Surviving mutations.** B ran 22 mutations on a copy, and 5 survived. They pointed to gaps: no test pinned the weights of every mode, that `energy_sigma` and `partial_mood_credit` were not tested, that the tie-break order was not tested, and that the unknown-mode CLI test only checked for a non-zero exit. Agent C added a test of the full weight table, tests with custom `ScoringMode` objects, tests for sorting by score, then energy gap, then title in every mode, and an exact exit code of 2. Then Agent C re-ran 11 mutations on a copy of the repo, including: genre-first energy 2.0 to 2.5, no tie-break, no title tie-break, no gap tie-break, ignoring `energy_sigma`, ignoring the partial mood credit, and an unknown mode that exits 1. The suite caught all 11. The real repo was not mutated.
- **Hard-coded mode count.** Some tests assumed there were exactly four modes. Agent C made them read `MODES`. As a test, Agent C added a fifth mode with one registry line in a copy of the repo, and the whole suite still passed. The real repo has four modes.
- **Missing validation.** `ScoringMode` accepted negative or infinite weights. It now raises a `ValueError` for weights that are not finite or are below 0, an `energy_sigma` that is not above 0, and a partial mood credit outside 0 to 1. Zero weights are still allowed.
- **A misleading "max 8".** Extension profiles can score above 8.0, so `--list-modes` now says "base max 8", and I checked the docstrings.
- **A command-line change.** The old code printed "Unknown profile" and exited with 1 for any bad word. With `argparse`, an unknown flag or an extra word (such as an unquoted `high-energy pop`) exits with 2. I wrote this down in the README.
- **Skipped on purpose.** I did not make `str(mode)` stricter, because it only matters for odd input. I left `MODES` as a plain dict. I kept the `energy_sigma` and `partial_mood_credit` fields, because tests now cover them. I let `--list-modes` ignore a bad profile name, because it exits before looking at it.
- **Docs.** I searched README.md and model_card.md for statements that are true only for the default mode ("maximum score is 8.0", "4.0 of 8.0", the weights table) and added a "default mode" qualifier. I left the history sections as they were. I used the real test counts.

---

## Challenge 3: Diversity and Fairness Logic

**What task did you give the agent?**

The challenge was "Diversity and Fairness Logic": stop the top results from filling up with the same artist or genre. I used the same three agent roles as before and did the git work and the checks myself:

- Agent A built it.
- Agent B reviewed A's work, read-only, and wrote its own version to compare.
- Agent C fixed B's findings and updated the docs and this log.

I prototyped the work on a branch called `challenge-3-diversity`. After the checks passed, I merged it into `main`.

**Prompts used:**

- To Agent A (shortened): "Add an optional diversity penalty. Build the top k greedily. For each next pick, its adjusted score is its normal score minus 1.0 per earlier pick by the same artist and minus 0.5 per earlier pick in the same genre. Report the adjusted score, and add a reason line for each penalty. With the penalty off, the output must be byte-for-byte identical to today's."
- Shared rule for all agents (same as before): "Default behavior must stay exactly the same. A regression guard compares the top 5 and the scores of the original 10 profiles and the CLI output of `all` and `adversarial` against saved files. New options are extras. Do not run git add, commit, or reset."
- To Agent B (shortened): "Review A's work read-only. Write your own version from the rule and compare. Check old against new on the default path. Run mutations on a copy of the repo."
- To Agent C (shortened): "Make a negative `k` return an empty list on both paths. Validate `k` once at the top of `recommend_songs`: whole numbers only, and reject floats, None, strings and booleans with a clear `ValueError`. Make a huge integer penalty raise the same `ValueError` as other bad penalties. A song with no artist must not crash, and a missing artist or genre must not count as 'the same'. Wrap the long import line. Run at least 5 mutations on a copy. Then update the README, the model card and this log."

**What did the agent generate or change?**

- `src/recommender.py`: two constants (`ARTIST_PENALTY = 1.0`, `GENRE_PENALTY = 0.5`), the helpers `check_penalty` and `pick_diverse`, and optional `artist_penalty` and `genre_penalty` arguments on `recommend_songs` and `Recommender`. Both are 0 by default, and then the old plain ranking runs.
- `src/main.py`: a `--diverse` flag that turns on both default sizes and adds one header line.
- `tests/test_recommender.py`: 460 new test cases from Agent A (577 in total), then 33 more from Agent C (610 in total, in 95 test functions, by `pytest --collect-only -q`).
- Agent C added `check_k` and the None handling in `pick_diverse`.
- `README.md` (new Challenge 3 subsection, flow diagram, run commands, test counts), `model_card.md`, and this file.

**What did you verify or fix manually?**

- **Guard and tests.** I re-ran the regression guard and `pytest` myself after each stage. Default output of the original 10 profiles is unchanged.
- **My hand check.** Library Rain scores 7.92 in the plain list. It comes second after a lofi song, so I checked that 7.92 - 0.50 = 7.42 matches the diverse output. It does.
- **Agent B's checks.** B wrote an independent version, and it matched A's on 1680 cases (14 profiles, 4 modes, 6 penalty pairs, 5 values of `k`). B compared the old and new code on the default path in 24,000 cases, and all were identical. B ran 2352 property cases, and they passed. B ran 35 mutations on a copy, and 34 were killed. The survivor was the negative-`k` change, which I had already agreed to make.
- **A's demo numbers.** I reproduced all of them: 5 of 14 lists change at the default sizes, average distinct artists 4.71 to 4.93, average distinct genres 4.36 to 4.57, and 8 of 14 lists change at 100 / 100.
- **Negative `k`.** On the plain path, `k=-1` returned 19 songs, because the slice `ranked[:k]` counts from the end. I decided that both paths return an empty list for `k` of 0 or less. This is a small change from the old behavior, and I wrote it in the README.
- **Non-whole `k`.** B found that `k=None`, `k=2.5` and `k="3"` behaved differently on the two paths. Agent C now validates `k` once at the top of `recommend_songs`. Only whole numbers pass. Floats, None, strings and booleans raise a `ValueError`.
- **Overflow.** `check_penalty("p", 2**2000)` raised an `OverflowError`. It now raises the same `ValueError` as every other bad penalty.
- **Missing artist.** A song without an `artist` key raised a `KeyError`, but only when diversity was on. A None artist or genre was also treated as equal to another None. Now missing values never count as repeats. While fixing this, a first try still failed, because the penalty text was built even when there was no repeat. A test caught it, and Agent C fixed it.
- **Mutations.** Agent C ran 10 mutations on a copy of the repo (never the real one): no `k` validation, no negative-`k` clamp, a raw negative `k` slice, booleans accepted, floats truncated, None artist equal, None genre equal, missing artist raising, overflow handling removed, and penalty text built with no repeat. The suite caught all 10.
- **Skipped on purpose.** I did not normalize artist or genre text, so "Neon Echo" and "neon echo " count as different. I did not scale the penalties for extension profiles, whose scores run from 10 to 11, so they are relatively weak there. I did not make `Recommender.explain_recommendation` show penalty lines. It explains a song's own fit, so it can disagree with the adjusted score in the CLI. I wrote all three in the README.
- **Docs.** I searched README.md and model_card.md for old test counts ("117", "61 test functions"), the "sorted from highest to lowest" sentence, and the flow description. I used the real counts and said that the diversity step is optional.

---

## Challenge 4: Visual Summary Table

**What task did you give the agent?**

The challenge was "Visual Summary Table": show the top recommendations as a formatted table in the terminal, with the reasons for each score. I used the same three agent roles as before and did the git work and the checks myself:

- Agent A built it.
- Agent B reviewed A's work, read-only, and ran its own checker.
- Agent C fixed B's findings and updated the docs and this log.

I worked on a branch called `challenge-4-table`.

**Prompts used:**

- To Agent A (shortened): "Suggest and implement a way to display the top recommendations as a formatted table in the terminal, using a library like tabulate or simple ASCII formatting. The table MUST include the reasons for each score, not only the score." I also said it must be opt-in (a flag), the default output must stay byte-for-byte the same, and it should compare `tabulate` with plain ASCII before choosing.
- Shared rule for all agents (same as before): "Default behavior must stay exactly the same. A regression guard compares the top 5 and the scores of the original 10 profiles and the CLI output of `all` and `adversarial` against saved files. New options are extras. Do not run git add, commit, or reset."
- To Agent B (shortened): "Review A's work read-only. Write your own checker that runs the real CLI over many profiles, modes and widths. Check that the default output did not change. Run mutations on a copy of the repo."
- To Agent C (shortened): "Fix the crash on a whitespace-only field. Add the missing tests (right alignment of Score and Rank, the blank line before the table, a minimum share for the Why column, exact text checks) and run at least 8 mutations on a copy. Adopt B's better column layout, but output at 80 columns and up must not change. Treat zero-width characters as width 0. Rename the shadowed function in `main.py`. Then update the README, the model card and this log. Document what is not fixed."

**What did the agent generate or change?**

- `src/table.py` (new): `format_table(recommendations, width=100)`. It is plain ASCII and uses only the standard library. It has its own word wrapper that counts wide characters as 2 columns, and it picks the column widths. Every reason is on its own `- ` bullet line, and long ones wrap with an indent.
- `src/main.py`: a `--table` flag and a `--width N` flag (default 100, minimum 60). Without `--table`, the output is unchanged.
- `tests/test_table.py` (new): 39 test cases from Agent A, then 125 in total after Agent C (735 test cases in the whole project, by `pytest --collect-only -q`).
- `tabulate` is not installed here and is not in `requirements.txt`. Agent A compared it with a hand-written ASCII helper and chose the helper: no dependency, full control over how reasons wrap, and a pure function that is easy to test. `requirements.txt` did not change.
- `README.md` (new Challenge 4 subsection, run commands, test counts), `model_card.md`, and this file.

**What did you verify or fix manually?**

- **Guard and tests.** I re-ran the regression guard and `pytest` myself after each stage. The default output of the original 10 profiles and of `all` and `adversarial` is unchanged. I also looked at the real tables.
- **Agent B's checker.** B wrote an independent checker that ran the real CLI 896 times (20 profiles, 4 modes, diversity on and off, 8 widths). Every table line had the same length and fit the width. Only plain ASCII was used. Every reason appeared in full as its own bullet group. In 170 default-output runs, the output was byte-identical to the commit before the change. Agent C re-ran this checker after the layout change: 896 runs, 0 problems.
- **B's mutations.** B ran 34 mutations on a copy, and 8 survived. They pointed to gaps in my tests: nothing pinned the right alignment of Score and Rank, the blank line before the table, a minimum share for the Why column, or the exact text of title, artist, genre and mood (the checks ignored spaces, so a cut word could pass).
- **A crash.** B found that a title, artist, genre or mood that is only spaces crashed `format_table` with `ValueError: max() iterable argument is empty`. Agent C fixed it. Agent C added tests for empty and whitespace-only values in each field (in a table with other songs and in a table with only that song). A first test with other songs in the table did not catch the crash when I mutated it back, because the column was never empty. Only the single-song test caught it.
- **A false claim.** Agent A wrote that the Why column gets at least half of the free width. B showed that this is false at widths 60 to about 65. Agent C removed the claim.
- **Layout change.** B tried a different way to share the width. Words stay whole first, Why takes what is left, and spare width goes to the other columns. B measured that words cut in Title and Artist at width 70 fell from 49 to 0, and at width 60 from 51 to 39. The total table height at 70 columns grew from 644 to 806 lines. Agent C ported the idea into `src/table.py`. The first port changed the output at 80 columns and up, because it handed the spare width out in a different order and dropped the minimum column widths. Agent C fixed that. Then I compared the real CLI output before and after the change for all profiles, 4 modes, diversity on and off, and widths 80, 90, 100, 120, 140 and 200 (78 files in all). All were identical. Only tables below 80 columns changed. After the change, there are 0 cut words at width 70 (I counted words of titles and artists), and 0 cut reasons from 70 up.
- **Mutations by Agent C.** Agent C ran 33 mutations on a copy of the repo (never the real one): Score and Rank alignment flipped (and each one alone), `WHY_SHARE` changed (0.3 and 0.7), the blank line before and after the table removed, the last reason dropped, the width off by one (both ways), the `=` rule removed, the CLI ignoring `--table`, the CLI ignoring `--width`, the width minimum removed (in `table.py` and in the CLI), a changed default width, a zero-width joiner and ESC counted as width 1, the wrapper using `<` instead of `<=`, the bullet missing, and a few more in the width rule. On the first run, 7 survived. Two of those needed hand-made cases, because on the real profiles they give the same output: a case where the columns must go below their minimum widths, and one where very long words force Title and Artist down. I added tests for all of them, and the final run killed all 33. I also pinned the exact column widths of several real profiles at widths 60, 70, 80 and 100.
- **Zero-width characters.** The width function now counts combining marks, format characters (such as the zero-width joiner) and ESC as 0 columns, with a test.
- **Small cleanups.** I renamed the `table_width` function in `main.py`, because the `print_recommendations` parameter has the same name. `format_table` has a one-line docstring, `table_width` is typed `Optional[int]`, the "too small" check comes first in `column_widths`, and the long lines are wrapped.
- **Skipped on purpose.** The header "Genre / Mood" always wraps to two lines. I accepted this. I also did not fix the problems below. I wrote them in the README limits list: a `|` inside a cell looks like a column separator (the line length stays right); a score of 12345 or more at width 60 gives a misleading "too small" error; zero-width-joiner emoji sequences are not handled; I did not check how real terminals draw CJK or emoji text; reasons are split on `"; "`; `--width` without `--table` is ignored; and piping to `head` can raise a `BrokenPipeError`, which is normal for `print`.
- **Docs.** I searched README.md and model_card.md for the old test counts ("610", "95 test functions") and the run-command list. I used the real counts (735 in all) and added the new test file to the test description. I did not call the table better than the list for everything. It is easier for comparing songs at 80 columns and up, and about the same for reading the reasons.

---

## Design Pattern (SF10)

> Document how AI helped you choose or implement a design pattern.

**Which design pattern did you use?**

A data-driven Strategy pattern, for the scoring modes. Each mode is a small frozen object that holds the weights (`ScoringMode`). The modes live in a registry (`MODES`). The scoring code is shared, and it reads the weights from the mode it is given.

**How did AI help you brainstorm or implement it?**

Before coding, I asked Agent A to weigh at least three designs. It weighed four:

- (a) Each mode as a function or object of its own. It is flexible, but every mode has to rebuild the reasons text, and copied scoring code can drift apart.
- (b) A frozen dataclass of weights plus a registry dict. The modes are named, interchangeable, and picked at run time. A new mode is one registry entry, and it is easy to test.
- (c) A subclass of `Recommender` for each mode. It splits one idea across classes, and the function-based API would not see it.
- (d) An if/elif on a mode name inside `score_song`. It is the simplest, but every new mode means editing the scoring code, and it is hard to test.

Agent A picked (b), because the scoring code is shared and only the numbers differ. Later, Agent B reviewed it and described the limit: it is a parameterized strategy, where data selects the weights and the formulas are shared. That is the right size for four modes, and a fifth mode needs one registry line and no scoring changes. But it cannot change the shape of a term (for example, a straight-line energy term) without code changes, so I did not call it a general strategy in the README. Agent C then checked the "one line" claim by adding a fifth mode to a copy of the repo and running the full suite. It passed.

**How does the pattern appear in your final code?**

In `src/recommender.py`:

- `ScoringMode` is the strategy: a frozen dataclass with the four weights, the energy curve width, the partial mood credit, and a `max_score` property. It checks its own numbers when it is created.
- `MODES` is the registry (a dict by name), and `DEFAULT_MODE` is `balanced`. A new mode is one new entry.
- `resolve_mode` turns `None`, a name, or a `ScoringMode` into a `ScoringMode`, and raises a `ValueError` for an unknown name.
- `score_song` and `recommend_songs` take an optional `mode` argument, and `Recommender(songs, mode=...)` passes it on.

In `src/main.py`, the `--mode` flag picks a mode by name, and `--list-modes` prints the registry.
