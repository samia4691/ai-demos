"""Run with: pytest -q  (from the citation-rag/ folder)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag import Retriever, answer, load_corpus
from rag.eval import evaluate, regression_gate


def _retriever(floor=0.12):
    return Retriever(load_corpus(), score_floor=floor)


def test_grounded_answer_is_cited():
    a = answer("How long do I have to return an item?", _retriever())
    assert a.grounded is True
    assert a.citations, "a grounded answer must carry at least one citation"
    assert any(c.startswith("returns-policy") for c in a.citations)


def test_out_of_corpus_query_refuses():
    a = answer("Do you offer a student discount?", _retriever())
    assert a.grounded is False
    assert a.citations == []
    assert "don't have that" in a.render()


def test_score_floor_controls_refusal():
    # With no floor, junk sneaks through and the refusal guarantee breaks.
    strict = evaluate(_retriever(0.12))
    reckless = evaluate(_retriever(0.0))
    assert strict.answerability >= reckless.answerability


def test_regression_gate_blocks_a_drop():
    baseline = evaluate(_retriever(0.12))
    candidate = evaluate(_retriever(0.0))
    ok, msg = regression_gate(baseline, candidate)
    assert ok is False
    assert "BLOCKED" in msg


def test_no_regression_passes_when_equal():
    baseline = evaluate(_retriever(0.12))
    candidate = evaluate(_retriever(0.12))
    ok, msg = regression_gate(baseline, candidate)
    assert ok is True
