import subprocess
import sys
from pathlib import Path

import pytest

from src.main import ADVERSARIAL_PROFILES, ALL_PROFILES, EXTENSION_PROFILES, PROFILES
from src.recommender import ARTIST_PENALTY, GENRE_PENALTY, MODES, load_songs, recommend_songs
from src.table import DEFAULT_WIDTH, HEADERS, MIN_WIDTH, display_width, format_table, split_reasons, wrap

REPO_ROOT = Path(__file__).resolve().parent.parent
WIDTHS = (60, 70, 80, 100, 140)
SONGS = load_songs("data/songs.csv")


def penalties(diverse):
    return {"artist_penalty": ARTIST_PENALTY, "genre_penalty": GENRE_PENALTY} if diverse else {}


def results(profile, mode, diverse):
    return recommend_songs(ALL_PROFILES[profile], SONGS, k=5, mode=mode, **penalties(diverse))


def cases():
    return [(p, m, d) for p in ALL_PROFILES for m in MODES for d in (False, True)]


def fake(title="T", artist="A", genre="g", mood="m", explanation="one; two"):
    return ({"title": title, "artist": artist, "genre": genre, "mood": mood}, 1.0, explanation)


def parse(table):
    """Split a table into (header cells, [cells per physical line] for each recommendation block)."""
    lines = table.split("\n")
    marks = [i for i, ch in enumerate(lines[0]) if ch == "+"]

    def cells(line):
        return [line[a + 2:b - 1].rstrip() for a, b in zip(marks, marks[1:])]

    blocks, current, header = [], [], []
    for line in lines[1:]:
        if line.startswith("+"):
            if line.startswith("+="):
                header, current = current, []
            elif current:
                blocks.append(current)
                current = []
        else:
            current.append(cells(line))
    return header, blocks


def column(block, index):
    return [row[index] for row in block]


def column_widths_of(table):
    """The six inner column widths (padding excluded), read off the first rule line."""
    marks = [i for i, ch in enumerate(table.split("\n")[0]) if ch == "+"]
    return [b - a - 3 for a, b in zip(marks, marks[1:])]


def rebuilt(fragments):
    return " ".join(part.strip() for part in fragments if part.strip())


def reasons_in(block):
    reasons = []
    for fragment in column(block, 5):
        if fragment.startswith("- "):
            reasons.append([fragment[2:]])
        elif fragment.strip():
            assert fragment.startswith("  "), f"continuation line is not indented: {fragment!r}"
            reasons[-1].append(fragment)
    return reasons


def squash(text):
    return "".join(text.split())


@pytest.mark.parametrize("width", WIDTHS)
def test_every_line_has_the_same_width_and_fits_for_all_profiles_modes_and_diversity(width):
    for profile, mode, diverse in cases():
        lines = format_table(results(profile, mode, diverse), width).split("\n")
        assert len({display_width(line) for line in lines}) == 1, (profile, mode, diverse)
        assert display_width(lines[0]) <= width, (profile, mode, diverse)


@pytest.mark.parametrize("width", WIDTHS)
def test_every_title_artist_score_and_rank_appears_in_order(width):
    for profile, mode, diverse in cases():
        recommendations = results(profile, mode, diverse)
        header, blocks = parse(format_table(recommendations, width))
        assert len(blocks) == len(recommendations)
        for n, (block, (song, score, _)) in enumerate(zip(blocks, recommendations), start=1):
            assert column(block, 0)[0].strip() == str(n)
            assert column(block, 4)[0].strip() == f"{score:.2f}"
            texts = (rebuilt(column(block, 1)), rebuilt(column(block, 2)), rebuilt(column(block, 3)))
            if width >= 70:  # exact text: a word cut in half would show up as two words
                assert texts == (song["title"], song["artist"], f"{song['genre']} {song['mood']}"), (profile, width)
            else:
                expected = (song["title"], song["artist"], song["genre"] + song["mood"])
                assert tuple(map(squash, texts)) == tuple(map(squash, expected))


@pytest.mark.parametrize("width", WIDTHS)
def test_every_reason_of_every_recommendation_appears_in_full_one_per_line_group(width):
    for profile, mode, diverse in cases():
        recommendations = results(profile, mode, diverse)
        _, blocks = parse(format_table(recommendations, width))
        for block, (_, _, explanation) in zip(blocks, recommendations):
            expected = explanation.split("; ")
            found = reasons_in(block)
            assert len(found) == len(expected), (profile, mode, diverse, width)
            for fragments, reason in zip(found, expected):
                # words are only cut in half when a column is narrower than the word
                assert squash(rebuilt(fragments)) == squash(reason)
                if width >= 70:
                    assert rebuilt(fragments) == reason


