# Chinook store assistant

Streamlit chatbot that answers strictly and securely from [Chinook_Sqlite.sql](../ChinookDatabase/DataSources/Chinook_Sqlite.sql).

For detailed system architecture, execution flowcharts, security guardrails, and data schemas, see **[ARCHITECTURE.md](ARCHITECTURE.md)**.

```bash
cd chinook-chatbot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

## Architecture Summary
- **Multi-Step Agent Pipeline**: Intent Routing (`sql`, `lookup`, `clarify`, `out_of_scope`) -> Entity Resolution -> Guarded SQL Generation -> Grounded Answer Synthesis.
- **Entity Resolution via FTS5**: Fuzzy entity matching over artists, albums, tracks, customers, and employees using SQLite FTS5.
- **AST-Based SQL Guardrails**: Multi-layer security via `sqlglot` (read-only verification, table/column allowlisting, automatic `LIMIT 50` injection) + SQLite engine-level read-only isolation (`?mode=ro` and `PRAGMA query_only = ON`).
- **Grounded Anti-Hallucination**: Answers are synthesized strictly from query row sets; external music trivia is suppressed.

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for detailed Mermaid diagrams and component breakdowns.

## Using Gemma 4 31B via Ollama

The bot talks to any OpenAI-compatible `/v1/chat/completions` endpoint. Point `.env` at Ollama instead of OpenAI.

**Local Ollama app already connected to cloud** (typical if `ollama run gemma4:31b-cloud` works):

```
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama
OPENAI_MODEL=gemma4:31b-cloud
```

Confirm the tag with `ollama list`. Cloud models in the app are often `gemma4:31b-cloud` or `gemma4:cloud`.

**Direct Ollama Cloud API** (no local daemon):

```
OLLAMA_API_KEY=your_cloud_key
OPENAI_BASE_URL=https://ollama.com/v1
OPENAI_MODEL=gemma4:31b
```

Create a key at [ollama.com](https://ollama.com). `gemma4:31b` does not support structured JSON mode; the client parses JSON from the model text instead.

On first run the app loads the SQL script into `data/chinook.db` and builds a name search index. Questions are routed to fuzzy catalog lookup and/or a read-only SELECT, then answered from the result rows.
