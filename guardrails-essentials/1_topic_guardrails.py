"""
================================================================================
TOPIC GUARDRAILS
================================================================================

THE PROBLEM
-----------
We are building an assistant for a mutual fund company. It should answer
questions about NAV, SIPs, folios, redemptions and scheme details.

It should not answer questions about cooking, laptops, or which stock to buy
tomorrow. Those are not dangerous questions, they are simply not our job.
Answering them costs money and quietly turns a regulated financial product into
a general-purpose chatbot that nobody approved.

A topic guardrail answers one question about every incoming message:

Does this belong to our domain -- yes or no?

THE APPROACH
------------
We use two checks, in order:

    Check 1   Keyword matching       instant, free
    Check 2   Semantic similarity    ~50 ms, one embedding call

Check 1 looks for words we recognise. If it finds one, we are done and we never
make an API call. If it finds nothing, that does not mean the message is off
topic -- it only means this check has nothing useful to say. So we move to
Check 2, which compares meaning instead of spelling and makes the final call.

Cheap check first, expensive check only when the cheap one has no answer.

HOW TO RUN
----------
    pip install openai numpy python-dotenv
    export OPENAI_API_KEY="sk-..."
    python topic_guardrails.py

================================================================================
"""

import os
import re
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

# load_dotenv() reads a file named .env sitting next to this script and copies
# anything inside it into the environment variables. It lets us keep the API key
# out of the code. If there is no .env file, this line simply does nothing.
load_dotenv()


# ==============================================================================
# SECTION 0 - CONFIGURATION
# ==============================================================================
# Every value we might want to change lives here, at the top, instead of being
# buried inside a function. Guardrails get adjusted constantly once real users
# start typing into them, and a setting hidden on line 300 is a setting nobody
# will ever find.
# ==============================================================================

EMBEDDING_MODEL = "text-embedding-3-small"

# Semantic similarity produces a score between roughly 0.0 and 1.0 describing
# how close a message is to our subject.
#
#     score above 0.40  ->  on topic, allow it
#     score below 0.40  ->  off topic, block it
#
# There is nothing magic about 0.40. It is a starting point that works well for
# the embedding model above. The right way to set it is to run real messages
# through the script, look at the scores printed at the bottom, and move the
# number until the split matches your judgement. A different embedding model
# produces a different range of scores and will need its own value.
SIMILARITY_THRESHOLD = 0.40

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ==============================================================================
# SECTION 1 - DEFINING THE DOMAIN
# ==============================================================================
# Before we can check whether a message is on topic, we have to write down what
# our topic actually is. This step gets skipped surprisingly often, and it is the
# main reason topic guardrails behave unpredictably: the boundary was never
# properly defined in the first place.
#
# We write it down twice, because our two checks use it in different ways.
# ==============================================================================

# Used by Check 1: individual words that suggest a mutual fund context.
DOMAIN_KEYWORDS = [
    "nav", "sip", "swp", "stp", "nfo", "folio", "amc", "elss",
    "mutual", "fund", "scheme", "units", "redemption", "redeem",
    "expense ratio", "exit load", "portfolio", "dividend",
    "debt fund", "equity fund", "index fund", "kyc", "nominee",
]

# Used by Check 2: complete questions in the voice of a real investor.
#
# These are not keywords. They are examples of MEANING. Check 2 measures how
# close an incoming message is to these sentences, so two things matter:
#
#   1. Cover the whole domain, not just the most common question. Whatever
#      sub-area is missing here is the sub-area the guardrail will wrongly reject.
#   2. Write them the way investors actually type. Real people write
#      "my money hasn't come yet", not "redemption settlement pending".
DOMAIN_REFERENCE_EXAMPLES = [
    "What is today's NAV for this fund?",
    "How do I start a monthly SIP?",
    "I want to redeem my units, how long will the money take?",
    "What is the expense ratio of this scheme?",
    "How has this fund performed over the last three years?",
    "Is there an exit load if I withdraw early?",
    "How do I add a nominee to my folio?",
    "What is the difference between a direct plan and a regular plan?",
    "Which funds qualify for tax saving under section 80C?",
    "How do I pause or cancel my SIP?",
    "What is the minimum amount I can invest?",
    "How is capital gains tax calculated when I sell my units?",
    "Can I switch from one scheme to another in the same fund house?",
    "My KYC is not verified, what documents do I need?",
    "What is the difference between growth and dividend options?",
    "How do I download my statement for last financial year?",
]


