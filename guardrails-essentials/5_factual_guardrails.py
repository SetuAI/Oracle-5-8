"""
================================================================================
FACTUAL GUARDRAILS
================================================================================

THE PROBLEM
-----------
This is the hardest of the five, and it is worth being honest about why.

The other guardrails check properties we can define. Is this on topic? Is this
harmful? Does this contain a PAN number? Is this valid JSON? Each has a clear
answer that a rule or a classifier can reach.

"Is this true?" has no such shortcut. Verifying an arbitrary claim is roughly as
hard as producing the claim in the first place, so a model checking another
model's facts is not obviously an improvement.

SO WE CHANGE THE QUESTION
-------------------------
Rather than asking "is this true?", which we cannot answer, we ask something we
can:

    Is every statement in this answer supported by the documents we retrieved?

That is a narrower question with a definite answer. We are no longer judging
truth in general -- we are checking that the model stayed inside its sources.

This is called GROUNDING, and it is how factual checking is actually done in
practice. It does not catch a wrong number in the source document. It catches
the model inventing a number that was never in any document, which is the
failure that actually happens.

WHY THIS MATTERS PARTICULARLY HERE
----------------------------------
A mutual fund assistant deals in numbers that customers act on. An invented
expense ratio, an invented exit load, an invented return figure -- these are not
embarrassing errors, they are potentially misrepresentations of a regulated
financial product.

THE APPROACH
------------
    Check 1   Number verification   instant, free, no model needed
    Check 2   Claim verification    one model call, catches invented statements

Check 1 deserves attention because it is unusually effective for its cost. Most
damaging hallucinations in a financial assistant are numeric, and a number is
either present in the source text or it is not. No judgement required.

A THIRD ACTION
--------------
The topic guardrail could block. The privacy guardrail could redact. The format
guardrail could retry. This one introduces the fourth and last action: ESCALATE.

When an answer looks ungrounded, refusing outright is often too blunt -- the
answer may well be correct and simply worded in a way our check could not
follow. So instead of discarding it, we route it to a human reviewer.

That is the human-in-the-loop pattern, and this is where it naturally belongs:
not on every answer, which nobody can staff, but on the small proportion the
automated checks are unsure about.

HOW TO RUN
----------
    pip install openai python-dotenv
    export OPENAI_API_KEY="sk-..."
    python factual_guardrails.py

================================================================================
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


# ==============================================================================
# SECTION 0 - CONFIGURATION
# ==============================================================================

MODEL = "gpt-4o-mini"

# What proportion of the answer's numbers must be traceable to the source before
# we accept it without a model call.
#
# It is not 1.0, and the reason is practical. Answers legitimately contain
# numbers that are not in the source: dates the customer mentioned, a total the
# model correctly added up, an ordinal like "the 3 options below". Demanding
# perfection would escalate almost everything and make the reviewer queue
# useless.
NUMERIC_GROUNDING_THRESHOLD = 0.8

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ==============================================================================
# SECTION 1 - THE DECISION OBJECT
# ==============================================================================

GROUNDED = "grounded"            # Supported by the source. Send it.
UNGROUNDED = "ungrounded"        # Contradicts or invents. Do not send it.
NEEDS_REVIEW = "needs_review"    # Unclear. Send it to a human.


@dataclass
class FactualDecision:
    """
    The result of checking an answer against its sources.

    verdict            GROUNDED, UNGROUNDED or NEEDS_REVIEW.
    check              Which check decided it.
    reason             A short explanation for the logs.
    unsupported_facts  Specific items we could not trace to the source. This is
                       what a human reviewer actually needs -- not "something is
                       wrong" but "this number does not appear anywhere".

    field(default_factory=list) gives each object its own empty list. Writing
    "= []" would make every object share a single list, because a default value
    is created once when the class is defined rather than once per object.
    """
    verdict: str
    check: str
    reason: str
    unsupported_facts: List[str] = field(default_factory=list)


# ==============================================================================
# SECTION 2 - CHECK 1: NUMBER VERIFICATION
# ==============================================================================
# Pull every number out of the answer, pull every number out of the source
# documents, and see whether the first set is contained in the second.
#
# Crude, and considerably more useful than it sounds. In a financial assistant
# the numbers ARE the answer, and an invented number is the failure that causes
# actual harm. This check finds them in under a millisecond with no API call.
#
# It cannot catch a purely verbal invention -- "this fund is suitable for
# conservative investors" contains no numbers at all. That is Check 2's job.
# ==============================================================================

def extract_numbers(text: str) -> List[str]:
    """
    Find every number in a piece of text.

    ABOUT THE REGEX
    ---------------
    \\d{1,3}(?:,\\d{2,3})+    numbers written with commas: 5,000 or 1,00,000
                             (Indian grouping uses 2 digits after the first
                             group, which is why it is {2,3} and not {3})
    \\d+\\.?\\d*               plain numbers, with or without a decimal point
    |                        try the first alternative, then the second

    The comma pattern comes first deliberately. If the plain pattern ran first,
    it would match "5" out of "5,000" and stop, and we would be comparing the
    wrong value.

    We then strip the commas so that "5,000" in the answer and "5000" in the
    source are recognised as the same number.
    """
    raw = re.findall(r"\d{1,3}(?:,\d{2,3})+|\d+\.?\d*", text)
    return [value.replace(",", "") for value in raw]


def check_numbers(answer: str, sources: List[str]) -> FactualDecision:
    """
    Verify that the numbers in the answer appear in the source documents.

    ABOUT set()
    -----------
    We build a set of the source numbers rather than a list. Checking whether an
    item is in a set is close to instant regardless of size, while checking a
    list means scanning it item by item. With a handful of documents the
    difference is invisible; with a real document store it is the difference
    between usable and unusable.
    """
    source_numbers = set()
    for document in sources:
        source_numbers.update(extract_numbers(document))

    answer_numbers = extract_numbers(answer)

    if not answer_numbers:
        return FactualDecision(
            verdict=NEEDS_REVIEW,
            check="numbers",
            reason="no numbers to verify, cannot judge from this check alone",
        )

    unsupported = [n for n in answer_numbers if n not in source_numbers]
    supported_count = len(answer_numbers) - len(unsupported)
    ratio = supported_count / len(answer_numbers)

    if ratio >= NUMERIC_GROUNDING_THRESHOLD:
        return FactualDecision(
            verdict=GROUNDED,
            check="numbers",
            reason=f"{supported_count} of {len(answer_numbers)} numbers found in sources",
        )

    return FactualDecision(
        verdict=NEEDS_REVIEW,
        check="numbers",
        reason=f"only {supported_count} of {len(answer_numbers)} numbers found in sources",
        unsupported_facts=unsupported,
    )


# ==============================================================================
# SECTION 3 - CHECK 2: CLAIM VERIFICATION
# ==============================================================================
# Hand the model the answer and the source documents together, and ask whether
# every statement in the answer is supported.
#
# Two details in the prompt do most of the work:
#
#   1. The model is told to judge SUPPORT, not TRUTH. This is the whole idea of
#      grounding. A statement can be perfectly true and still ungrounded, and for
#      our purposes ungrounded is what matters -- it means the model wrote it
#      from memory rather than from the document in front of it.
#
#   2. The model is asked to name the unsupported statement, not just report a
#      verdict. "Something in this answer is unsupported" is useless to a
#      reviewer. "The claim that the exit load is 2% does not appear in the
#      sources" tells them exactly where to look.
# ==============================================================================

GROUNDING_PROMPT = """You check whether an answer is supported by the source \
documents provided.

