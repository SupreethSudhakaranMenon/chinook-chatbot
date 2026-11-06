# Chinook Store Chatbot - System Architecture & Design

This document details the architectural design, security guardrails, data pipeline, and query lifecycle for the Chinook Store Chatbot.

---

## 1. High-Level System Architecture

The chatbot is structured into five decoupled layers:
1. **User Interface Layer**: Interactive Streamlit web interface with real-time feedback, execution transparency (SQL inspector, row viewer, hit inspect), and conversational session state.
2. **Agent Orchestration Layer**: Router, intent classifier, and multi-step pipeline coordinator (`ChinookAgent`).
3. **Entity Resolution Layer**: SQLite FTS5 full-text indexing engine that resolves messy user entity names (artists, tracks, albums, employees, customers) to exact database primary keys.
4. **Security & Guardrail Layer**: Abstract Syntax Tree (AST) validation via `sqlglot` and SQLite engine-level read-only constraints.
5. **Database Storage Layer**: Auto-provisioning SQLite database seeded from `Chinook_Sqlite.sql`.

```mermaid
graph TD
    User([User]) <--> UI[Streamlit UI<br/>app.py]
    
    subgraph Agent Layer ["Agent Orchestration Layer (chinook_bot/agent.py)"]
        UI <--> Agent[ChinookAgent]
        Agent --> Router[Intent Router<br/>complete_json]
    end

    subgraph LLM Layer ["LLM Interface Layer (chinook_bot/llm.py)"]
        Router <--> LLMClient[OpenAI-Compatible Client<br/>Ollama / Gemma 4 / OpenAI]
        Agent <--> LLMClient
    end

    subgraph Entity Resolution ["Entity Resolution Layer (chinook_bot/fts.py)"]
        Agent --> FTS[FTS5 Search Index<br/>chinook_fts]
    end

    subgraph Security Layer ["Security & Guardrail Layer (chinook_bot/sql_guard.py)"]
        Agent --> ASTGuard[sqlglot AST Validator<br/>Table/Col Whitelist + Limit Enforcement]
    end

    subgraph Database Layer ["Database Layer (chinook_bot/db.py)"]
        ASTGuard --> ReadOnlyConn[Read-Only SQLite Connection<br/>?mode=ro & PRAGMA query_only = ON]
        ReadOnlyConn --> ChinookDB[(chinook.db)]
        FTS --> ChinookDB
    end
```

---

## 2. End-to-End Query Lifecycle

Every user question passes through a deterministic, multi-stage pipeline designed to minimize hallucinations, prevent unauthorized data access, and ground answers strictly in database truth.

```mermaid
flowchart TD
    Start([User Submits Prompt]) --> ChatHistory[Append to Session History]
    ChatHistory --> IntentClassification[Step 1: Intent Routing<br/>complete_json]
    
    IntentClassification --> IntentCheck{Intent Decision}
    
    IntentCheck -->|out_of_scope| OutOfScopeReply[Return Out-of-Scope Notice<br/>Zero DB queries]
    IntentCheck -->|clarify| ClarifyReply[Return Clarification Question<br/>Zero DB queries]
    IntentCheck -->|lookup| RunFTS[Run FTS5 Entity Search]
    IntentCheck -->|sql| CheckEntityNeed[Run SQL Flow]
    
    RunFTS --> FormatHits[Format Resolved Catalog IDs]
    FormatHits --> SQLGen
    CheckEntityNeed --> SQLGen[Step 2: Generate SQL<br/>Prompt: Schema Card + Entity IDs]
    
    SQLGen --> ASTValidation[Step 3: sqlglot AST Validation<br/>validate_sql]
    
    ASTValidation --> ASTCheck{Passes Security Check?}
    ASTCheck -->|No / Syntax Error| GuardError[Return Guard Error Message]
    
    ASTCheck -->|Yes| ExecuteQuery[Step 4: Execute on Read-Only DB<br/>fetchmany capped at 40 rows]
    
    ExecuteQuery --> QueryCheck{Execution Succeeded?}
    QueryCheck -->|No / OperationalError| DBError[Return DB Error Notice<br/>No hallucinated guess]
    
    QueryCheck -->|Yes| AnswerGen[Step 5: Grounded Answer Synthesis<br/>complete_text]
    
    AnswerGen --> ReturnUI[Render Answer in UI<br/>+ Collapsible SQL & Row Details]
    OutOfScopeReply --> ReturnUI
    ClarifyReply --> ReturnUI
    GuardError --> ReturnUI
    DBError --> ReturnUI
    ReturnUI --> End([Turn Finished])
```

---

## 3. Defense-in-Depth Security Architecture

Data safety is enforced across three distinct structural tiers rather than relying solely on system prompts:

```mermaid
flowchart LR
    subgraph Tier1 ["Tier 1: AST Analysis (sqlglot)"]
        T1_1[Single Statement Check]
        T1_2[Rejection of DDL/DML Nodes]
        T1_3[Strict Table & Column Allowlist]
        T1_4[Enforced LIMIT 50 Clause]
    end

    subgraph Tier2 ["Tier 2: SQLite Connection Isolation"]
        T2_1[URI Read-Only Mode ?mode=ro]
        T2_2[PRAGMA query_only = ON]
        T2_3[Isolated Read-Only Factory]
    end

    subgraph Tier3 ["Tier 3: Prompt & Context Boundary"]
        T3_1[Schema-Card Closed World]
        T3_2[Row Result Grounding Constraint]
        T3_3[Zero External Knowledge Permitted]
    end

    Tier1 --> Tier2 --> Tier3
```