# ==============================================================================
# SECTION 2 - THE DECISION OBJECT
# ==============================================================================
# Our checks could just return True or False. We deliberately do not, because
# the moment a function returns a bare True, every piece of information about WHY
# it decided that is thrown away -- and that is exactly what we need later when a
# customer complains that their question was refused.
#
# So instead we return a small object carrying the decision plus its reasoning.
#
# ABOUT @dataclass
# ----------------
# Normally, writing a class that just holds a few values means writing an
# __init__ method by hand and assigning every field one by one. The @dataclass
# decorator above a class writes all of that for us automatically. We list the
# fields with their types, and Python generates the rest.
#
# So this short class gives us the ability to write:
#
#     decision = GuardrailDecision(verdict="allow", check="keyword", reason="...")
#     print(decision.verdict)     ->  allow
#
# ABOUT Optional[float]
# ---------------------
# Optional[float] means "either a number, or nothing at all (None)". We use it
# for the score because the keyword check does not produce a score -- only the
# similarity check does. The "= None" makes it optional to pass in.
# ==============================================================================

# The two possible outcomes. We define them as named constants rather than typing
# the strings "allow" and "block" all over the file, because a typo in a plain
# string ("alow") fails silently, whereas a typo in a constant name is an
# immediate, obvious error.
ALLOW = "allow"
BLOCK = "block"


@dataclass
class GuardrailDecision:
    """
    The result of running the guardrail on one message.

    verdict   ALLOW or BLOCK.
    check     Which check made this decision. Useful when tracing why a
              particular message was refused.
    reason    A short explanation, written for whoever reads the logs.
    score     The similarity number, when there is one.
    """
    verdict: str
    check: str
    reason: str
    score: Optional[float] = None


# ==============================================================================
# SECTION 3 - CHECK 1: KEYWORD MATCHING
# ==============================================================================
# The simplest possible check. Look for a domain word in the message.
#
# It costs nothing and runs instantly, which is genuinely useful. But it compares
# SPELLINGS, not meaning, so it can only ever confirm a message is on topic --
# it can never prove one is off topic.
#
# That is why this function returns None when it finds nothing. None here means
# "no opinion", not "off topic". A question like "if I invest 5,000 every month
# for 10 years, what will I get?" is obviously about mutual funds and contains
# none of our words. Blocking it here would be wrong.
# ==============================================================================

def check_by_keywords(message: str) -> Optional[GuardrailDecision]:
    """
    Look for domain keywords in the message.

    Returns a decision if a keyword was found, or None if the check has nothing
    to contribute.

    ABOUT THE REGEX
    ---------------
    We use re.search with \\b rather than a simple "if keyword in message".
    \\b means "word boundary" -- the edge of a word.

    Without it, the keyword "nav" would match inside "navigate", and "sip" would
    match inside "gossip". A user asking "how do I navigate your website" would
    be treated as asking about NAV. The word boundary prevents that.

    re.escape() is a safety habit: it makes sure that if a keyword ever contains
    a character with special meaning in a regex, it gets treated as plain text.
    """
    normalised = message.lower()

    matched = []
    for keyword in DOMAIN_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", normalised):
            matched.append(keyword)

    if matched:
        return GuardrailDecision(
            verdict=ALLOW,
            check="keyword",
            reason=f"found domain terms: {', '.join(matched)}",
        )

    return None


# ==============================================================================
# SECTION 4 - CHECK 2: SEMANTIC SIMILARITY
# ==============================================================================
# Check 1 compares spellings. Check 2 compares meanings.
#
# How it works, in four steps:
#
#   1. Turn each of our reference examples into a list of numbers, called an
#      embedding. Sentences with similar meaning produce similar lists.
#   2. Turn the incoming message into an embedding the same way.
#   3. Compare the message against every reference example and get a similarity
#      score for each.
#   4. Take the single highest score. If the message is close to ANY part of our
#      domain, it belongs to us.
#
# Step 4 takes the maximum rather than the average on purpose. Our domain has
# separate areas -- SIPs, taxation, redemptions, KYC -- and a taxation question
# is genuinely unlike a KYC question. Averaging would punish every specific
# question for not resembling the entire domain at once.
# ==============================================================================

def embed_texts(texts: List[str]) -> np.ndarray:
    """
    Turn a list of sentences into their embeddings.

    We send all the sentences in one API call rather than looping and calling
    once per sentence. It is faster and cheaper.

    The result is a table of numbers: one row per sentence.
    """
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return np.array([item.embedding for item in response.data])


def cosine_similarity(vector: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """
    Compare one embedding against every row of a table of embeddings.

    Returns one score per row, close to 1.0 for similar meaning and close to 0.0
    for unrelated meaning.

    WHY COSINE
    ----------
    An embedding can be pictured as an arrow pointing in some direction. Cosine
    similarity measures the ANGLE between two arrows and ignores their length.

    We want that. A one-line question and a long, rambling question about the
    same subject should score as similar. Their arrows point the same way even
    though one is longer, and it is the direction that carries the meaning.

    The steps below:
      - dividing by np.linalg.norm() sets every arrow to the same length, so
        only direction remains
      - the @ symbol is matrix multiplication, which compares our one message
        against all reference rows in a single operation
      - the tiny 1e-10 prevents division by zero if an embedding is ever all
        zeros
    """
    vector_norm = vector / (np.linalg.norm(vector) + 1e-10)
    matrix_norms = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10)
    return matrix_norms @ vector_norm


