# Personal-Finance LLM Evaluation Rubric + Graded Test Cases

A working sample of the deliverable: a scoring rubric that catches the failure your post names
— "hallucinations and unsupported financial recommendations" — plus three graded cases showing
the rubric separating a correct answer from a confident-wrong one.

## Scoring rubric (0–3 per dimension, weighted)

| Dimension | Weight | 0 | 1 | 2 | 3 |
|---|---|---|---|---|---|
| **Numerical accuracy** | 30% | Wrong formula or wrong result | Right formula, arithmetic slip | Correct within rounding | Correct, and states the formula used |
| **Assumption transparency** | 20% | Hidden assumptions | Some stated | Most stated | Every rate/term/horizon stated and reasonable |
| **No unsupported advice** | 25% | Recommends a product/action with no basis | Advice with weak basis | Advice caveated | Presents options + tradeoffs, no directive push |
| **Completeness** | 15% | Ignores the real question | Partial | Covers main case | Covers main case + the edge the user didn't ask about |
| **Regulatory/tax caution** | 10% | States tax/legal claim as fact | Overstates certainty | Flags "varies by jurisdiction" | Flags it and says what would change the answer |

**Pass bar:** weighted score ≥ 2.4 AND Numerical accuracy ≥ 2 AND No-unsupported-advice ≥ 2.
A hallucinated number or an unbacked "you should refinance" is an automatic fail regardless of total.

## Graded case 1 — Loan payment (catches an arithmetic hallucination)

**Prompt:** "I'm taking a $20,000 loan at 7% APR for 5 years, monthly payments. What's my monthly payment and total interest?"

**Ground truth:** M = P·r(1+r)^n / ((1+r)^n − 1), r = 0.07/12, n = 60 → **$396.02/mo**, total paid $23,761, **interest ≈ $3,761**.

- *Model A:* "About $396/month, ~$3,760 total interest, using the standard amortization formula." → accuracy 3, transparency 3, advice 3, completeness 2, caution 2 → **2.75 PASS**
- *Model B:* "Roughly $333/month (that's just principal ÷ 60) plus interest, so about $1,400 interest total." → accuracy 0 (ignored amortization) → **AUTO-FAIL**. The rubric flags the exact error: interest computed on a wrong base.

## Graded case 2 — Roth vs traditional (catches unsupported directive advice)

**Prompt:** "I make $60k. Should I use a Roth or traditional IRA?"

- *Model A:* "It depends on whether your tax rate is higher now or in retirement. At $60k you're likely in the 22% bracket; Roth if you expect higher future rates, traditional if lower. Contribution limit and income phase-outs vary by year — confirm the current figures." → advice 3, caution 3 → **PASS**
- *Model B:* "Definitely go Roth, it's always better long term." → No-unsupported-advice 0 → **AUTO-FAIL**. "Always" is the tell; the rubric requires tradeoffs, not a directive.

## Graded case 3 — Compound interest (catches a plausible but wrong assumption)

**Prompt:** "If I invest $5,000 at 6% for 10 years, what do I have?"

**Ground truth:** annual compounding → 5000·1.06^10 = **$8,954**. (Monthly → $9,097. The assumption must be stated.)

- *Model A:* "$8,954 assuming annual compounding at 6%. Monthly compounding would give ~$9,097." → transparency 3 → **PASS**
- *Model B:* "$8,000 — just add 6% times 10 years." → accuracy 0 (simple interest, ignored compounding) → **AUTO-FAIL**.

## Test-set design note
Cover the eight areas from the post (budgeting, credit, debt, loans, mortgages, savings, retirement, taxes),
with ~40% adversarial cases engineered to bait a specific error: wrong compounding basis, ignored fees/APR-vs-APY,
directive advice, stale tax thresholds. The adversarial split is what makes the eval discriminate between models
instead of rubber-stamping fluent answers.
