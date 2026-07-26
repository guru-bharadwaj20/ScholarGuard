"""Tests for extracting figure numbers from retraction-notice text.

These labels decide which figures count as ground-truth positives, so a parsing
error does not just lose data — it silently mislabels a clean figure as
manipulated and corrupts every recall number computed afterwards. Hence the
false-positive cases below matter as much as the recall ones.
"""

from scripts.annotate_fraud_figures import parse_figure_numbers


def nums(text):
    return parse_figure_numbers(text)[0]


def test_single_figure_and_panel_letter():
    assert nums("Figure 3B was duplicated.") == {3}
    assert nums("An investigation found duplication in Fig. 7.") == {7}
    assert nums("Figure 4 was manipulated.") == {4}


def test_conjunction_does_not_swallow_the_next_number():
    """'Figures 2 and 4' must not parse as '2 a' and drop the 4."""
    assert nums("Concerns were raised about Figures 2 and 4.") == {2, 4}
    assert nums("Figures 1, 3 and 6 are affected.") == {1, 3, 6}


def test_ranges_expand():
    assert nums("Bands in Figs 1-3 appear identical.") == {1, 2, 3}
    assert nums("Figures 2–4 were reused.") == {2, 3, 4}


def test_abbreviating_period_does_not_split_the_reference():
    """A sentence splitter would cut 'Fig. 7' in two and lose the number."""
    text = "The investigation concluded. Duplication was found in Fig. 7. Done."
    assert nums(text) == {7}


def test_only_the_accused_figure_is_taken_from_a_mixed_notice():
    """A neutral mention alongside an accusation must not be labelled."""
    text = "Figure 1 shows the workflow. Figure 12C is manipulated."
    assert nums(text) == {12}


def test_exculpatory_mentions_are_not_labelled_as_manipulated():
    """Regression: a real notice (PMID 35245321) volunteered supporting data.

    "the authors have provided ... most blots presented in Figs 1-5" would
    otherwise mark every figure in a five-figure paper as manipulated, on the
    strength of the authors' defence, leaving the paper with no negatives.
    """
    text = ("The authors have provided individual level data underlying the "
            "graphs and most blots presented in Figs 1-5. The underlying blots "
            "provided for Fig 3D confirm that despite their similarity, the "
            "bands are not identical.")
    assert 1 not in nums(text) and 2 not in nums(text)


def test_a_figure_needs_a_manipulation_cue_nearby():
    assert nums("See figure 4 for the study workflow.") == set()
    assert nums("Figure 4 shows overlapping panels.") == {4}


def test_notices_without_figures_yield_nothing():
    assert nums("Retracted: A study of protein expression.") == set()
    assert nums("This article was retracted by the publisher.") == set()


def test_bare_numbers_are_not_mistaken_for_figures():
    """Only figure-prefixed numbers count; years and volumes must not."""
    assert nums("published in 2019, volume 45, pages 1-10") == set()
    assert nums("10 patients were enrolled in 3 cohorts") == set()


def test_implausible_figure_numbers_are_rejected():
    assert nums("Figure 99 is fine") == set()


def test_evidence_is_returned_for_audit():
    found, evidence = parse_figure_numbers(
        "The authors retract this article. Figure 3B was duplicated from 5A.")
    assert found == {3}
    assert evidence and "Figure 3B" in evidence[0]


def test_comma_and_list_keeps_every_number():
    """'Figs 3, 4, and 5' is the commonest phrasing; it must not stop at 4."""
    assert nums("concerns regarding results presented in Figs 3, 4, and 5.") == {3, 4, 5}
    assert nums("Figures 1, 2, 3 and 7 are affected") == {1, 2, 3, 7}


def test_supplementary_figures_are_not_main_figures():
    """Supplementary figures are numbered separately from Figure N."""
    assert nums("Supplementary Figure 1b shows duplicates.") == set()
    assert nums("Supp. Fig 2 and Extended Data Figure 3") == set()
    text = "Supplementary Figure 1b: panels are duplicates. Figure 4(a): images reused."
    assert nums(text) == {4}


def test_list_does_not_run_away_into_unrelated_numbers():
    got = nums("Duplication in Figure 2, published in 2019 with 45 patients")
    assert 2 in got and 45 not in got and 19 not in got