### Security Rules Enforced by `sql_guard.py`:
1. **Single Statement Only**: Multi-statement execution via `;` is strictly rejected to prevent stacked SQL injection.
2. **Forbidden AST Expressions**: Rejects AST nodes of type `Insert`, `Update`, `Delete`, `Drop`, `Create`, `Alter`, `Command`, `Merge`, `Pragma`, `Transaction`, and `Grant`.
3. **Table & Column Allowlist**: All parsed `exp.Table` and qualified `exp.Column` tokens must exist within `schema.ALLOWED_TABLES` and `schema.ALLOWED_COLUMNS`.
4. **Automatic Limit Injection**: All `SELECT` queries without an existing limit are capped at `MAX_LIMIT = 50`. Scalar aggregates (e.g. `COUNT(*)`, `SUM(Total)`) without `GROUP BY` are allowed to run without limits.

---

## 4. Entity Resolution & Linking (FTS5)

One of the most frequent failure points in Text-to-SQL systems is fuzzy entity recognition (misspellings, partial names, varying casing). The bot implements an SQLite FTS5 virtual table (`chinook_fts`) with a Porter stemmer (`tokenize = 'porter unicode61'`).

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Agent as ChinookAgent
    participant FTS as SQLite FTS5 (chinook_fts)
    participant LLM as SQL Generator (LLM)
    participant DB as SQLite DB

    User->>Agent: "Which tracks did AC DC compose?"
    Agent->>FTS: search_names("AC DC")
    FTS-->>Agent: [Artist id=1: "AC/DC"]
    Agent->>LLM: Prompt containing Schema + "Resolved: Artist id=1: AC/DC"
    LLM-->>Agent: SELECT Name FROM Track WHERE AlbumId IN (SELECT AlbumId FROM Album WHERE ArtistId = 1)
    Agent->>DB: Execute guarded query
    DB-->>Agent: Query rows
    Agent->>User: Natural language summary + SQL inspection expander
```

---

## 5. Data Model & Relational Topology

The Chinook database models a digital media store covering catalog inventory, store operations, employee hierarchies, and customer billing.

```mermaid
erDiagram
    Artist ||--o{ Album : "has"
    Album ||--o{ Track : "contains"
    MediaType ||--o{ Track : "formats"
    Genre ||--o{ Track : "categorizes"
    Playlist ||--o{ PlaylistTrack : "includes"
    Track ||--o{ PlaylistTrack : "is in"
    Track ||--o{ InvoiceLine : "purchased via"
    Invoice ||--o{ InvoiceLine : "contains"
    Customer ||--o{ Invoice : "billed to"
    Employee ||--o{ Customer : "supports"
    Employee ||--o{ Employee : "reports to"

    Artist {
        int ArtistId PK
        string Name
    }
    Album {
        int AlbumId PK
        string Title
        int ArtistId FK
    }
    Track {
        int TrackId PK
        string Name
        int AlbumId FK
        int MediaTypeId FK
        int GenreId FK
        string Composer
        int Milliseconds
        int Bytes
        numeric UnitPrice
    }
    Customer {
        int CustomerId PK
        string FirstName
        string LastName
        string Email
        int SupportRepId FK
    }
    Invoice {
        int InvoiceId PK
        int CustomerId FK
        datetime InvoiceDate
        numeric Total
    }
    InvoiceLine {
        int InvoiceLineId PK
        int InvoiceId FK
        int TrackId FK
        numeric UnitPrice
        int Quantity
    }
    Employee {
        int EmployeeId PK
        string FirstName
        string LastName
        string Title
        int ReportsTo FK
    }
```

---

## 6. Component Directory Structure

```
chinook-chatbot/
├── app.py                 # Streamlit UI & conversation session state
├── requirements.txt       # Dependencies (streamlit, openai, sqlglot, python-dotenv)
├── README.md              # Quickstart, setup, and model configuration
├── ARCHITECTURE.md        # Architectural documentation & flowcharts (this document)
├── .env.example           # Configuration template for local Ollama, Cloud, or OpenAI
├── chinook_bot/
│   ├── __init__.py        # Exposes ChinookAgent
│   ├── agent.py           # Multi-step agent orchestrator (Router -> SQL -> Answer)
│   ├── db.py              # SQLite connection lifecycle & read-only isolation
│   ├── fts.py             # FTS5 full-text search & entity resolution
│   ├── llm.py             # Multi-provider OpenAI client & robust JSON parser
│   ├── schema.py          # Ground truth schema cards, foreign keys & business rules
│   └── sql_guard.py       # sqlglot AST parser, validator & safety clamp
├── tests/
│   └── test_offline.py    # Unit tests for DB initialization, FTS, and SQL guard
└── data/
    └── chinook.db         # Auto-generated SQLite database (git-ignored)
```

---

## 7. Trade-offs and Future Roadmap

| Capability | Current Implementation | Proposed Production Roadmap |
| :--- | :--- | :--- |
| **Error Recovery** | Static error message upon failure | **Self-Healing Reflection Loop**: Feed SQLite/guard errors back to LLM for up to 2 retry attempts. |
| **Entity Lookup** | Triggered only on `lookup` route | **Eager Entity Linking**: Extract entities via lightweight regex/FTS in parallel for all queries. |
| **Multi-turn Memory** | Retains conversational text | **Stateful Query Memory**: Retain previous SQL queries and resolved entity IDs for seamless drill-downs. |
| **Latency** | 3 sequential LLM round-trips | **Unified Tool Calling**: Merge Router and SQL Generation into a single function-calling LLM step. |

