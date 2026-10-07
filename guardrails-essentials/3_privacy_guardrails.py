"""
================================================================================
PRIVACY GUARDRAILS
================================================================================

THE PROBLEM
-----------
The previous two guardrails checked messages going IN. This one checks what
comes OUT.

A mutual fund assistant sits on top of folio records, KYC files and transaction
history. Sooner or later it will include something in an answer that should not
have been shown: a PAN number pulled from a document, a bank account number
copied out of a statement, an email address belonging to a different customer.

The model is not being malicious when this happens. It has no concept of
sensitive data at all -- it is repeating text that looked relevant. Deciding
what must not be shown is our job, not the model's.

BLOCK OR REDACT?
----------------
The obvious response is to refuse the whole answer. That is usually the wrong
call.

Consider: "Your redemption of 4,200 units has been processed and credited to
account 50100234567891." Almost all of that is exactly what the customer asked
for. Throwing it away because of one number at the end helps nobody.

So we have two possible actions, and choosing between them is the heart of this
file:

    REDACT   Keep the answer, hide the sensitive part.
             Used when the answer is useful and the exposure is small.
             "credited to account XXXXXXX7891"

    BLOCK    Throw the whole answer away.
             Used when the presence of the data is itself the problem, and
             hiding it would not fix anything.

The dividing line we use here: is this the customer's OWN data, shown back to
them? Then redact -- partial masking is enough. Is it an identifier that should
never appear in a chat window at all, such as an Aadhaar number, or data that
appears to belong to someone else? Then block.

WHY THIS ONE USES NO AI
-----------------------
Both checks in this file are plain pattern matching. There is no model call
anywhere, and that is deliberate.

The formats are fixed and known. A PAN is always five letters, four digits, one
letter. A regular expression matches that pattern every single time, in under a
millisecond, for free. A model would be slower, cost money, and occasionally
miss one.

You do not want a model DECIDING whether to hide an account number. You want a
rule that always does.

HOW TO RUN
----------
    python privacy_guardrails.py        (no API key needed)

================================================================================
"""

import re
from dataclasses import dataclass, field
from typing import List, Tuple


# ==============================================================================
# SECTION 1 - WHAT COUNTS AS SENSITIVE
# ==============================================================================
# Each entry describes one kind of sensitive data:
#
#     name        what we call it in the logs
#     pattern     the regular expression that finds it
#     action      "redact" or "block"
#     mask        how to disguise it, for the redact cases
#
# Writing the action into the table, rather than into the code that uses it,
# means changing a policy decision is a one-word edit. If the compliance team
# decides tomorrow that phone numbers must be blocked rather than masked, nobody
# has to touch any logic.
# ==============================================================================

@dataclass
class SensitivePattern:
    """
    One category of sensitive data and what to do about it.

    ABOUT @dataclass
    ----------------
    This decorator makes Python write the __init__ method for us. We just list
    the fields and their types below, and we can then create one by writing:

        SensitivePattern(name="pan", pattern=r"...", action="redact")
    """
    name: str
    pattern: str
    action: str          # "redact" or "block"
    description: str


REDACT = "redact"
BLOCK = "block"


