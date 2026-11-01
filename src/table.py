"""Plain-ASCII table for the top recommendations, with every reason for each score (standard library only)."""

import unicodedata

MIN_WIDTH = 60
DEFAULT_WIDTH = 100
HEADERS = ("Rank", "Title", "Artist", "Genre / Mood", "Score", "Why")
# Narrowest the Title, Artist and Genre / Mood columns may be squeezed to, and the Why column's floor
MIN_SIDE_WIDTHS = (6, 6, 8)
MIN_WHY_WIDTH = 10
WHY_SHARE = 0.5  # only for very narrow tables: fraction of the free width Why asks for when words must be cut


def zero_width(ch: str) -> bool:
    """True for characters with no width: combining marks, format characters (such as ZWJ) and ESC."""
    return ch == "\x1b" or unicodedata.category(ch) in ("Mn", "Me", "Cf")


def display_width(text: str) -> int:
    """Number of terminal columns text occupies: wide (CJK, emoji) characters count 2, zero-width ones 0."""
    return sum(0 if zero_width(ch) else 2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def wrap(text: str, width: int) -> list:
    """Word-wrap text to at most width columns; a word wider than width is cut into pieces."""
    lines = []
    line = ""
    for word in text.split():
        while word:
            joined = f"{line} {word}" if line else word
            if display_width(joined) <= width:
                line, word = joined, ""
            elif line:  # the word does not fit after what is already on this line
                lines.append(line)
                line = ""
            else:  # a lone word wider than the cell: cut it to fit and carry the rest over
                cut = 1
                while cut < len(word) and display_width(word[:cut + 1]) <= width:
                    cut += 1
                lines.append(word[:cut])
                word = word[cut:]
    if line:
        lines.append(line)
    return lines or [""]


def pad(text: str, width: int, align: str = "<") -> str:
    """Pad text with spaces to width terminal columns (left-aligned unless align is '>')."""
    gap = " " * (width - display_width(text))
    return gap + text if align == ">" else text + gap


def split_reasons(explanation: str) -> list:
    """Split an explanation into its reasons the way recommend_songs joins them ("; "); none gives []."""
    return explanation.split("; ") if explanation else []


def column_widths(rows: list, width: int) -> list:
    """Pick the six column widths so the whole table (borders and padding included) fits within width.

    Rank and Score take what their values need. The other four columns share the rest:
    - Title, Artist and Genre / Mood start at their minimum (or longest word if wider), Why at its longest word.
    - Why then takes what is left, up to its widest reason, so a reason is wrapped only when it must be.
    - Spare width goes to Genre / Mood first, then to the narrower of Title and Artist, up to their full text.
    If that leaves Why less than its longest word, Title, Artist and Genre / Mood go down to their longest
    words instead. Only when even the longest words do not fit (below about 70 columns) does Why ask for
    WHY_SHARE of the free width, the other columns get squeezed, and long words are cut.
    """
    overhead = 3 * len(HEADERS) + 1  # "| " and " |" around every cell, one shared "|" between neighbours
    rank_w = max([display_width(HEADERS[0])] + [display_width(r["rank"]) for r in rows])
    score_w = max([display_width(HEADERS[4])] + [display_width(r["score"]) for r in rows])
    avail = width - overhead - rank_w - score_w
    if avail < sum(MIN_SIDE_WIDTHS) + MIN_WHY_WIDTH:
        raise ValueError(f"width {width} is too small for this table")

    columns = [
        [r["title"] for r in rows],
        [r["artist"] for r in rows],
        [part for r in rows for part in (r["genre"], r["mood"])],
    ]
    reasons = [reason for r in rows for reason in r["reasons"]]
    # widest text of each column once runs of spaces are squeezed
    natural = [max([m] + [display_width(" ".join(text.split())) for text in col])
               for m, col in zip(MIN_SIDE_WIDTHS, columns)]
    # longest word of each column (a whitespace-only text has none), and that word or the column minimum if wider
    word = [max([1] + [display_width(w) for text in col for w in text.split()]) for col in columns]
    soft = [max(m, w) for m, w in zip(MIN_SIDE_WIDTHS, word)]
    # a reason plus its 2-character "- " bullet; the header is the floor when nothing is wider
    why_natural = max([display_width(HEADERS[5])] + [display_width(reason) + 2 for reason in reasons])
    why_word = max([MIN_WHY_WIDTH] + [display_width(w) + 2 for reason in reasons for w in reason.split()])

    if sum(word) + why_word <= avail:  # every word fits whole
        why_w = min(why_natural, max(avail - sum(soft), why_word))
        sides = list(soft if sum(soft) + why_w <= avail else word)
        spare = avail - sum(sides) - why_w
        grown = min(spare, natural[2] - sides[2])  # Genre / Mood first, so its two lines stay whole
        sides[2] += grown
        spare -= grown
        while spare > 0 and any(sides[i] < natural[i] for i in (0, 1)):  # then the narrower of Title and Artist
            i = min((i for i in (0, 1) if sides[i] < natural[i]), key=lambda i: (sides[i], -i))
            sides[i] += 1
            spare -= 1
        return [rank_w, *sides, score_w, why_w]

    mins = list(MIN_SIDE_WIDTHS)
    why_w = min(why_natural, max(avail - sum(soft), int(avail * WHY_SHARE)), avail - sum(mins))
    budget = avail - why_w
    floors = soft if sum(soft) <= budget else mins
    sides = [max(n, f) for n, f in zip(natural, floors)]
    while sum(sides) > budget:  # squeeze the wider of Title/Artist; Genre / Mood only once both are at the floor
        squeezable = [i for i in (0, 1) if sides[i] > floors[i]] or [2]
        i = max(squeezable, key=lambda i: sides[i])
        sides[i] -= 1
    why_w = min(why_natural, avail - sum(sides))
    return [rank_w, *sides, score_w, why_w]


def format_table(recommendations: list, width: int = DEFAULT_WIDTH) -> str:
    """Return recommendations [(song, score, explanation), ...] as an ASCII table no wider than width."""
    if isinstance(width, bool) or not isinstance(width, int) or width < MIN_WIDTH:
        raise ValueError(f"width must be a whole number of at least {MIN_WIDTH}, got {width!r}")
    if not recommendations:
        return "No recommendations."

    rows = [
        {
            "rank": str(rank), "title": str(song["title"]), "artist": str(song["artist"]),
            "genre": str(song["genre"]), "mood": str(song["mood"]), "score": f"{score:.2f}",
            "reasons": split_reasons(explanation),
        }
        for rank, (song, score, explanation) in enumerate(recommendations, start=1)
    ]
    widths = column_widths(rows, width)

    def block(cells: list) -> list:
        """Turn per-column line lists into physical table lines (shorter cells padded with blanks)."""
        height = max(len(lines) for lines in cells)
        return [
            "| " + " | ".join(
                pad(lines[n] if n < len(lines) else "", w, ">" if c in (0, 4) else "<")
                for c, (lines, w) in enumerate(zip(cells, widths))
            ) + " |"
            for n in range(height)
        ]

    def rule(char: str) -> str:
        return "+" + "+".join(char * (w + 2) for w in widths) + "+"

    out = [rule("-")]
    out += block([wrap(h, w) for h, w in zip(HEADERS, widths)])
    out.append(rule("="))
    for row in rows:
        why = [
            # bullet on a reason's first line, indent on its continuation lines
            ("- " if n == 0 else "  ") + line
            for reason in row["reasons"] for n, line in enumerate(wrap(reason, widths[5] - 2))
        ] or ["-"]
        out += block([
            [row["rank"]], wrap(row["title"], widths[1]), wrap(row["artist"], widths[2]),
            wrap(row["genre"], widths[3]) + wrap(row["mood"], widths[3]), [row["score"]], why,
        ])
        out.append(rule("-"))
    return "\n".join(out)
