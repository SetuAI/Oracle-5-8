"""
================================================================================
FORMAT GUARDRAILS
================================================================================

THE PROBLEM
-----------
So far our guardrails have decided whether text is acceptable. This one asks a
different question:

    Is this answer in the SHAPE we asked for?

Whenever a model's output feeds into other code rather than into a human's eyes,
shape becomes critical. Suppose our mutual fund assistant extracts structured
details from a scheme document so they can be displayed in a table:

    {"scheme_name": "...", "nav": 48.21, "expense_ratio": 0.65, ...}

The model will usually produce exactly that. Occasionally it will produce:

    - the same JSON wrapped in ```json code fences
    - a helpful sentence before the JSON: "Here are the details you asked for:"
    - "expense_ratio": "0.65%"   -- a string with a symbol, not a number
    - "nav": 4821                -- a number, but a wrong one
    - a missing field

Every one of these crashes the code downstream, or worse, quietly puts wrong
numbers on a customer's screen.

A DIFFERENT KIND OF ACTION
--------------------------
The earlier guardrails could block or redact. This one introduces a third
action: RETRY.

If the answer is the wrong shape, we do not have to refuse the customer. We can
hand the answer back to the model along with a description of exactly what was
wrong, and ask again. Models are generally good at fixing a specific, named
mistake -- far better than they are at avoiding it in the first place.

So the flow is: ask -> validate -> if invalid, explain the error and ask again.
We allow a small number of attempts and then give up, because a model that has
failed twice with clear feedback is unlikely to succeed on the fifth try, and
each attempt costs money and time.

THE APPROACH
------------
    Check 1   Can it be read as JSON at all?      cheap, catches fences and prose
    Check 2   Does it match our required shape?   catches missing and wrong fields

We use Pydantic for Check 2. Pydantic lets us describe the shape we want as a
Python class, and then checks any data against it, producing precise error
messages we can feed back to the model.

HOW TO RUN
----------
    pip install openai pydantic python-dotenv
    export OPENAI_API_KEY="sk-..."
    python format_guardrails.py

================================================================================
"""

import json
import os
import re
from typing import Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

load_dotenv()


# ==============================================================================
# SECTION 0 - CONFIGURATION
# ==============================================================================

MODEL = "gpt-4o-mini"

# How many times we are willing to ask the model to fix its own output.
#
# Two is a considered number, not a guess. The first retry catches genuine slips,
# which is the common case. Beyond that the failure is usually caused by our
# prompt or our schema being unclear, and asking a third time just spends money
# repeating the same misunderstanding.
MAX_ATTEMPTS = 3

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ==============================================================================
# SECTION 1 - DESCRIBING THE SHAPE WE WANT
# ==============================================================================
# This class IS our format guardrail. Everything below it is machinery for
# applying it.
#
# ABOUT BaseModel
# ---------------
# A normal Python class will accept anything you put in it. If you write
# fund.nav = "not a number", Python shrugs and stores the string.
#
# A class inheriting from Pydantic's BaseModel does not. It checks every value
# against the declared type when the object is created, and refuses anything that
# does not fit. That refusal is what we want -- it is the guardrail firing.
#
# ABOUT Field(...)
# ----------------
# Field lets us attach rules and descriptions to individual fields.
#
#   ge=0        "greater than or equal to 0"
#   le=100      "less than or equal to 100"
#   description  human-readable text, which we can feed to the model so it knows
#                what each field means without us writing the explanation twice
#
# The ge and le rules matter more than they look. A model asked for an expense
# ratio will occasionally return 65 when it means 0.65. Both are valid numbers,
# so a type check alone would accept it and put a 65% fee on a customer's screen.
# A range rule catches it.
# ==============================================================================

class SchemeDetails(BaseModel):
    """The structured details we want extracted from a scheme document."""

    scheme_name: str = Field(
        description="Full name of the mutual fund scheme"
    )
    category: str = Field(
        description="Scheme category, for example Large Cap or Liquid"
    )
    nav: float = Field(
        gt=0,
        description="Net asset value per unit in rupees"
    )
    expense_ratio: float = Field(
        ge=0, le=5,
        description="Annual expense ratio as a percentage, for example 0.65"
    )
    minimum_investment: int = Field(
        gt=0,
        description="Minimum lump sum investment in rupees"
    )
    exit_load_percent: float = Field(
        ge=0, le=10,
        description="Exit load as a percentage, 0 if there is none"
    )