You are NOT judging whether the answer is true in general. You are judging one
thing only: can every statement in the answer be traced to the sources below?

A statement is UNSUPPORTED if it states something the sources do not say, even
if it sounds plausible or is likely to be correct.

Reply in exactly this format:

VERDICT: SUPPORTED
or
VERDICT: UNSUPPORTED
UNSUPPORTED_CLAIM: <the specific statement that is not in the sources>

SOURCES:
{sources}

ANSWER TO CHECK:
{answer}"""


def check_claims(answer: str, sources: List[str]) -> FactualDecision:
    """
    Ask a model whether the answer is supported by the sources.

    Temperature is 0 so the same answer always gets the same verdict.

    On an API failure we return NEEDS_REVIEW rather than UNGROUNDED. This is a
    deliberate difference from the safety guardrail, where a failure meant
    blocking outright.

    The reasoning: a safety failure risks real harm, so refusing is correct. A
    grounding failure usually means an answer is slightly loose, and discarding
    every answer whenever a network call times out would break the product for no
    safety benefit. Sending it to a human is the proportionate response.

    Different risks deserve different defaults. "Always fail closed" is too blunt
    a rule to apply everywhere without thinking.
    """
    combined_sources = "\n\n---\n\n".join(sources)

    try:
        response = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            max_tokens=150,
            messages=[{
                "role": "user",
                "content": GROUNDING_PROMPT.format(
                    sources=combined_sources, answer=answer
                ),
            }],
        )

        reply = response.choices[0].message.content.strip()

        if "VERDICT: SUPPORTED" in reply.upper():
            return FactualDecision(
                verdict=GROUNDED,
                check="claims",
                reason="every statement traced to the sources",
            )

        # Pull out the specific claim the model flagged, if it gave us one.
        claim_match = re.search(r"UNSUPPORTED_CLAIM:\s*(.+)", reply, re.IGNORECASE)
        claim = claim_match.group(1).strip() if claim_match else "not specified"

        return FactualDecision(
            verdict=UNGROUNDED,
            check="claims",
            reason="a statement could not be traced to the sources",
            unsupported_facts=[claim],
        )

    except Exception as error:
        return FactualDecision(
            verdict=NEEDS_REVIEW,
            check="claims",
            reason=f"grounding check unavailable ({type(error).__name__})",
        )


# ==============================================================================
# SECTION 4 - PUTTING IT TOGETHER
# ==============================================================================

def check_factual(answer: str, sources: List[str]) -> FactualDecision:
    """
    Run the full factual guardrail.

        numbers all check out   ->  grounded, no API call needed
        otherwise               ->  ask the model to check the claims

    Check 1 acts as a filter. Answers whose numbers all trace back to the source
    are accepted immediately, and only the remainder cost a model call. In a
    working system that is the large majority filtered out for free.
    """
    if not answer.strip():
        return FactualDecision(UNGROUNDED, "input", "answer is empty")

    number_decision = check_numbers(answer, sources)

    if number_decision.verdict == GROUNDED:
        return number_decision

    return check_claims(answer, sources)


REVIEW_NOTICE = (
    "I want to double-check this before confirming it. A member of our team will "
    "get back to you shortly."
)


def handle_answer(answer: str, sources: List[str]) -> str:
    """
    What the application calls before showing an answer to the customer.

    Note that NEEDS_REVIEW and UNGROUNDED produce the same customer-facing
    message but very different internal consequences. One goes into a reviewer's
    queue with the answer attached; the other is discarded and logged as a
    failure. The customer does not need to know which happened, and telling them
    would only invite them to rephrase until they get past the check.
    """
    decision = check_factual(answer, sources)

    if decision.verdict == GROUNDED:
        return answer

    # In a real system, this is where the answer, the sources, the flagged claims
    # and the customer's original question are written to a review queue. The
    # reviewer needs all four to make a decision in seconds rather than minutes.
    return REVIEW_NOTICE


# ==============================================================================
# SECTION 5 - RUNNING IT
# ==============================================================================

SOURCE_DOCUMENTS = [
    """BLUECHIP GROWTH FUND - FACTSHEET, AUGUST 2026
    Category: Large Cap. NAV as on 8 August 2026: Rs 48.21 per unit.
    Total expense ratio (direct plan): 0.65% per annum.
    Minimum lump sum investment: Rs 5,000.
    Exit load: 1% if redeemed within 365 days of allotment.""",

    """BLUECHIP GROWTH FUND - PERFORMANCE
    1 year return: 14.2%. 3 year return: 11.8% annualised.
    5 year return: 13.4% annualised.
    Benchmark: Nifty 100 TRI. Fund manager: since March 2019.""",
]


SAMPLE_ANSWERS = [
    # Every number is in the factsheet. Check 1 accepts this with no API call.
    ("The Bluechip Growth Fund has a NAV of Rs 48.21 as on 8 August 2026, "
     "with an expense ratio of 0.65% and a minimum investment of Rs 5,000."),

    # The 3-year return is stated as 15.6%. The source says 11.8%.
    # An invented number, and the one that would cause real damage.
    ("The fund has delivered a 3 year return of 15.6% annualised, comfortably "
     "ahead of its benchmark."),

    # An invented exit load: 2% for 18 months, where the source says 1% for 365
    # days. Both numbers are wrong.
    ("An exit load of 2% applies if you redeem within 18 months of investing."),

    # No numbers at all, so Check 1 cannot judge it and passes it to Check 2.
    # The claim about suitability appears nowhere in the sources.
    ("This fund is well suited to conservative investors looking for capital "
     "protection with steady income."),

    # Correct, and stated without numbers. Check 2 should support this.
    ("The fund is a Large Cap scheme and is benchmarked against the Nifty 100 TRI."),
]


def demonstrate_number_check() -> None:
    """Run Check 1 alone, which needs no API key."""
    print("=" * 78)
    print("CHECK 1 - NUMBER VERIFICATION")
    print("=" * 78)

    for answer in SAMPLE_ANSWERS:
        decision = check_numbers(answer, SOURCE_DOCUMENTS)

        print(f"\n  {decision.verdict.upper():13} {answer[:64]}")
        print(f"                {decision.reason}")
        if decision.unsupported_facts:
            print(f"                not in sources: "
                  f"{', '.join(decision.unsupported_facts)}")


def main() -> None:
    demonstrate_number_check()

    print("\n" + "=" * 78)
    print("FULL GUARDRAIL - BOTH CHECKS")
    print("=" * 78)

    for answer in SAMPLE_ANSWERS:
        decision = check_factual(answer, SOURCE_DOCUMENTS)

        print(f"\n  {decision.verdict.upper():13} via {decision.check}")
        print(f"                {answer[:64]}")
        print(f"                {decision.reason}")
        if decision.unsupported_facts:
            print(f"                flagged: {decision.unsupported_facts[0][:60]}")

    print("\n" + "=" * 78)
    print("WHAT THE CUSTOMER SEES")
    print("=" * 78)

    for answer in [SAMPLE_ANSWERS[0], SAMPLE_ANSWERS[2]]:
        print(f"\n  MODEL WROTE  : {answer[:66]}")
        print(f"  CUSTOMER SEES: {handle_answer(answer, SOURCE_DOCUMENTS)[:66]}")


if __name__ == "__main__":
    main()