# 🎵 Chinook AI Store Assistant

> **Enterprise-Grade, Defense-in-Depth Text-to-SQL Chatbot over the Chinook SQLite Database**  
> *Architected & Built by **Supreeth Sudhakaran Menon** as an advanced technical interview challenge.*

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B.svg?logo=streamlit)](https://streamlit.io/)
[![Security](https://img.shields.io/badge/Security-sqlglot%20AST%20Guard-green.svg)](https://github.com/tobymao/sqlglot)
[![Search](https://img.shields.io/badge/Entity%20Resolution-SQLite%20FTS5-blueviolet.svg)](https://www.sqlite.org/fts5.html)
[![Models](https://img.shields.io/badge/LLM-Gemma%204%2031B%20%7C%20OpenAI-orange.svg)](https://ollama.com/)
[![Tests](https://img.shields.io/badge/Tests-Offline%20Verified-brightgreen.svg)](chinook-chatbot/tests/test_offline.py)

---

## 🚀 Quick Navigation
- **[🤖 Chatbot Implementation & Deep-Dive](chinook-chatbot/README.md)**
- **[🏛️ System Architecture & Mermaid Diagrams](chinook-chatbot/ARCHITECTURE.md)**
- **[⚡ Quickstart & Setup Guide](#-quickstart)**
- **[🗄️ Original Chinook Database Documentation](#-underlying-chinook-database)**

---

## 💡 About The Solution & Engineering Craft

Given only a raw database dump (`Chinook_Sqlite.sql`) and the challenge to build a conversational assistant around it, this solution rejects naive text-to-SQL wrappers (which dump prompts into an unconstrained LLM and run raw SQL against production data).

Instead, this project is engineered with **production-grade rigor**, addressing the 5 fundamental failure modes of Text-to-SQL in production:

| The Real-World Failure Mode | How Most Prototypes Fail | How This Architecture Solves It |
| :--- | :--- | :--- |
| **1. Entity Misalignment** | User queries for *"AC DC"* or *"Helena"*; SQL does `WHERE Name = 'AC DC'` and returns 0 rows. | **SQLite FTS5 Full-Text Engine**: Resolves names and fuzzy misspellings into exact primary keys (`Artist id=1`) *before* SQL generation. |
| **2. SQL Injection & Destructive DDL/DML** | LLM hallucinates `DROP`, `DELETE`, `UPDATE`, or stacked `;` queries. | **AST Validation (`sqlglot`)**: Parses the Abstract Syntax Tree, strictly rejecting non-SELECT nodes, multi-statements, and non-whitelisted tables/columns. |
| **3. Accidental Write Attacks** | Malicious or buggy SQL slips past string filters. | **Database-Level Read-Only Sandbox**: Database connections enforce URI `?mode=ro` **and** execute `PRAGMA query_only = ON`. Writes are physically impossible. |
| **4. Unbounded / Expensive Queries** | User asks for *"all tracks"*; server exhausts memory trying to render 100,000 rows. | **AST-Level Limit Clamping**: Automatically injects `LIMIT 50` into the AST while intelligently sparing single-row scalar aggregations (`COUNT(*)`, `SUM()`). |
| **5. Hallucination & Trivia Bleed** | Model answers from general pre-training memory instead of store data. | **Closed-World Grounded Synthesis**: Router segregates `out_of_scope` questions; the synthesis layer answers strictly from SQL result sets. |

---

## 🏛️ System Architecture & Workflow

```mermaid
flowchart TD
    User([👤 User / Recruiter]) <--> UI[🖥️ Streamlit Interactive UI<br/>chinook-chatbot/app.py]
    
    subgraph Orchestration ["Agent Core (chinook_bot/agent.py)"]
        UI --> Agent[ChinookAgent.ask]
        Agent --> Router[1. Intent Router<br/>sql · lookup · clarify · out_of_scope]
    end

    Router -->|out_of_scope| OutOfScopeMsg[🚫 Refuse Out-of-Scope Query]
    Router -->|clarify| ClarifyMsg[❓ Request Metric Clarification]
    
    Router -->|lookup / sql| FTSCheck[2. Entity Resolution<br/>FTS5 Indexing on Names]
    
    subgraph Grounding ["Entity Resolution (chinook_bot/fts.py)"]
        FTSCheck --> FTSIndex[(SQLite FTS5<br/>chinook_fts)]
        FTSIndex --> PreResolvedIDs[Resolved Catalog IDs<br/>e.g. Artist id=1: AC/DC]
    end
    
    subgraph Generation ["SQL Generation & Guard (chinook_bot/sql_guard.py)"]
        PreResolvedIDs --> Prompt[Prompt: Schema Card + Entity IDs]
        Prompt --> LLMGen[3. Generate SQL Query<br/>OpenAI / Ollama / Gemma 4]
        LLMGen --> ASTValidator{4. sqlglot AST Guard}
        ASTValidator -->|Invalid / DDL / Multi-Stmt| GuardReject[❌ Block & Inform User]
        ASTValidator -->|Valid SELECT| ClampedSQL[Inject LIMIT 50 Clamping]
    end
    
    subgraph Execution ["Isolated Database Engine (chinook_bot/db.py)"]
        ClampedSQL --> ReadOnlyDB[(Chinook SQLite Engine<br/>?mode=ro & PRAGMA query_only = ON)]
        ReadOnlyDB --> ResultRows[Fetch Result Rows<br/>Capped at 40 rows]
    end
    
    subgraph Synthesis ["Grounded Synthesis (chinook_bot/agent.py)"]
        ResultRows --> LLMSynth[5. Synthesize Grounded Answer<br/>Zero outside music trivia]
    end

    LLMSynth --> UI
    OutOfScopeMsg --> UI
    ClarifyMsg --> UI
    GuardReject --> UI
```

---

## 🖥️ Streamlit Dashboard Walkthrough

The interface provides complete transparency into the agent's thought process and database interactions:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ ♪ Chinook Store Assistant                                                              │
│ Answers only from the Chinook sample database (catalog, invoices, customers, employees)│
├──────────────────────────────┬─────────────────────────────────────────────────────────┤
│ 📚 What this bot knows       │ 👤 User: Who are the top 3 customers by invoice total?  │
│                              │                                                         │
│ • Tables & Foreign Keys      │ 🤖 Assistant:                                           │
│   - Album, Artist, Customer  │ The top 3 customers by total invoice expenditure are:   │
│   - Employee, Genre, Invoice │ 1. Helena Holý ($49.62)                                 │
│   - InvoiceLine, Track, etc. │ 2. Richard Cunningham ($47.62)                          │
│                              │ 3. Luis Rojas ($46.62)                                  │
│ • Sample Questions           │                                                         │
│   - Top customers by sales   │ ▼ SQL used                                              │
│   - Tracks in Rock genre     │   ```sql                                                │
│   - AC/DC album inventory    │   SELECT c.FirstName, c.LastName, SUM(i.Total) as Spent │
│   - Support reps for clients │   FROM Customer c JOIN Invoice i ON ...                 │
│                              │   GROUP BY c.CustomerId ORDER BY Spent DESC LIMIT 3;    │
│                              │   ```                                                   │
│                              │   [Tabular Dataframe with exact row counts]             │
├──────────────────────────────┴─────────────────────────────────────────────────────────┤
│ [ Ask about Chinook artists, sales, playlists, customers...                          ] │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Quickstart

```bash
cd chinook-chatbot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

To run the offline test suite (no API key needed):
```bash
python tests/test_offline.py
```

---

## 🗄️ Underlying Chinook Database

The underlying data model represents a digital media store, including tables for artists, albums, media tracks, invoices and customers.

<img width="836" alt="image" src="https://github.com/lerocha/chinook-database/assets/135025/cea7a05a-5c36-40cd-84c7-488307a123f4">

### Entity Overview
- **Catalog**: `Artist`, `Album`, `Track`, `Genre`, `MediaType`
- **Playlists**: `Playlist`, `PlaylistTrack`
- **Sales & Invoicing**: `Customer`, `Invoice`, `InvoiceLine`
- **Support Staff**: `Employee`

---

## 👨‍💻 Author

**Supreeth Sudhakaran Menon**  
- **GitHub**: [@SupreethSudhakaranMenon](https://github.com/SupreethSudhakaranMenon)
- **Role**: Software & AI Engineer
