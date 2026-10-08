# Claims Assistant — an MCP server

A tiny, self-contained project that teaches how MCP works, end to end, with
**no database, no API keys, and no internet**.

## The story

Meera runs the motor-claims desk at a general insurer. All day, agents and
customers ask her team the same thing: *"What's the status of my claim? Is
it approved? How much will I get?"* She wants an AI assistant that answers
instantly. But the AI has **no idea** whether claim CLM-4471 is approved —
that lives only in the claims system. So she gives the AI a tool to look it
up. That tool is the MCP server we build here.

## Why this example works

A claim's status is a fact the AI **cannot guess** — it exists only in our
records. So the AI has no choice but to call our tool. That is the real
reason MCP exists: to connect a model to knowledge it could never have on
its own.

## The two files (so far)

| File               | What it is                                                  | The lesson                                                |
| ------------------ | ----------------------------------------------------------- | --------------------------------------------------------- |
| `claims_data.py` | A plain Python "claims system" + a lookup function. No MCP. | *An MCP tool is, at heart, just a function.*            |
| `server.py`      | The MCP server that exposes that function as a tool.        | *MCP is the bridge that lets an AI call your function.* |

Keeping them separate is deliberate: the data (the **concept**) is one file,
the MCP wrapping (the **application**) is another.

---

# Project 1 : Claims Status MCP Server

Follow these steps in order. Each one confirms the layer beneath it before
adding the next — so if something breaks, you know exactly where.

## Step 1 — Install the MCP SDK

Python 3.10 or newer is required.

```bash
pip install "mcp[cli]"
```

## Step 2 — Check the data works (no MCP yet)

Run the plain lookup on its own first. This proves the claims data is
correct before we involve any AI.

```bash
python3 claims_data.py
```

You should see records printed for CLM-4471 (Approved), CLM-5522 (Under
Review), CLM-6033 (Rejected), and CLM-9999 (not found). If this fails, it
is a plain Python problem — fix it before touching MCP.

## Step 3 — Test the server with the MCP Inspector

The Inspector is a small web tool that connects to your server exactly like
a real AI app would — but shows you everything happening underneath. It IS a
client (the same role VS Code or Claude Desktop plays), just without an AI
model. Using it, *you* play the part of the AI: you pick the tool and type
the input by hand.

### Launch it

Run this from **inside the project folder** (where `server.py` lives):

```bash
npx @modelcontextprotocol/inspector python3 claims_server.py
```

> ⚠️ Do **not** use `mcp dev server.py` unless you have `uv` installed.
> On a plain `pip` setup, `mcp dev` tries to launch through `uv` and fails
> with a `SyntaxError: Unexpected token 'E'` error. The `npx` command above
> launches your server with `python3` directly and avoids this.

The terminal prints something like:

```
MCP Inspector is up and running at:
http://localhost:6274/?MCP_PROXY_AUTH_TOKEN=...
```

A browser tab opens automatically. If it does not, open the **full URL,
including the `?MCP_PROXY_AUTH_TOKEN=...` part** — that token is what lets
the page talk to the server. Leave the terminal running; that IS your server.

### In the browser — connect

1. On the left, confirm **Transport Type = STDIO**, **Command = `python3`**,
   **Arguments = ` claims_server.py`**. (The `npx` command fills these in for you.)
2. Click **Connect**.
3. The dot at the bottom-left should turn green and say **Connected**.

### In the browser — call the tool

1. Click the **Tools** tab in the top bar (the crossed-hammers icon).
2. Click **List Tools**. Your tool **`get_claim_status`** appears, with its
   description. *This is the client asking the server "what can you do?"*
3. Click the **`get_claim_status`** row (the one with the `>` arrow). An
   input box opens.
4. In **`claim_id`**, type: `CLM-4471`
5. Click **Run Tool**.

### What you should see

A green **Tool Result: Success** with output like:

```json
{
  "found": true,
  "claim_id": "CLM-4471",
  "policy_holder": "Rahul Deshpande",
  "claim_type": "Motor - Accident",
  "status": "Approved",
  "claim_amount": 85000,
  "approved_amount": 72000,
  "note": "Approved after garage inspection. Policy excess of Rs.13,000 applied."
}
```

This should match what `python3 claims_data.py` printed in Step 2. Same
data — now reachable over MCP. Your server is verified.