# ==============================================================================
# SECTION 2 - CHECK 1: CAN WE READ IT AS JSON?
# ==============================================================================
# Before we can check the shape of the data, we have to get the data out of the
# model's reply. This is more fiddly than it should be, because models like to be
# helpful.
#
# A model asked for JSON very often returns:
#
#     Here are the scheme details you requested:
#     ```json
#     {"scheme_name": "..."}
#     ```
#     Let me know if you need anything else!
#
# All of that is well-intentioned and all of it breaks json.loads(). So we
# extract the JSON object before attempting to read it.
# ==============================================================================

def extract_json(text: str) -> Tuple[Optional[dict], Optional[str]]:
    """
    Pull a JSON object out of the model's reply.

    Returns a pair: (the data, an error message). Exactly one of the two will be
    filled in -- if the data is there, the error is None, and the other way
    round. Returning both together is a common Python pattern for "this might
    fail, and if it does I want to know why".

    ABOUT THE REGEX
    ---------------
    \\{.*\\}       find a { followed later by a }
    re.DOTALL     by default, the dot does not match newline characters, so a
                  JSON object spread over several lines would not be found. This
                  flag makes the dot match newlines too.

    We deliberately match from the FIRST { to the LAST }, so any prose before or
    after is discarded.
    """
    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        return None, "no JSON object found in the response"

    try:
        return json.loads(match.group()), None
    except json.JSONDecodeError as error:
        # A common cause is a trailing comma, which Python's JSON reader rejects.
        return None, f"the JSON could not be parsed: {error.msg}"


# ==============================================================================
# SECTION 3 - CHECK 2: DOES IT MATCH OUR SHAPE?
# ==============================================================================

def validate_shape(data: dict) -> Tuple[Optional[SchemeDetails], Optional[str]]:
    """
    Check the data against the SchemeDetails class.

    Returns (validated object, error message), with exactly one filled in.

    ABOUT ValidationError
    ---------------------
    When Pydantic rejects data it raises a ValidationError containing a list of
    every problem it found -- not just the first one. That completeness is the
    reason we bother: telling the model about all three of its mistakes at once
    means one retry instead of three.

    The loop below turns that list into a plain-English summary. Pydantic's raw
    error output is detailed but noisy, and a cleaner message gets a better
    correction out of the model.
    """
    try:
        return SchemeDetails(**data), None

    except ValidationError as error:
        problems = []

        for issue in error.errors():
            # issue["loc"] is the path to the offending field, as a tuple.
            # For a simple flat object it holds one item, the field name.
            field_name = ".".join(str(part) for part in issue["loc"])
            problems.append(f"'{field_name}': {issue['msg']}")

        return None, "; ".join(problems)


# ==============================================================================
# SECTION 4 - THE RETRY LOOP
# ==============================================================================
# Where the two checks come together with the model.
#
# The important idea: when validation fails, we do not just try again. We tell
# the model precisely what was wrong and include its own previous answer.
#
# Asking again with the identical prompt would very likely produce the identical
# mistake. Asking again with "your last answer was missing 'category' and
# 'expense_ratio' was 65 which exceeds the maximum of 5" gives the model
# something specific to correct.
# ==============================================================================

EXTRACTION_PROMPT = """Extract the scheme details from the document below.

Respond with a single JSON object and nothing else. No explanation, no code
fences, no text before or after.
Required fields:
- scheme_name        (text)  full name of the scheme
- category           (text)  for example Large Cap, Liquid, ELSS
- nav                (number) net asset value per unit in rupees
- expense_ratio      (number) annual expense ratio as a percentage, e.g. 0.65
- minimum_investment (whole number) minimum lump sum in rupees
- exit_load_percent  (number) exit load percentage, 0 if none

DOCUMENT:
{document}"""


def extract_scheme_details(document: str, verbose: bool = True) -> Optional[SchemeDetails]:
    """
    Ask the model for structured details, validating and retrying as needed.

    Returns the validated object, or None if every attempt failed.

    The conversation list grows as we go. On the first attempt it holds only our
    request. On a retry it also holds the model's failed answer and our
    correction, so the model can see its own mistake in context.
    """
    conversation = [
        {"role": "user", "content": EXTRACTION_PROMPT.format(document=document)}
    ]

    for attempt in range(1, MAX_ATTEMPTS + 1):

        response = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            messages=conversation,
        )
        raw_reply = response.choices[0].message.content

        if verbose:
            print(f"\n    attempt {attempt}: {raw_reply[:90]}")

        # --- Check 1 --------------------------------------------------------
        data, parse_error = extract_json(raw_reply)

        if parse_error:
            if verbose:
                print(f"      check 1 FAILED: {parse_error}")
            conversation.append({"role": "assistant", "content": raw_reply})
            conversation.append({
                "role": "user",
                "content": f"That response could not be read as JSON: {parse_error}. "
                           f"Reply with only the JSON object, nothing else.",
            })
            continue

        # --- Check 2 --------------------------------------------------------
        validated, shape_error = validate_shape(data)

        if shape_error:
            if verbose:
                print(f"      check 2 FAILED: {shape_error}")
            conversation.append({"role": "assistant", "content": raw_reply})
            conversation.append({
                "role": "user",
                "content": f"That JSON had these problems: {shape_error}. "
                           f"Send a corrected JSON object with all fields present "
                           f"and within their allowed ranges.",
            })
            continue

        # --- Both checks passed ---------------------------------------------
        if verbose:
            print(f"      both checks PASSED")
        return validated

    if verbose:
        print(f"      gave up after {MAX_ATTEMPTS} attempts")
    return None


