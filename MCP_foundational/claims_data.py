##############################################################################
# claims_data.py
#
# PURPOSE:
#   This file pretends to be the insurer's internal claims system. It stores
#   a handful of motor-insurance claims and can look up the full status of
#   any one of them by its claim ID.
#
# WHY WE NEED THIS (this is the whole point of the example):
#   An AI model knows a lot about the world, but it knows NOTHING about our
#   claims. It cannot possibly know whether claim CLM-4471 was approved, or
#   for how much — that fact lives only here, in our own records. This file
#   is that private knowledge.
#
#   Later, we let an AI reach this data through an MCP tool. The AI has no
#   choice but to ask us, because there is no other way for it to know a
#   claim's status. That is exactly when MCP earns its place: connecting a
#   model to information it could never have on its own.
#
# WHAT IS AND ISN'T HERE:
#   In a real insurer this data lives in a large claims system behind a
#   login. To keep this first example simple — no database, no passwords,
#   no internet — we use a plain Python dictionary. The idea is identical;
#   only the storage is simpler. All names and claim IDs below are made up.
#
# A NOTE ON THE FIELDS:
#   Some fields are only filled in once a claim reaches a certain stage.
#   For example, "approved_amount" is None (empty) while a claim is still
#   under review, and only gets a value once a decision is made. This is
#   realistic, and it teaches that a tool's answer can legitimately contain
#   "not decided yet" rather than a number.
#
# SHOULD YOU RUN THIS FILE DIRECTLY?
#   Yes, to check it works. There is a small demo at the bottom that runs
#   when you execute:  python3 claims_data.py
#   In normal use, server.py imports this file instead of running it.
#
# HOW OTHER FILES USE THIS:
#   from claims_data import get_claim_status
#
#   result = get_claim_status("CLM-4471")
##############################################################################


# ─────────────────────────────────────────────────────────────
# THE PRETEND CLAIMS SYSTEM
# ─────────────────────────────────────────────────────────────
#
# Each claim has a status somewhere along its life:
#   Submitted -> Under Review -> Approved (or Rejected) -> Paid
# Claim IDs are stored in upper case so we can match them regardless of
# how the user types them.

CLAIM_RECORDS = {
    "CLM-4471": {
        "policy_holder":   "Rahul Deshpande",
        "claim_type":      "Motor - Accident",
        "status":          "Approved",
        "claim_amount":    85000,
        "approved_amount": 72000,
        "note":            "Approved after garage inspection. "
                           "Policy excess of Rs.13,000 applied.",
    },
    "CLM-5522": {
        "policy_holder":   "Sana Qureshi",
        "claim_type":      "Motor - Own Damage",
        "status":          "Under Review",
        "claim_amount":    46000,
        "approved_amount": None,  # not decided yet
        "note":            "Awaiting surveyor report before a decision.",
    },
    "CLM-6033": {
        "policy_holder":   "Vikram Nair",
        "claim_type":      "Motor - Theft",
        "status":          "Rejected",
        "claim_amount":    310000,
        "approved_amount": 0,
        "note":            "Rejected: theft reported to insurer 21 days "
                           "after incident, beyond the policy limit.",
    },
    "CLM-7180": {
        "policy_holder":   "Ananya Rao",
        "claim_type":      "Motor - Accident",
        "status":          "Paid",
        "claim_amount":    40000,
        "approved_amount": 40000,
        "note":            "Settled in full. Amount credited to the "
                           "registered bank account.",
    },
    "CLM-8890": {
        "policy_holder":   "Imran Sheikh",
        "claim_type":      "Motor - Own Damage",
        "status":          "Submitted",
        "claim_amount":    58000,
        "approved_amount": None,  # not decided yet
        "note":            "Claim received. Documents pending verification.",
    },
}


# ─────────────────────────────────────────────────────────────
# THE LOOKUP FUNCTION
# ─────────────────────────────────────────────────────────────

def get_claim_status(claim_id: str) -> dict:
    """
    Looks up the full status of one insurance claim by its claim ID.

    Args:
        claim_id: The claim's ID, in any capitalisation
                  (for example "CLM-4471" or "clm-4471").

    Returns:
        A dictionary describing the result.

        If the claim is found:
            {
                "found": True,
                "claim_id": "CLM-4471",
                "policy_holder": "Rahul Deshpande",
                "claim_type": "Motor - Accident",
                "status": "Approved",
                "claim_amount": 85000,
                "approved_amount": 72000,     # may be None if not decided
                "note": "..."
            }

        If the claim is NOT found (so the caller — and later, the AI — is
        told clearly rather than being given a wrong answer):
            {
                "found": False,
                "claim_id": "whatever was searched for"
            }
    """

    lookup_key = claim_id.strip().upper()
    record     = CLAIM_RECORDS.get(lookup_key)

    if record is None:
        return {
            "found":    False,
            "claim_id": claim_id,
        }

    return {
        "found":           True,
        "claim_id":        lookup_key,
        "policy_holder":   record["policy_holder"],
        "claim_type":      record["claim_type"],
        "status":          record["status"],
        "claim_amount":    record["claim_amount"],
        "approved_amount": record["approved_amount"],
        "note":            record["note"],
    }


# ─────────────────────────────────────────────────────────────
# QUICK DEMO — runs only if you execute this file directly
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    for cid in ["CLM-4471", "CLM-5522", "CLM-6033", "CLM-9999"]:
        print(f"Looking up: {cid}")
        print(f"  {get_claim_status(cid)}")
        print()