### Try a few more (to see the range)

| Type this claim_id | What it shows                                         | Why it matters                                                         |
| ------------------ | ----------------------------------------------------- | ---------------------------------------------------------------------- |
| `CLM-5522`       | Status "Under Review",`approved_amount` is `null` | A tool can honestly say "not decided yet"                              |
| `CLM-6033`       | Status "Rejected", with a reason in`note`           | Structured data carries context, not just a status                     |
| `CLM-9999`       | `found: false`                                      | A good tool admits what it doesn't know instead of inventing an answer |

> **Note on the Resources / Prompts tabs:** they will be empty. That is
> correct — this server exposes only a *tool*, not resources or prompts.

## What each part means (the three-beat conversation)

Everything you just did is MCP in three moves. Say it to students like this:

1. **"What can you do?"** — clicking *List Tools* is the client asking the
   server for its list of tools. Nobody hardcoded it; the client discovered
   it by asking.
2. **"Please do it."** — typing the claim ID and clicking *Run Tool* sends
   that input to the server and says "run your tool with this."
3. **"Here's the result."** — the green Success and the JSON is the server
   handing back an exact, trustworthy answer, because real data produced it.

## What to notice ?

1. **A tool is a function.** Step 2 runs the exact same lookup with no AI
   involved. The tool is just that function, made reachable.
2. **The AI cannot cheat here.** Unlike a maths question, the AI cannot
   guess a claim's status — so it is forced to use the tool. This is the
   clearest way to show *why* MCP matters: access to private knowledge.
3. **The description is the interface.** The text under `get_claim_status`
   in the Inspector is the docstring from `server.py` — the exact words the
   AI reads to decide when to use the tool. Change it to something vague,
   restart, and tool selection gets worse. In MCP the description is not a
   comment; it is instructions the model reads.
4. **A good tool tells the truth.** The `found: false` and the `null`
   approved amount show the tool being honest about what it doesn't know or
   hasn't decided — so the AI can say so instead of hallucinating.

---

## Troubleshooting

| Symptom                                         | Almost always means                                                                                    |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `python3 claims_data.py` errors               | Python issue — fix before touching MCP                                                                |
| `mcp dev` fails with `Unexpected token 'E'` | It launched via`uv`; use the `npx ... python3 server.py` command instead                           |
| Inspector**Connect** does nothing         | Opened the URL without the`?MCP_PROXY_AUTH_TOKEN=...` token — reopen the full URL from the terminal |
| `No module named 'mcp'` on launch             | The`mcp` package is in a different Python — run `python3 -m pip install "mcp[cli]"`               |
| Tools tab empty after Connect                   | Server didn't start — check the terminal for a Python error in`server.py`                           |

---

# Project 2 : Consuming a Market-Data Server We Didn't Build

In Project 1 we **built** an MCP server (the claims assistant).

In Project 2
we do the opposite and more powerful thing: we **consume** a server that a
company (Alpha Vantage) built and runs for us. We write no server code and
no client code — we just connect the hosts we already know to their server
and watch it work.

## The point of this project

This is the other half of the whole reason MCP exists. Project 1 showed
"anyone can build a server." Project 2 shows "any MCP host can use a server
someone else built, over one shared standard" — without writing a single
line of integration code. That is the M + N payoff made real.

It also introduces one genuinely new idea:

- **Project 1 transport = stdio** — a local server we launched on our own
  machine.
- **Project 2 transport = HTTP** — a remote server running on Alpha
  Vantage's machines, reached over a URL.

Same MCP, different transport. The tools, the "list tools", the "call tool"
— all identical. Only *where the server lives* changes.

## The story

Meera's claims desk is one thing. But her colleague Ravi runs an equity
research desk, and his team constantly needs live market data — quotes,
company fundamentals, currency rates. Ravi is NOT going to build and
maintain a server for all of that. Someone already did: Alpha Vantage
publishes an MCP server covering stocks, forex, crypto, fundamentals, and
economic indicators. Ravi just connects to it. That is when you consume
instead of build: when a good server already exists.

---

## Before you start — get a free API key

Alpha Vantage's server needs a free key (a ~30-second signup):

  https://www.alphavantage.co/support/#api-key

