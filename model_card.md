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

Where the system struggles or behaves unfairly. 

Prompts:  

- Features it does not consider  
- Genres or moods that are underrepresented  
- Cases where the system overfits to one preference  
- Ways the scoring might unintentionally favor some users  

---

## 7. Evaluation  

How you checked whether the recommender behaved as expected. 

Prompts:  

- Which user profiles you tested  
- What you looked for in the recommendations  
- What surprised you  
- Any simple tests or comparisons you ran  

No need for numeric metrics unless you created some.

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