SENSITIVE_PATTERNS = [
    # PAN: five letters, four digits, one letter. e.g. ABCDE1234F
    # The customer's own PAN, partially masked, is standard practice on
    # statements, so masking is enough here.
    SensitivePattern(
        name="pan",
        pattern=r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
        action=REDACT,
        description="PAN number",
    ),

    # Aadhaar: twelve digits, often written in groups of four.
    # This one is blocked outright, not masked. Aadhaar numbers should not be
    # travelling through a chat interface at all, so the presence of one means
    # something upstream has gone wrong and the answer must not be sent.
    SensitivePattern(
        name="aadhaar",
        pattern=r"\b[0-9]{4}[\s-]?[0-9]{4}[\s-]?[0-9]{4}\b",
        action=BLOCK,
        description="Aadhaar number",
    ),

    # Indian mobile: starts 6-9, ten digits, with an optional +91.
    #
    # ORDER MATTERS HERE. This entry sits ABOVE bank_account deliberately.
    #
    # A mobile number is ten digits, and the bank account pattern below accepts
    # anything from nine to eighteen digits -- so a mobile number also matches
    # the account pattern. Whichever pattern runs first claims the value.
    #
    # With the order reversed, every mobile number in every answer would be
    # logged as a bank account. The masking would still happen, so nothing would
    # look broken on screen, but the logs would be quietly wrong. That is the
    # worst kind of bug: invisible until someone tries to use the data.
    #
    # The general rule: when two patterns can match the same text, the more
    # specific one goes first.
    SensitivePattern(
        name="phone",
        pattern=r"\b(?:\+?91[\s-]?)?[6-9][0-9]{9}\b",
        action=REDACT,
        description="mobile number",
    ),

    # Bank account: 9 to 18 digits. Broadest of the numeric patterns, so it runs
    # after the narrower ones above.
    SensitivePattern(
        name="bank_account",
        pattern=r"\b[0-9]{9,18}\b",
        action=REDACT,
        description="bank account number",
    ),

    SensitivePattern(
        name="email",
        pattern=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        action=REDACT,
        description="email address",
    ),

    # IFSC: four letters, a zero, then six characters.
    # Not sensitive on its own -- it identifies a branch, not a person -- but it
    # is included because an IFSC beside an account number completes a payable
    # set of details.
    SensitivePattern(
        name="ifsc",
        pattern=r"\b[A-Z]{4}0[A-Z0-9]{6}\b",
        action=REDACT,
        description="IFSC code",
    ),
]


# ==============================================================================
# SECTION 2 - THE DECISION OBJECT
# ==============================================================================

@dataclass
class PrivacyDecision:
    """
    The result of checking one answer for sensitive data.

    action        "allow", "redact" or "block".
    text          What should actually be sent to the customer. For a redaction
                  this is the cleaned answer; for a block it is empty.
    found         Which categories were detected, for the logs.

    ABOUT field(default_factory=list)
    ---------------------------------
    We cannot write "found: List[str] = []" as a default. In Python, a default
    value is created once when the class is defined, so every object would end
    up sharing the SAME list, and appending to one would change them all.

    default_factory=list tells the dataclass to call list() afresh each time an
    object is created, giving every object its own empty list. This is a classic
    Python trap and worth recognising.
    """
    action: str
    text: str
    found: List[str] = field(default_factory=list)


ALLOW = "allow"


# ==============================================================================
# SECTION 3 - MASKING
# ==============================================================================
# How we disguise a value we have decided to keep.
#
# We do not replace the whole thing with [HIDDEN]. We keep the last four
# characters: XXXXXXX7891.
#
# That is a deliberate compromise. The customer recognises their own account
# from the last four digits, which is how every bank statement and card receipt
# in the world works. Anyone reading over their shoulder learns nothing useful.
#
# Full replacement would be more secure and considerably more annoying -- the
# customer would have no way to tell which of their three accounts we meant.
# ==============================================================================

def mask_value(value: str, visible_characters: int = 4) -> str:
    """
    Replace all but the last few characters with X.

    Examples:
        50100234567891  ->  XXXXXXXXXX7891
        ABCDE1234F      ->  XXXXXX234F

    Short values are masked completely, because keeping four characters of a
    five-character value would reveal almost all of it.
    """
    if len(value) <= visible_characters:
        return "X" * len(value)

    hidden_count = len(value) - visible_characters
    return "X" * hidden_count + value[-visible_characters:]


# ==============================================================================
# SECTION 4 - THE CHECK
# ==============================================================================

