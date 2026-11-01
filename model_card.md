# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name

**VibeCheck 1.0**: a small music recommender that tells you why it picked each song.

---

## 2. Goal / Task

VibeCheck suggests songs. It tries to answer one question: "Which songs in this catalog fit what this listener says they want?"

- **Input:** a taste profile. It holds a favorite genre, a favorite mood, a target energy level, and a target "sunniness" (valence).
- **Output:** the top 5 songs, each with a score and a list of reasons.

It does not predict what a person will click or replay. It only matches a stated taste to song labels and numbers.

---

## 3. Data Used

- **Size:** 20 songs in `data/songs.csv`. The first 10 came with the project. I added the other 10.
- **Columns:** id, title, artist, genre, mood, energy, tempo, valence, danceability, acousticness.
- **Variety:** 17 genres and 16 moods. Most appear only once. Lofi and chill each have 3 songs.
- **Used in scoring:** energy, mood, valence, and genre.
- **Not used:** tempo, danceability, and acousticness. They move almost in step with energy, so they would count the same signal twice.

**Limits.**

- The catalog is tiny.
- The 10 songs I added have invented numbers, written with AI help. They are guesses, not measurements.
- Energy only covers 0.22 to 0.97. Only 2 songs are below 0.30. No song sits between 0.58 and 0.75.
- There are no lyrics, no language, no release years, and no listening history.

---

## 4. Algorithm Summary

VibeCheck is like a judge with a checklist. It scores every song. Then it shows the five best.

Each song can earn up to 8 points:

- **Energy: up to 4 points.** The closer a song's energy is to what you want, the more points it gets. A little off loses a little. Far off loses a lot.
- **Mood: up to 2 points.** An exact match gets 2. A close mood gets 1. For example, "playful" is close to "happy". "Relaxed" is close to "chill".
- **Sunniness (valence): up to 1 point.** Songs closer to the sunniness you want score higher.
- **Genre: 1 point.** A song gets it if it matches your favorite genre.

Genre is worth less than mood on purpose. Most genres have only one song here. A genre tag alone should not beat a song that fits your mood and energy.

After scoring, the songs are sorted from highest to lowest. The top five are shown. If two songs tie, the one with energy closer to your target goes first. Each pick comes with the points it earned, so you can see why it was chosen.

The starter code only returned the first few songs and ignored the user. This version scores every song, rewards closeness, gives partial credit for close moods, and explains each result. It runs in the terminal only.

---

## 5. Observed Behavior / Biases

**Biggest weakness: quiet and extreme listeners get less help.**

- The catalog has only two songs below 0.30 energy, and none below 0.22.
- A listener who wants energy 0.0 can earn at most 2.72 of the 4 energy points. Anyone between 0.2 and 0.9 can earn about 4.
- When no song is close, the mood and genre labels decide the order.
- In my "energy 0.0, pop, happy" test, the loud, bright Sunrise City (energy 0.82) ranked #2 only because its labels matched.
- The top five still looked confident. Nothing warned that the system had little to choose from.

**Other patterns I saw.**

- **Energy is the boss.** It is half of all the points. A "sad classical" listener who also asked for very high energy got metal, rock, and EDM.
- **Labels must match word for word.** "Indie pop" earns nothing for a "pop" listener. "Romantic" is in no group of close moods, so only one song can match it.
- **One song keeps coming back.** Gym Hero is in the top five for 5 of 10 profiles. It looks like a happy pop song on paper, and only its mood tag is different.
- **Some listeners get fuller lists.** Lofi and chill have 3 songs each. A metal or classical fan has one genre match and then filler.
- **One taste only.** A profile cannot say "never metal" or "I like quiet and loud". It also cannot find anything new for you.

**What works well.**

- Chill Lofi and Happy Pop results feel right to me.
- Opposite listeners get opposite lists. Chill Lofi and Deep Intense Rock share no songs.
- The reasons always add up to the score, so every result can be explained.

---

## 6. Evaluation Process

- **Profiles.** I tested 10: four everyday listeners and six tricky ones, such as "sad but loud" and "labels that don't exist".
- **What I checked.** Does the top pick fit the listener? Do different listeners get different lists? Do the reasons add up? Does any song repeat where it shouldn't?
- **Comparisons.** I compared profiles in 12 pairs and wrote down what changed and why.
- **One experiment.** I doubled the energy weight and halved the genre weight. The #1 song stayed the same for all 10 profiles. Below #1, one list got clearly better and two got a little worse. I put the weights back.
- **A trace.** I worked out, term by term, why Pulse Garden ranks first for "high-energy pop".
- **Tests.** Eleven automated tests pass. They cover the `Recommender` class (including a test with the songs in reverse order and a check that it matches the function-based version on the real catalog) and the input cleaning. They do not check exact scores. I checked the scoring by running profiles and reading the results.

The full terminal output for every profile is in the README, under "Stress test: diverse profiles". The details are below.

**Everyday profiles**