def test_default_width_shows_each_reason_on_its_own_line_group_with_a_bullet():
    recommendations = results("ext-90s-nostalgia", "balanced", False)
    _, blocks = parse(format_table(recommendations))
    for block, (_, _, explanation) in zip(blocks, recommendations):
        first_lines = [f for f in column(block, 5) if f.startswith("- ")]
        assert [f[2:].split()[0] for f in first_lines] == [r.split()[0] for r in explanation.split("; ")]


def test_diversity_penalty_reasons_and_extension_reasons_appear_in_the_table():
    diverse = format_table(results("lofi/chill", "balanced", True))
    assert "diversity penalty" in diverse
    extension = format_table(results("ext-90s-nostalgia", "balanced", False))
    assert "mood tags matched 3 of 3 requested:" in extension and "decade 1990s" in extension


def test_header_row_names_every_column():
    header, blocks = parse(format_table(results("pop/happy", "balanced", False), 100))
    for index, label in enumerate(HEADERS):
        assert rebuilt(column(header, index)) == label
    assert len(blocks) == 5


def test_rules_use_plain_ascii_only():
    table = format_table(results("pop/happy", "balanced", False))
    assert table.isascii()
    lines = table.split("\n")
    assert lines[0] == lines[-1] and set(lines[0]) == {"+", "-"}
    assert sum(set(line) == {"+", "="} for line in lines) == 1


def test_empty_list_gives_one_line():
    assert format_table([]) == "No recommendations."
    assert format_table([], 60) == "No recommendations."


def test_a_song_with_no_reasons_shows_a_dash():
    _, blocks = parse(format_table([fake(explanation="")], 80))
    assert [cell for cell in column(blocks[0], 5) if cell] == ["-"]


def test_scores_of_different_widths_line_up():
    songs = [fake("A"), fake("B"), fake("C")]
    table = format_table([(s, score, e) for (s, _, e), score in zip(songs, (10.5, 7.95, -1.25))], 80)
    _, blocks = parse(table)
    assert [column(b, 4)[0].strip() for b in blocks] == ["10.50", "7.95", "-1.25"]
    assert len({len(line) for line in table.split("\n")}) == 1


def test_very_long_title_artist_and_unbroken_word_wrap_inside_their_cells():
    long_text = "Supercalifragilisticexpialidocious " * 3
    table = format_table([fake(title=long_text, artist="X" * 90, explanation="Y" * 150 + "; ok")], 60)
    assert len({display_width(line) for line in table.split("\n")}) == 1
    assert max(display_width(line) for line in table.split("\n")) <= 60
    _, blocks = parse(table)
    assert squash("".join(column(blocks[0], 1))) == squash(long_text)
    assert squash("".join(column(blocks[0], 2))) == "X" * 90
    assert [squash("".join(r)) for r in reasons_in(blocks[0])] == ["Y" * 150, "ok"]


def test_unicode_does_not_crash_and_wide_characters_count_two_columns():
    song = fake(title="日本語のタイトル Café", artist="Beyoncé", genre="j-pop", mood="café")
    table = format_table([song], 60)
    assert len({display_width(line) for line in table.split("\n")}) == 1
    assert display_width("日本") == 4 and display_width("é") == 1
    assert max(display_width(line) for line in table.split("\n")) <= 60


def test_wrap_breaks_on_spaces_cuts_overlong_words_and_never_exceeds_the_width():
    text = "mood tags matched 3 of 3 requested: nostalgic, warm, sentimental (+1.50)"
    lines = wrap(text, 18)
    assert len(lines) > 1 and all(display_width(line) <= 18 for line in lines)
    assert " ".join(lines) == text
    assert wrap("abc def", 7) == ["abc def"] and wrap("abc def", 6) == ["abc", "def"]
    assert wrap("", 10) == [""]
    assert wrap("abcdefgh", 3) == ["abc", "def", "gh"]


@pytest.mark.parametrize("bad", [59, 0, -5, 80.0, "80", None, True])
def test_format_table_rejects_a_bad_width(bad):
    with pytest.raises(ValueError):
        format_table([fake()], bad)


def test_default_width_is_one_hundred_and_minimum_sixty():
    assert (DEFAULT_WIDTH, MIN_WIDTH) == (100, 60)
    assert max(len(line) for line in format_table(results("pop/happy", "balanced", False)).split("\n")) <= 100


@pytest.mark.parametrize("width", (60, 70))
def test_a_narrow_table_uses_exactly_the_width_it_is_given(width):
    for profile, mode, diverse in cases():
        table = format_table(results(profile, mode, diverse), width)
        assert display_width(table.split("\n")[0]) == width, (profile, mode, diverse)


@pytest.mark.parametrize("width", (80, 100, 140))
def test_why_keeps_a_large_share_of_the_text_columns_from_80_columns_up(width):
    for profile, mode, diverse in cases():
        ranks, title, artist, genre, score, why = column_widths_of(format_table(results(profile, mode, diverse), width))
        assert why >= 0.4 * (title + artist + genre + why), (profile, mode, diverse, width)
        assert why >= 25, (profile, mode, diverse, width)