def check_privacy(answer: str) -> PrivacyDecision:
    """
    Scan an answer for sensitive data and decide what to do with it.

    The order of work matters here:

      1. Look for everything marked BLOCK first. If any is present, we stop
         immediately -- there is no point carefully masking phone numbers in an
         answer we are about to discard.

      2. Then work through everything marked REDACT, replacing each match with
         its masked version.

    ABOUT re.finditer
    -----------------
    re.search finds the first match. re.finditer finds every match and lets us
    loop over them. We need every match, because an answer might contain three
    account numbers and masking only the first would be worse than useless.

    ABOUT set()
    -----------
    We collect matches into a set before replacing. A set automatically discards
    duplicates, so if the same account number appears four times in the answer,
    we perform the replacement once rather than four times over.
    """
    found_categories = []

    # --- Step 1: anything that forces a block -------------------------------
    for entry in SENSITIVE_PATTERNS:
        if entry.action != BLOCK:
            continue

        if re.search(entry.pattern, answer):
            return PrivacyDecision(
                action=BLOCK,
                text="",
                found=[entry.name],
            )

    # --- Step 2: mask everything else ---------------------------------------
    cleaned = answer

    for entry in SENSITIVE_PATTERNS:
        if entry.action != REDACT:
            continue

        matches = set(match.group() for match in re.finditer(entry.pattern, cleaned))

        if matches:
            found_categories.append(entry.name)

        for value in matches:
            cleaned = cleaned.replace(value, mask_value(value))

    if not found_categories:
        return PrivacyDecision(action=ALLOW, text=answer)

    return PrivacyDecision(action=REDACT, text=cleaned, found=found_categories)


# ==============================================================================
# SECTION 5 - PUTTING IT TOGETHER
# ==============================================================================

BLOCK_MESSAGE = (
    "I'm not able to display that information here. Please check your statement "
    "in the portal, or contact our support team for help."
)


def handle_answer(answer: str) -> str:
    """
    What the application calls after the model has written its answer, and
    before the customer sees anything.

    This is the last gate. Whatever this function returns is what appears on
    screen.
    """
    decision = check_privacy(answer)

    if decision.action == BLOCK:
        # A block here means sensitive data reached the model's answer, which
        # points at a problem further upstream -- probably a document that should
        # never have been in the retrievable set. This log line is how that gets
        # discovered.
        return BLOCK_MESSAGE

    return decision.text


# ==============================================================================
# SECTION 6 - RUNNING IT
# ==============================================================================
# These are model answers, not user messages. That is the difference between an
# input guardrail and an output guardrail, and it is worth keeping straight: by
# the time this code runs, the model has already done its work.
# ==============================================================================

SAMPLE_ANSWERS = [
    # Clean. Nothing to do.
    "Your SIP of 5,000 rupees is scheduled for the 5th of every month. "
    "The next instalment is due on 5 September.",

    # A useful answer with one account number in it. Masking keeps the answer.
    "Your redemption of 4,200 units has been processed and the amount will be "
    "credited to account 50100234567891 within 3 working days.",

    # Several categories at once.
    "I've found your folio. The registered email is ravi.kumar@example.com, "
    "the mobile number is 9876543210, and the PAN on record is ABCDE1234F.",

    # An Aadhaar number. Masking is not enough -- the whole answer is discarded.
    "Your KYC record shows Aadhaar 2345 6789 0123 verified on 12 March 2024.",

    # The same account number repeated. It should be masked everywhere, and the
    # replacement should happen once, not three times.
    "Account 50100234567891 was debited on Monday. Account 50100234567891 was "
    "credited on Tuesday. Please confirm account 50100234567891 is correct.",
]


def main() -> None:
    print("=" * 78)
    print("PRIVACY GUARDRAIL - MUTUAL FUND ASSISTANT")
    print("=" * 78)

    for answer in SAMPLE_ANSWERS:
        decision = check_privacy(answer)

        found = ", ".join(decision.found) if decision.found else "nothing"
        print(f"\n  {decision.action.upper():6}  found: {found}")
        print(f"  BEFORE  {answer[:100]}")

        if decision.action == BLOCK:
            print(f"  AFTER   [answer discarded]")
        else:
            print(f"  AFTER   {decision.text[:100]}")

    print("\n" + "=" * 78)
    print("WHAT THE CUSTOMER SEES")
    print("=" * 78)

    for answer in [SAMPLE_ANSWERS[1], SAMPLE_ANSWERS[3]]:
        print(f"\n  MODEL WROTE : {answer[:80]}")
        print(f"  CUSTOMER SEES: {handle_answer(answer)[:80]}")


if __name__ == "__main__":
    main()