- **Happy Pop** (`pop/happy`): pop, happy mood, fairly high energy.
- **Chill Lofi** (`lofi/chill`): lofi, chill mood, low energy, a calm study listener.
- **High-Energy Pop** (`high-energy pop`): pop, euphoric mood, very high energy, a workout listener.
- **Deep Intense Rock** (`deep intense rock`): rock, intense mood, very high energy, dark and heavy.

**Trick profiles**

- **Sad but loud** (`adv-conflict-sad`): wants sad classical music at very high energy.
- **Made-up labels** (`adv-ghost-labels`): asks for "k-pop" and "aggressive", which are not in the catalog.
- **Silence seeker** (`adv-extreme-zero`): wants pop and happy, but at energy 0.0 and valence 0.0.
- **Calm labels, loud numbers** (`adv-calm-labels-high-energy`): asks for ambient and chill, but at energy 0.92.
- **Energy only** (`adv-energy-only`): says nothing except "medium energy".
- **Romantic R&B** (`adv-romantic-rnb`): asks for a mood ("romantic") that sits in no group of related moods.

### What surprised me

- **Gym Hero kept showing up.** It appears in the top five for 5 of the 10 profiles, including Happy Pop. The next section explains why.
- **An EDM song beat both pop songs for the "high-energy pop" listener.** Pulse Garden is the only euphoric song, and matching the mood plus the energy was worth more than the single bonus point for matching "pop".
- **The sad listener got loud songs.** Asking for sad classical music at very high energy returned metal, rock, and EDM. The sad classical song didn't make the list.
- **Weak results look just as confident as strong ones.** A listener whose labels match nothing still gets five songs and scores, with no warning.
- **Doubling the weight on energy changed less than I expected.** The #1 song stayed the same for all ten profiles. Only the lower spots moved.

### Why does "Gym Hero" keep showing up for people who just want happy pop?