def test_long_words_fall_back_to_cutting_and_why_asks_for_its_share():
    reason = " ".join(["R" * 12] * 3)
    table = format_table([fake(title="T" * 60, explanation=reason)], 100)
    assert column_widths_of(table) == [4, 22, 6, 8, 5, 36]
    assert len({len(line) for line in table.split("\n")}) == 1


PINNED_WIDTHS = [  # (profile, mode, diverse): {table width: [Rank, Title, Artist, Genre / Mood, Score, Why]}
    (("pop/happy", "balanced", False), {60: [4, 7, 7, 8, 5, 10], 70: [4, 7, 7, 8, 5, 20], 80: [4, 7, 7, 8, 5, 30]}),
    (("lofi/chill", "balanced", True), {60: [4, 6, 6, 8, 5, 12], 70: [4, 9, 8, 8, 5, 17], 80: [4, 9, 8, 8, 5, 27]}),
    (("ext-90s-nostalgia", "balanced", False),
     {60: [4, 6, 6, 8, 5, 12], 70: [4, 6, 7, 9, 5, 20], 80: [4, 6, 7, 9, 5, 30]}),
    (("ext-instrumental-focus", "mood-first", False),
     {60: [4, 6, 6, 8, 5, 12], 70: [4, 9, 8, 7, 5, 18], 100: [4, 9, 8, 8, 5, 47]}),
    (("adv-energy-only", "balanced", False),
     {65: [4, 8, 7, 9, 5, 13], 80: [4, 8, 7, 9, 5, 28], 100: [4, 14, 13, 9, 5, 36]}),
]


@pytest.mark.parametrize("case, expected", PINNED_WIDTHS)
def test_column_widths_for_real_profiles_are_pinned(case, expected):
    for width, widths in expected.items():
        assert column_widths_of(format_table(results(*case), width)) == widths, (case, width)


def test_spare_width_goes_to_genre_first_then_the_narrower_of_title_and_artist():
    song = fake(title="aaaa bbbb cccc dddd", artist="eeee ffff gggg hhhh", genre="indie pop", explanation="short; text")
    assert [column_widths_of(format_table([song], width)) for width in (70, 71, 72)] == [
        [4, 13, 13, 9, 5, 7], [4, 13, 14, 9, 5, 7], [4, 14, 14, 9, 5, 7],
    ]


def test_columns_go_below_their_minimums_before_a_word_is_cut():
    song = fake(title="abcde", artist="abcdef", explanation="R" * 20)
    assert column_widths_of(format_table([song], 68)) == [4, 5, 6, 7, 5, 22]


def test_very_long_words_squeeze_title_and_artist_down_to_their_longest_word_first():
    song = fake(title="T" * 10 + " " + "T" * 9, artist="A" * 12, genre="g", mood="g", explanation="R" * 40)
    assert column_widths_of(format_table([song], 88)) == [4, 10, 12, 8, 5, 30]


def test_split_reasons_splits_only_on_semicolon_space():
    assert split_reasons("a;b; c") == ["a;b", "c"] and split_reasons("") == []


def test_rank_and_score_are_right_aligned():
    recommendations = [fake(f"S{n}") for n in range(1, 11)]
    recommendations = [(song, score, e) for (song, _, e), score in zip(recommendations, (7.95, 10.5) * 5)]
    lines = format_table(recommendations, 80).split("\n")
    rows = {cells[0].strip(): cells for cells in (line.split("|")[1:-1] for line in lines if line.startswith("| "))}
    assert rows["1"][0] == "    1 " and rows["10"][0] == "   10 "
    assert rows["1"][4] == "  7.95 " and rows["2"][4] == " 10.50 "
    assert rows["1"][1].startswith(" S1") and rows["1"][5].startswith(" - ")


@pytest.mark.parametrize("field", ["title", "artist", "genre", "mood"])
@pytest.mark.parametrize("value", ["", " ", "   ", "\t \n"])
@pytest.mark.parametrize("width", (60, 70, 100))
def test_empty_and_whitespace_only_fields_still_render_aligned(field, value, width):
    table = format_table([fake(**{field: value}), fake()], width)
    assert len({display_width(line) for line in table.split("\n")}) == 1
    _, blocks = parse(table)
    assert len(blocks) == 2
    index = {"title": 1, "artist": 2, "genre": 3, "mood": 3}[field]
    assert rebuilt(column(blocks[0], index)) == {"title": "", "artist": "", "genre": "m", "mood": "g"}[field]
    assert [rebuilt(column(blocks[1], i)) for i in (1, 2, 3)] == ["T", "A", "g m"]