# Our reference examples never change while the program runs, so their embeddings
# never change either. We work them out once and keep them in this variable.
#
# Without this, every single user message would re-embed all 16 reference
# sentences, multiplying our API bill by 16 for no benefit at all.
_reference_embeddings: Optional[np.ndarray] = None


def get_reference_embeddings() -> np.ndarray:
    """
    Return the reference embeddings, calculating them the first time only.

    The "global" keyword tells Python that we intend to modify the variable
    defined outside this function, rather than creating a new local one.
    """
    global _reference_embeddings
    if _reference_embeddings is None:
        _reference_embeddings = embed_texts(DOMAIN_REFERENCE_EXAMPLES)
    return _reference_embeddings


def check_by_similarity(message: str) -> GuardrailDecision:
    """
    Decide whether a message is on topic by comparing its meaning to the domain.

    Unlike Check 1, this one always returns a decision. It is the final word.

    np.max() picks the highest score. np.argmax() gives the POSITION of that
    highest score, which we use to look up which reference example was the
    closest match -- useful in the logs when explaining a decision.
    """
    message_embedding = embed_texts([message])[0]
    scores = cosine_similarity(message_embedding, get_reference_embeddings())

    best_score = float(np.max(scores))
    closest_example = DOMAIN_REFERENCE_EXAMPLES[int(np.argmax(scores))]

    if best_score >= SIMILARITY_THRESHOLD:
        return GuardrailDecision(
            verdict=ALLOW,
            check="similarity",
            reason=f"close in meaning to: '{closest_example}'",
            score=best_score,
        )

    return GuardrailDecision(
        verdict=BLOCK,
        check="similarity",
        reason="not close to anything in our domain",
        score=best_score,
    )


# ==============================================================================
# SECTION 5 - PUTTING IT TOGETHER
# ==============================================================================

REFUSAL_MESSAGE = (
    "I can only help with questions about your mutual fund investments -- "
    "things like NAV, SIPs, redemptions, statements and scheme details."
)


def check_topic(message: str) -> GuardrailDecision:
    """
    Run the full topic guardrail on a message.

        empty message      ->  block straight away
        keyword found      ->  allow, and skip the API call entirely
        otherwise          ->  let the similarity check decide
    """
    if not message.strip():
        return GuardrailDecision(BLOCK, "input", "message is empty")

    keyword_decision = check_by_keywords(message)
    if keyword_decision is not None:
        return keyword_decision

    return check_by_similarity(message)


def handle_message(message: str) -> str:
    """
    What the application actually calls.

    A blocked message never reaches the main model at all. It gets a fixed
    refusal that we wrote ourselves, not one the model generated. That keeps the
    wording consistent and costs nothing.
    """
    decision = check_topic(message)

    if decision.verdict == BLOCK:
        # In a real system, this is where we would write the block to our logs:
        # the message, the check, the score, the time. Those logs are the only
        # evidence we will have when adjusting the threshold later.
        return REFUSAL_MESSAGE

    return "[allowed -- this message would now go to the main model]"


# ==============================================================================
# SECTION 6 - RUNNING IT
# ==============================================================================

SAMPLE_MESSAGES = [
    # Obvious fund vocabulary. Check 1 handles these with no API call.
    "What is today's NAV for the flexi cap scheme?",
    "How do I pause my SIP for two months?",

    # Clearly about mutual funds, but not one of our keywords appears.
    # Check 1 has nothing to say; Check 2 understands the meaning.
    "If I invest 5,000 every month for 10 years, what will I end up with?",
    "My money still hasn't reached my bank account after I sold.",

    # Nothing to do with us.
    "What is a good recipe for paneer butter masala?",
    "Which laptop should I buy this year?",

    # Financial, but outside what a fund house assistant should answer.
    "Should I buy Reliance shares right now?",
]


def main() -> None:
    print("=" * 78)
    print("TOPIC GUARDRAIL - MUTUAL FUND ASSISTANT")
    print("=" * 78)

    for message in SAMPLE_MESSAGES:
        decision = check_topic(message)

        score_text = f"{decision.score:.3f}" if decision.score is not None else "  -  "
        print(f"\n  {decision.verdict.upper():5}  score {score_text}  "
              f"via {decision.check}")
        print(f"         {message}")
        print(f"         {decision.reason}")

    print("\n" + "=" * 78)
    print("WHAT THE CUSTOMER SEES")
    print("=" * 78)

    for message in ["How do I pause my SIP for two months?",
                    "Which laptop should I buy this year?"]:
        print(f"\n  USER: {message}")
        print(f"  BOT : {handle_message(message)}")


if __name__ == "__main__":
    main()