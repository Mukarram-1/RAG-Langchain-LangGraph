# Legal AI Chatbot

Python/LangGraph framework for read-only structured lookups against the
`API_ada_dashboard` PostgreSQL database.

Implemented flow:

`question + history -> orchestrator -> SQL writer -> SQL guardrail -> SQL executor -> deterministic checks -> result validator -> response synthesis`

Guardrail and grounding failures retry the SQL writer at most twice with
specific internal feedback. Missing identifiers produce a clarification
question instead of fake SQL. Semantic retrieval and document access remain
future agents.

## Setup

```bash
cd /Users/mac/Desktop/legal_ai_chatbot
cp .env.example .env
```

Set `DATABASE_URL` and one provider API key in `.env`, then choose:

```dotenv
LLM_PROVIDER=anthropic
# or
LLM_PROVIDER=openai
```

The virtual environment is already created. To recreate it:

```bash
python3 -m venv .venv
.\.venv\Scripts\activate 
pip install -r requirements.txt
```

## Run

One question:

```bash
.venv/bin/python main.py "Find the domain with domain number 60001"
```

Interactive session:

```bash
.venv/bin/python main.py
```

The console logs each pipeline stage at INFO level: discovered schema and
foreign-key counts, orchestrator route, SQL-writer rationale and draft SQL,
guardrail verdict and final limited SQL, executor row count, grounding verdict,
and response synthesis. Restart the CLI after code or prompt changes because
schema metadata is loaded at startup.

Programmatic use:

```python
from src.chatbot import LegalAIChatbot

async with LegalAIChatbot() as chatbot:
    result = await chatbot.ask("List active matters for Acme")
    print(result.answer)
```

## Safety boundary

- The language model receives schema metadata, not database credentials.
- The schema context includes live PostgreSQL foreign keys plus curated
  business semantics for ambiguous legacy names such as `retestVisiteDate`.
- The SQL writer cannot execute SQL.
- `sqlglot` parses every query and accepts one quoted, schema-allow-listed
  `SELECT` only.
- Unknown tables/columns, wildcard selection, comments, mutations, unsafe
  functions, locking, and credential columns are rejected.
- A configured maximum row limit is applied deterministically.
- PostgreSQL connections request read-only transactions and enforce a
  statement timeout. Use a database account whose grants are also SELECT-only;
  application checks are not a substitute for database permissions.

Because this milestone has no HTTP API, authentication remains the
responsibility of the future API adapter and must occur before `ask()` is
called.

## Add an agent

1. Implement the async `AgentNode` protocol in `src/agents/`.
2. Register the node in `src/graph.py` through `AgentRegistry`.
3. Add an explicit conditional route and failure route.
4. Add deterministic tests for the new path.

Keep graph state lean and pass infrastructure through constructors rather than
storing pools, models, credentials, or complete schemas in checkpointed state.

## Test

```bash
.venv/bin/python -m pytest -q
```
