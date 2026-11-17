# Notes on the implementation

## Matching is the part to distrust first

Two sections can have the same heading and mean completely different things. A
unique heading is still treated as an identity in this version. Conversely, a
renamed and heavily rewritten clause can show up as one removal and one addition.
The report exposes the matching rule rather than pretending the alignment is
certain.

Duplicate headings skip the unique-heading rule. Exact text is matched first,
with proximity as a tie breaker; remaining candidates use token overlap. This
keeps both clauses, but it cannot resolve every ambiguity. Splitting one clause
into two is not supported as a distinct operation.

Plain paragraphs get positional labels for readability, but those labels do not
drive matching. Headings that contain only a document title can appear as renamed
clauses if they have body text. Empty headings are ignored.

## What the price parser deliberately misses

The parser recognizes dollar signs and `USD`, with explicit monthly, annual, or
one-time frequency wording. It skips multiple prices, missing prices, unsupported
currencies, and mixed frequencies. It does not interpret discounts, credits,
negative amounts, taxes, conditional fees, or spelled-out amounts. Even a single
price may be conditional; the raw clause remains the source of truth.

In the sample, parking changes from included to $65 monthly. There is no explicit
old dollar amount, so the report skips the delta. This trades some convenience
for fewer assumptions. The rent calculation is straightforward: 1575 − 1450 =
125 per month; 125 × 12 = 1500 over twelve payments. That does not establish the
length of the renewed agreement.

## The explanation check has a hard limit

Checking that a quote exists is cheap. Checking that an explanation follows from
the quote is harder. This code does the first check only. Explanations stay visibly
labeled as model output. The quote check also rejects valid quotations if a model
changes spacing or punctuation; that is intentional for this first version.

One model request keeps spending bounded and debugging simple. It is not an
autonomous agent. Adding more agents would not solve the alignment problem.

## Local validation, 2026-11-17

- Python 3.14.5 on Windows: 37 tests passed.
- The documented sample command wrote HTML and JSON reports.
- Expected sample results: five changed clauses, one moved, one added, one removed,
  and one unchanged. Two clauses have calculated price deltas.
- No paid model calls were made. The request adapter and quote validation were
  exercised with mocked provider responses.

GitHub CI checks package installation as well as the tests. Its status is recorded
on the repository, separately from the local results above.
