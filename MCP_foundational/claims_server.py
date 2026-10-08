##############################################################################
# claims_server.py
#
# PURPOSE:
#   This file is the MCP SERVER. It takes the claim-lookup function from
#   claims_data.py and offers it to an AI as a "tool" the AI can call.
#   This is the ANSWERING side of MCP: it waits to be asked, and answers.
#
# WHY WE NEED THIS:
#   claims_data.py knows every claim's status, but an AI has no way to
#   reach it. This file is the bridge. Once it is running and connected to
#   an AI app, a person can ask "what's the status of claim CLM-4471?" and
#   the AI will:
#       1. understand the question and pull out the claim ID,
#       2. call our tool with that ID,
#       3. take the exact record our claims data returns,
#       4. reply in a clear, friendly sentence.
#   Crucially, the AI CANNOT answer without us -- a claim's status exists
#   nowhere else. That is what makes this a real MCP use case, not a toy.
#
# HOW MCP WORKS HERE:
#   We use FastMCP from the official MCP Python SDK. We only do two things:
#       1. create a server:            mcp = FastMCP("claims-assistant")
#       2. mark a function as a tool:  @mcp.tool()
#   FastMCP reads the function's type hints (to know its inputs) and its
#   DOCSTRING (to describe the tool). That docstring is the text the AI
#   reads to decide WHETHER and HOW to use the tool -- so it is part of the
#   engineering, not a comment.
#
# HOW TO RUN / TEST IT ON ITS OWN:
#   A server just waits for a client, so running it alone shows nothing.
#   To see it work, connect a client. The quickest client is the MCP
#   Inspector (it launches the server for you):
#
#       npx @modelcontextprotocol/inspector python3 claims_server.py
#
#   (Do NOT use "mcp dev claims_server.py" unless you have uv installed -- on a
#   plain pip setup it fails. The npx command above launches with python3
#   directly and avoids that.)
#
#   In the Inspector: Connect -> Tools tab -> List Tools -> click
#   get_claim_status -> enter a claim ID -> Run Tool.
#
# NEXT:
#   In Stage 3 we replace the Inspector with our OWN client (client.py),
#   so we can see in code exactly what a client does.
##############################################################################


from mcp.server.fastmcp import FastMCP

# The server contains no claims data of its own -- it only exposes the
# tool. The knowledge lives in claims_data.py. We import the data lookup
# under a clear alias so it never clashes with our tool's name below.
from claims_data import get_claim_status as look_up_claim


# -------------------------------------------------------------
# CREATE THE SERVER
# -------------------------------------------------------------

mcp = FastMCP("claims-assistant")


# -------------------------------------------------------------
# DEFINE THE TOOL
# -------------------------------------------------------------
#
# The @mcp.tool() line turns an ordinary function into something the AI is
# allowed to call. Everything below it is a normal Python function whose
# only job is to hand the claim ID to our data lookup and return the result.

@mcp.tool()
def get_claim_status(claim_id: str) -> dict:
    """
    Looks up the current status and details of an insurance claim.

    Use this whenever someone asks about a claim -- its status, whether it
    is approved, rejected, or paid, how much was claimed, or how much was
    approved. You do not know this information yourself; it lives only in
    the insurer's claims system. Always use this tool to answer such
    questions rather than guessing.

    Args:
        claim_id: The claim's ID to look up (for example, "CLM-4471").

    Returns:
        A record with the policy holder, claim type, status, claimed
        amount, approved amount (which may be empty if no decision has
        been made yet), and a note explaining the current situation. If
        the claim ID is not found, it returns a result marked as not
        found, so you can say so honestly instead of inventing an answer.
    """
    return look_up_claim(claim_id)


# -------------------------------------------------------------
# START THE SERVER
# -------------------------------------------------------------
#
# mcp.run() starts the server using stdio transport (the default) -- the
# same transport the Inspector and, later, our own client will use.

if __name__ == "__main__":
    mcp.run()