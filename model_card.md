# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name  

Give your model a short, descriptive name.  
Example: **VibeFinder 1.0**  

---

## 2. Intended Use  

Describe what your recommender is designed to do and who it is for. 

Prompts:  

- What kind of recommendations does it generate  
- What assumptions does it make about the user  
- Is this for real users or classroom exploration  

---

## 3. How the Model Works  

The recommender works like a judge at a talent show who scores every act against a checklist and then announces the highest scores.

**What it knows about a song:** its genre (like pop or lofi), its mood (like happy or chill), how energetic it feels, and how positive or sunny it sounds (called valence). **What it knows about you:** your favorite genre, your favorite mood, and the energy and positivity level you are in the mood for.

**How it scores a song.** For every song in the catalog it hands out points in four categories, for a possible total of 8:

- **Energy, up to 4 points.** The closer a song's energy is to the level you asked for, the more points it earns. A song that is a little off loses only a little, and a song that is far off loses a lot. This is the biggest category, because energy is the clearest difference between, say, a study playlist and a workout playlist.
- **Mood, up to 2 points.** A song with exactly your mood earns the full 2 points. A song with a related mood earns half. For example, "playful" counts as close to "happy" and "relaxed" counts as close to "chill".
- **Positivity, up to 1 point.** Songs closer to your preferred level of sunniness earn more.
- **Genre, 1 point.** A song in your favorite genre gets a bonus point. Genre is worth less than mood on purpose, because with only 20 songs most genres have a single song, and a genre label alone should not beat a song that fits your mood and energy.

**How it picks what to show.** Once every song has a score, the songs are lined up from highest to lowest and the top five are shown. If two songs tie, the one whose energy is closer to your target comes first. Along with each pick, the recommender lists the points it earned in each category, so you can see exactly why it was chosen.

**What changed from the starter code.** The starter version only returned the first few songs in the file, without looking at the user at all. This version scores every song, rewards closeness instead of "bigger is better", gives partial credit for similar moods, and explains each result. It runs from the command line, with no app or website.

---

## 4. Data  

Describe the dataset the model uses.  

Prompts:  

- How many songs are in the catalog  
- What genres or moods are represented  
- Did you add or remove data  
- Are there parts of musical taste missing in the dataset  

---

## 5. Strengths  

Where does your system seem to work well  

Prompts:  

- User types for which it gives reasonable results  
- Any patterns you think your scoring captures correctly  
- Cases where the recommendations matched your intuition  

---

## 6. Limitations and Bias 

One weakness I found is that the system serves listeners with extreme energy targets much worse than listeners in the middle, because of how the energy gap is scored against a small catalog. The catalog has only two songs below 0.30 energy and none below 0.22, so a listener who wants very quiet music (energy 0.0) can earn at most 2.72 of the 4 energy points, compared with about 4.0 for any target between 0.2 and 0.9. When no song is close to the target, nearly every song earns little energy credit, so the mood and genre labels (up to 3 points) decide the order: in my "energy 0.0, pop, happy" test, the loud, bright Sunrise City (energy 0.82) ranked #2 above calmer songs only because its labels matched. The recommender therefore favors users whose taste sits in the well-stocked middle of the energy range, and it still prints a confident-looking top 5 with no sign that it had little to choose from.

---

## 7. Evaluation  

I tested ten listener profiles against the 20-song catalog. Four are everyday listeners and six were designed to trip the system up. The full terminal output for every one of them is in the README, under "Stress test: diverse profiles".

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

**What I looked for.** First, does the #1 song make sense for the person described? Second, do different listeners get clearly different lists? Third, do the written reasons add up to the score? Fourth, does any song keep showing up where it doesn't belong?

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

## 8. Future Work  

Ideas for how you would improve the model next.  

Prompts:  

- Additional features or preferences  
- Better ways to explain recommendations  
- Improving diversity among the top results  
- Handling more complex user tastes  

---

## 9. Personal Reflection  

A few sentences about your experience.  

Prompts:  

- What you learned about recommender systems  
- Something unexpected or interesting you discovered  
- How this changed the way you think about music recommendation apps  
