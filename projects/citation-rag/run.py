"""
Demo runner. Shows: a grounded+cited answer, an honest refusal, the eval report, and a
regression gate catching a bad config (score floor set too low so junk sneaks through).

    python run.py
"""
from rag import Retriever, answer, load_corpus
from rag.eval import evaluate, regression_gate


def main() -> None:
    corpus = load_corpus()
    r = Retriever(corpus, score_floor=0.12)

    print("=" * 70)
    print("Q: How long do I have to return an item?")
    print(answer("How long do I have to return an item?", r).render())

    print("=" * 70)
    print("Q: Do you offer a student discount?  (not in the docs)")
    print(answer("Do you offer a student discount?", r).render())

    print("=" * 70)
    baseline = evaluate(r)
    print(f"Baseline eval  ->  answerability={baseline.answerability}  "
          f"citation_validity={baseline.citation_validity}  overall={baseline.overall}")
    for f in baseline.failures:
        print("   fail:", f)

    # A tempting "improvement": drop the floor to 0 so we always return something.
    # It looks like higher recall, but it destroys the refusal behavior. The gate catches it.
    reckless = Retriever(corpus, score_floor=0.0)
    candidate = evaluate(reckless)
    print("=" * 70)
    print(f"Candidate (score_floor=0.0)  ->  answerability={candidate.answerability}  "
          f"citation_validity={candidate.citation_validity}")
    ok, msg = regression_gate(baseline, candidate)
    print("Regression gate:", msg)
    print("=" * 70)


if __name__ == "__main__":
    main()