The recommender can't hear music. It only compares numbers and labels, and Gym Hero looks a lot like a happy pop song on paper. It is pop (a match), it is loud (energy 0.93, close to Sunrise City's 0.82), and it sounds upbeat (0.77 on the sunniness scale, close to Sunrise City's 0.84). That is three out of four checks passed. The only thing it fails is the mood label: it is tagged "intense", not "happy", and those two moods sit in different groups, so it gets zero mood points. That costs it up to 2 of the 8 points, which is why it ranks fifth for Happy Pop (5.46) and not first (Sunrise City scores 7.95).

It still makes the list because the catalog has only 20 songs and not many happy, loud songs, so Gym Hero fills one of the five seats. I expect a bigger catalog with more happy pop songs would push it out, but I haven't tested that. The same song also shows up for the Deep Intense Rock listener at #2, for the opposite reason: there its "intense" label matches exactly. The lesson is that "gym workout" and "happy summer day" can sound the same on a few numbers, and the difference lives in details this system doesn't capture.

### Comparing the profiles, pair by pair

**The four everyday profiles (all six pairs):**

1. **Happy Pop vs. Chill Lofi.** The two lists share no songs. Happy Pop's songs all have energy 0.76 or higher, and Chill Lofi's are all 0.42 or lower. That makes sense, because energy is the biggest part of the score and these two listeners are at opposite ends of it.
2. **Happy Pop vs. High-Energy Pop.** They return the same five songs in a different order. Pulse Garden jumps from 4th to 1st, because the second listener wants "euphoric" and energy 0.95, and Rooftop Lights falls from 2nd to 5th, because its energy of 0.76 is too mellow for a workout. This makes sense, and it also shows that this small catalog has only about five loud, upbeat songs to hand out.
3. **Happy Pop vs. Deep Intense Rock.** They share only two songs, Gym Hero and Pulse Garden. Both are loud, so they fit either listener, but the rock list leans dark (Storm Runner, Iron Tide) and the pop list leans bright (Sunrise City, Rooftop Lights). That is the sunniness number doing its job.
4. **Chill Lofi vs. High-Energy Pop.** There is no overlap at all, and the two lists are near mirror images: quiet and mellow against loud and bright. This is the clearest sign the energy setting is being respected.
5. **Chill Lofi vs. Deep Intense Rock.** There is no overlap here either, and these two profiles are the furthest apart. It is the sanity check I trust most: if calm study music and heavy rock ever returned similar songs, something would be broken.
6. **High-Energy Pop vs. Deep Intense Rock.** Both ask for energy 0.95 and they share Gym Hero and Pulse Garden, but the rest differs because one wants bright and happy and the other wants dark and heavy. The sunniness number separates them, though only partly: upbeat Gym Hero still lands at #2 for the rock listener.

**Each trick profile against the everyday profile it stresses:**

7. **Sad but loud vs. Deep Intense Rock.** Both ask for energy 0.95 and low sunniness, and they share four of five songs (Iron Tide, Storm Runner, Gym Hero, Pulse Garden). Asking for "sad classical" gets almost the same list as asking for rock, so the sad and classical requests were effectively ignored. The loud energy number overpowered them.
8. **Made-up labels vs. Happy Pop.** They share three songs (Rooftop Lights, Sabor de Noche, Sunrise City). When no label matches anything, the system falls back on energy and sunniness alone, and for a medium-high energy request that looks a lot like the happy pop list. That is reasonable, but it hides the fact that the genre and mood request found nothing.
9. **Silence seeker vs. Happy Pop.** They ask for the same genre and mood, and only the numbers differ (0.0 against 0.8). Only two songs overlap, Sunrise City and Rooftop Lights, and they sit in 2nd and 5th place for the silence seeker even though they're loud. Their matching labels still pull them up the list, even though they're a poor fit. The #1 song became a quiet classical piece, which is right.
10. **Calm labels, loud numbers vs. Chill Lofi.** They share no songs. The "ambient, chill" request returned loud songs (Pulse Garden, Gym Hero) because the very high energy number outweighed the labels. This is a case where the system picked the numbers over the words, and the listener might not agree with that choice.
11. **Energy only vs. Chill Lofi.** Only Midnight Coding is shared. With nothing but an energy number to go on, the energy-only list spans five different genres, because no genre is favored. Chill Lofi's list is full of lofi, because its genre and mood both match.
12. **Romantic R&B vs. Chill Lofi.** They share Midnight Coding and Focus Flow. The R&B listener gets one perfect match (Velvet Hours, 8.00) followed by mid-to-low-energy songs (two lofi, one country, one shoegaze) that are close in energy but nothing else. That fits what the system can do: once the single exact match is used up, it can only guess by energy, and the next four songs are nearly tied.

### What this tells me

The profiles are testing what I meant them to: energy separates the listeners most, mood and genre fine-tune who is on top, and sunniness helps tell bright from dark. The output is valid when a listener's wishes agree with each other and the catalog has songs to match. It is shaky when a listener's wishes conflict, or when the catalog is thin in the area they care about.

---

## 7. Intended Use and Non-Intended Use

**Intended use.**

- Classroom learning. It shows how a score and a ranking turn data into recommendations.
- Explaining a recommendation in plain words, one listener at a time.
- Trying out ideas, such as changing a weight and watching the lists move.

**It assumes the listener** knows what they want and can name one genre, one mood, and one energy level.

**Not intended for.**

- A real music app or real users. The catalog is far too small, and some of its numbers are invented.
- Deciding which artists get promoted, paid, or hidden.
- Listeners with mixed or changing taste, or who need to block genres or moods.
- Judging how good a song is. It only measures how well a song matches a profile.
- A large catalog, unless the weights are re-tested first.

---

## 8. Ideas for Improvement

1. **Say when the match is weak.** Warn the user when no song matches their labels or the best score is low. (Input cleaning is already done: capital letters and extra spaces are ignored, numbers are kept between 0 and 1, and bad input gives a clear error.)
2. **Match labels more softly.** Add more groups of close moods. Treat related genres, like pop and indie pop, as close. Let a profile list several favorites and a few dislikes.
3. **Use a bigger, more varied catalog.** Add more songs per genre and more quiet and mid-range songs. Then test different energy weights again. Add a rule so the top five are not all alike.

---

## 9. Personal Reflection

**Biggest learning moment.**

My biggest lesson came from the stress test. I had picked the weights by thinking them through. I even wrote that labels "cannot easily outvote a very wrong energy level." That sounded right. Then I tried a listener who wanted energy 0.0. A loud pop song ranked #2 because its genre and mood matched. My claim was only true when songs existed near the target. A reason that sounds good is not evidence. A weight is a guess about what people care about. Only awkward test listeners show where the guess breaks.

**How AI helped, and when I double-checked it.**

AI helped me move fast. It explained how Spotify-style systems work. It drafted the scoring recipe and wrote the code. It made up extra songs, built tricky test profiles, and ran quick simulations. The most useful habit was running every idea on the real catalog before I trusted it.

I still had to double-check it often:

- The common starting weights (genre 2, mood 1) looked fine. A simulation showed an intense gym song beating a happy indie-pop song for a happy pop listener.
- The starter tests passed while two methods were empty stubs. They only passed because of list order. A green test does not mean the work is done.
- The 10 songs I added have numbers the AI invented. They are guesses, so I said so in the model card.
- The docs went out of date after almost every change. I had to re-check numbers and claims each time.
- Sub-agent reports were second opinions. I re-ran their numbers before I used them.

**What surprised me.**

A few simple rules can feel like a real recommendation. Four scores added together and one sort gave sensible lists. The Chill Lofi listener got only calm songs. Opposite listeners shared no songs. The written reasons made it feel even more like the system understood. But Gym Hero showed that it does not. It only compares numbers and labels. It also prints five confident songs when nothing matched. A recommendation can feel smart without understanding anything. Real apps may hide how little they know behind the same confident, well-explained list.

**What I would try next.**

- Use a much bigger catalog with real audio measurements. Then re-test the weights.
- Warn the listener when the matches are weak.
- Let a profile list several favorites and some dislikes. Match close genres and moods softly.
- Add a rule so the top five are not all alike.
- Learn from skips and likes, the way real apps do. Then it could find songs a listener did not know to ask for.