Keep the key handy. The remote server is reached at this URL, with your key
in it:

  https://mcp.alphavantage.co/mcp?apikey=YOUR_API_KEY

> Free tier: about 500 standard requests/day (plenty for a workshop). A few
> premium endpoints are limited to ~25/day.

---

## Part 1 — Explore their server with the MCP Inspector

Here we answer the question "what tools did they define?" the right way:
we don't read their docs — we let the client ask the server directly.

### Launch the Inspector

```bash
npx @modelcontextprotocol/inspector
```

(No `python3 claims_server.py` this time — there is no local server. We are
connecting to a remote one.)

### Connect to the remote server

In the Inspector's left panel:

1. **Transport Type:** change from STDIO to **Streamable HTTP** (or "HTTP").
2. **URL:** paste `https://mcp.alphavantage.co/mcp?apikey=YOUR_API_KEY`
   (with your real key).
3. Click **Connect**. The dot should turn green / Connected.

### Discover what they defined

1. Open the **Tools** tab.
2. Click **List Tools**.
3. Watch their whole catalogue appear — stock quotes, time series, company
   fundamentals, forex, crypto, economic indicators, and their consolidated
   technical-indicator tools.

**This is the moment of the project.** Nobody in the room wrote any of this.
The client simply asked the server "what can you do?" and the server
answered. That is exactly how an AI would discover these tools too.

### Call one by hand

1. Find a quote tool (e.g. the global quote / `GLOBAL_QUOTE` tool).
2. Click it, enter a symbol like `IBM`, and **Run Tool**.
3. You get back live market data — from a server running somewhere else
   entirely, through the same MCP mechanics you learned in Project 1.

---

## Part 2 — Let an AI use their server (VS Code, Agent mode)

Now we hand the "asking" job to a real AI, so the full loop runs against
someone else's server.

### Connect VS Code to the remote server

Add this to `.vscode/mcp.json` (note `type: "http"` and the URL — this is
how a *remote* server is configured, versus the local `command`/`args`
style from Project 1):

```json
{
  "servers": {
    "alphavantage": {
      "type": "http",
      "url": "https://mcp.alphavantage.co/mcp?apikey=YOUR_API_KEY"
    }
  }
}
```

Then:

1. Click **Start** on the server entry (or Command Palette -> `MCP: List Servers`).
2. Open **Copilot Chat**, switch the dropdown to **Agent**.
3. Click the **Tools** icon and confirm the Alpha Vantage tools are listed.

### Ask a real question

In Agent mode:

> Get me the latest stock quote for IBM.

> What was IBM's OHLCV data for the last week?

Copilot will pick the right Alpha Vantage tool, call it, show an **Allow**
dialog, and answer using live data. The AI did the asking; their server did
the answering; you wrote nothing.

---

## Part 3 — The discussion (the Edelweiss-relevant payoff)

This is the most important part for a financial-services audience. With the
remote server connected, ask the room:

1. **Where does the API key live?** It sits in a config file / URL. Who can
   see it? What happens if that file is committed to git? How is it rotated?
2. **What leaves our building?** Every query — *which stocks our desk is
   researching* — travels to Alpha Vantage's servers. For a bank, that
   research interest is itself sensitive signal. Are we comfortable sending
   it to a third party?
3. **Whose source of truth is it?** If their data is wrong, stale, or the
   service is down, our AI confidently repeats the error. We inherit their
   reliability.
4. **When is consuming right, and when should we build our own?** Alpha
   Vantage is a fine choice for public US market data. But for our own
   internal, confidential data (like the claims system in Project 1), we
   build and host the server ourselves — inside our network — so nothing
   leaves and we control the key.

**The takeaway:** consuming a third-party MCP server is not just a config
step — it is a *trust decision*. That judgement is the real skill.

---

## What Project 2 teaches (summary)

| Idea                                        | How it showed up                                     |
| ------------------------------------------- | ---------------------------------------------------- |
| Consuming vs building a server              | We used Alpha Vantage's server; wrote no server code |
| Remote (HTTP) vs local (stdio) transport    | A URL instead of`python3 server.py`                |
| Tool discovery on a server you didn't write | List Tools revealed their whole catalogue            |
| The AI as client, against a real server     | VS Code Agent mode called their tools                |
| Third-party trust & data residency          | The Part 3 discussion — the banker's real question  |