# ==============================================================================
# SECTION 5 - SEEING THE CHECKS WORK WITHOUT AN API CALL
# ==============================================================================
# The retry loop needs a live model. The two checks themselves do not, so we can
# feed them the badly-formed replies that models actually produce and watch what
# each check says.
# ==============================================================================

BROKEN_REPLIES = [
    # Wrapped in code fences with a friendly sentence attached.
    ('Here are the details you asked for:\n```json\n'
     '{"scheme_name": "Bluechip Growth Fund", "category": "Large Cap", '
     '"nav": 48.21, "expense_ratio": 0.65, "minimum_investment": 5000, '
     '"exit_load_percent": 1.0}\n```\nLet me know if you need anything else!'),

    # A trailing comma, which JSON does not allow.
    ('{"scheme_name": "Bluechip Growth Fund", "category": "Large Cap", '
     '"nav": 48.21, "expense_ratio": 0.65, "minimum_investment": 5000, '
     '"exit_load_percent": 1.0,}'),

    # Two fields missing.
    ('{"scheme_name": "Bluechip Growth Fund", "nav": 48.21, '
     '"minimum_investment": 5000}'),

    # The percentage mistake: 65 instead of 0.65. Valid JSON, valid type,
    # completely wrong value. Only the range rule catches this.
    ('{"scheme_name": "Bluechip Growth Fund", "category": "Large Cap", '
     '"nav": 48.21, "expense_ratio": 65, "minimum_investment": 5000, '
     '"exit_load_percent": 1.0}'),

    # A number sent as text with a symbol attached.
    ('{"scheme_name": "Bluechip Growth Fund", "category": "Large Cap", '
     '"nav": "Rs 48.21", "expense_ratio": 0.65, "minimum_investment": 5000, '
     '"exit_load_percent": 1.0}'),

    # Correct.
    ('{"scheme_name": "Bluechip Growth Fund", "category": "Large Cap", '
     '"nav": 48.21, "expense_ratio": 0.65, "minimum_investment": 5000, '
     '"exit_load_percent": 1.0}'),
]


def demonstrate_checks() -> None:
    """Run both checks against replies a model might realistically produce."""
    print("=" * 78)
    print("THE TWO CHECKS, RUN AGAINST REALISTIC MODEL REPLIES")
    print("=" * 78)

    for reply in BROKEN_REPLIES:
        print(f"\n  REPLY   {reply[:78]}")

        data, parse_error = extract_json(reply)

        if parse_error:
            print(f"  RESULT  check 1 failed -- {parse_error}")
            continue

        validated, shape_error = validate_shape(data)

        if shape_error:
            print(f"  RESULT  check 2 failed -- {shape_error}")
            continue

        print(f"  RESULT  passed -- NAV {validated.nav}, "
              f"expense ratio {validated.expense_ratio}%")


SAMPLE_DOCUMENT = """
BLUECHIP GROWTH FUND - SCHEME INFORMATION

The Bluechip Growth Fund is an open-ended equity scheme in the Large Cap
category. As of 8 August 2026 the net asset value stood at Rs 48.21 per unit.

The total expense ratio for the direct plan is 0.65% per annum. Minimum lump sum
investment is Rs 5,000, and additional purchases may be made in multiples of
Rs 1,000. An exit load of 1% applies to units redeemed within 365 days of
allotment.
"""


def main() -> None:
    demonstrate_checks()

    print("\n" + "=" * 78)
    print("THE FULL LOOP, WITH A LIVE MODEL")
    print("=" * 78)
    print("\n  Extracting from the scheme document...")

    result = extract_scheme_details(SAMPLE_DOCUMENT)

    if result is None:
        print("\n  Extraction failed after all attempts.")
        return

    print(f"\n  {result.scheme_name} ({result.category})")
    print(f"    NAV                 Rs {result.nav}")
    print(f"    Expense ratio       {result.expense_ratio}%")
    print(f"    Minimum investment  Rs {result.minimum_investment}")
    print(f"    Exit load           {result.exit_load_percent}%")


if __name__ == "__main__":
    main()