@pytest.mark.parametrize("field", ["title", "artist", "genre", "mood"])
@pytest.mark.parametrize("value", ["", "   ", "\t \n"])
def test_a_table_whose_only_song_has_a_blank_field_still_renders_aligned(field, value):
    for width in (60, 80):
        table = format_table([fake(**{field: value})], width)
        assert len({display_width(line) for line in table.split("\n")}) == 1


@pytest.mark.parametrize("explanation", ["", " ", "   ", "one;  two"])
def test_empty_and_whitespace_only_explanations_still_render_aligned(explanation):
    table = format_table([fake(explanation=explanation)], 60)
    assert len({display_width(line) for line in table.split("\n")}) == 1


def test_zero_width_characters_take_no_column():
    assert display_width("e\u0301") == 1  # combining accent
    assert display_width("a\u200db") == 2  # zero-width joiner
    assert display_width("a\u20ddb") == 2  # enclosing mark
    assert display_width("\x1b") == 0 and display_width("\x1b[0m") == 3
    table = format_table([fake(title="Cafe\u0301 \u200dLoft", artist="A\u200bB")], 60)
    assert len({display_width(line) for line in table.split("\n")}) == 1


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "src.main", *args], cwd=REPO_ROOT, capture_output=True, text=True)


def test_cli_table_flag_prints_a_table_with_reasons_and_keeps_the_header_block():
    plain = run_cli("pop/happy")
    result = run_cli("pop/happy", "--table")

    assert result.returncode == 0
    assert result.stdout.splitlines()[:5] == plain.stdout.splitlines()[:5]
    assert "+======" in result.stdout and "| Rank |" in result.stdout
    assert "genre match: pop (+1.00)" in result.stdout
    assert "Why:" not in result.stdout
    assert max(len(line) for line in result.stdout.splitlines()[5:]) <= DEFAULT_WIDTH


def test_cli_without_table_is_unchanged_and_width_alone_changes_nothing():
    for args in (["pop/happy"], ["all"], ["adversarial"]):
        plain = run_cli(*args)
        assert "+---" not in plain.stdout
        assert run_cli(*args, "--width", "80").stdout == plain.stdout


def test_cli_table_works_for_every_profile_keyword_and_matches_the_library():
    tables = {
        "all": len(PROFILES), "adversarial": len(ADVERSARIAL_PROFILES), "extensions": len(EXTENSION_PROFILES),
        **dict.fromkeys(ALL_PROFILES, 1),
    }
    for keyword, count in tables.items():
        result = run_cli(keyword, "--table", "--width", "70")
        assert result.returncode == 0, keyword
        assert result.stdout.count("| Rank |") == count, keyword
        assert all(len(line) <= 70 for line in result.stdout.splitlines() if line.startswith(("+", "| ")))
    expected = format_table(results("lofi/chill", "balanced", False), 70)
    assert expected in run_cli("lofi/chill", "--table", "--width", "70").stdout


def test_cli_table_follows_the_width_option_and_defaults_to_one_hundred():
    narrow, default = run_cli("pop/happy", "--table", "--width", "70"), run_cli("pop/happy", "--table")
    rules = lambda out: {len(line) for line in out.splitlines() if line.startswith("+")}
    assert rules(narrow.stdout) == {70}
    assert rules(default.stdout) == {len(format_table(results("pop/happy", "balanced", False)).split("\n")[0])}
    assert narrow.stdout != default.stdout


def test_cli_table_has_exactly_one_blank_line_between_the_header_block_and_the_table():
    lines = run_cli("pop/happy", "--table").stdout.splitlines()
    first = next(i for i, line in enumerate(lines) if line.startswith("+---"))
    assert lines[first - 1] == "" and lines[first - 2].startswith("=" * 10)
    assert lines[-1] == "" and lines[-2].startswith("+---") and lines[-3].startswith("| ")
    two_profiles = run_cli("all", "--table").stdout
    assert "\n+\n" not in two_profiles and "\n\n\n" not in two_profiles


def test_cli_table_combines_with_mode_and_diverse():
    result = run_cli("lofi/chill", "--table", "--mode", "mood-first", "--diverse")

    assert result.returncode == 0
    assert " Mode: mood-first" in result.stdout.splitlines()
    assert " Diversity: on (artist -1.00, genre -0.50)" in result.stdout.splitlines()
    assert "diversity penalty" in result.stdout
    assert "mood match: chill (+4.00)" in result.stdout
    assert format_table(results("lofi/chill", "mood-first", True), DEFAULT_WIDTH) in result.stdout


@pytest.mark.parametrize("bad", ["30", "59", "-80", "abc", "80.5"])
def test_cli_rejects_a_bad_width_with_a_clear_message(bad):
    result = run_cli("pop/happy", "--table", "--width", bad)

    assert result.returncode == 2
    assert "--width" in result.stderr and "at least 60" in result.stderr
    assert result.stdout == ""
