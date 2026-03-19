# TARS Rewrite Plan — Complete Architecture Redesign

## Context

TARS is an ~11,000-line Python AI executive assistant with 23 integration modules, 60+ tools, and three channels (Telegram, Web, Voice). It works, but has accumulated structural debt that limits its evolution toward fully autonomous operation. This plan proposes a ground-up rewrite preserving the core value (strategic intelligence, Agile methodology, multi-channel access) while fixing fundamental architecture issues.

The deliverable is a comprehensive `TARS_REWRITE_PLAN.md` document committed to the repo, written for a professional developer audience — opinionated, actionable, and challenge-ready.

---

## Document Structure

### 1. Current State Assessment

**What works well (preserve in rewrite):**
- The simple agentic while-loop in `core.py` (118 lines) — correct pattern, just needs enhancement
- The `register_tool()` abstraction pattern — clean, just diverged into two copies
- Integration modules (`integrations/*.py`) — well-isolated, testable, portable
- The TARS personality / system prompt (75% humor, Interstellar persona)
- Intelligence engine concepts: Eisenhower matrix, delegation detection, topic extraction, proactive alerts
- Strategic layer: decisions register, initiatives/OKRs, meeting prep, team portfolio

**Critical problems:**
1. **Two separate tool systems**: ~35 tools in `agent/tools.py` (Claude format) vs ~55 tools in `web/server.py` (OpenAI format). Strategic tools only available via voice/web.
2. **JSON file persistence**: 8 JSON files, no concurrent access protection, no transactions, no migrations, no backup strategy
3. **No autonomous operation**: Intelligence scans, briefings, alerts are all on-demand only
4. **In-memory conversation history**: Lost on restart
5. **2,085-line web server monolith**: Tool schemas + dispatch + REST APIs + static serving + SSE streaming in one file
6. **1,564-line intelligence engine**: Scanning, extraction, classification, graph building, and persistence all in one module
7. **No CLI interface**: Only Telegram and web
8. **No Obsidian integration**: Only Notion for knowledge management
9. **No structured logging or observability**
10. **Synchronous Claude API calls in async context**

### 2. Tech Stack Recommendations

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | **Python 3.12+** | Ecosystem fit. All deps (Anthropic, OpenAI, MSAL, Telegram) are Python-first. No perf bottleneck. |
| Agent Framework | **Custom (no LangGraph/CrewAI)** | Single-agent system. LangGraph adds 5000+ lines of abstraction for the same behavior. The loop is 118 lines — enhance it, don't wrap it. |
| Database | **SQLite + WAL mode + Alembic** | Single-user = zero-ops. WAL handles concurrent reads. FTS5 for full-text search. Trivial backup (`cp`). If multi-user ever needed, SQLAlchemy Core makes Postgres migration a swap. |
| Tool Protocol | **Unified internal registry** (not MCP) | MCP is for inter-process tool discovery between separate apps. TARS is one app. Build a single `ToolDefinition` that emits both Claude and OpenAI formats. MCP's overhead (JSON-RPC, serialization) is unnecessary here. |
| Scheduler | **APScheduler 4.x** (async-native) | Cron/interval triggers. Persists jobs to SQLite. Replaces Telegram's JobQueue for reminders and adds autonomous operations. |
| CLI | **Typer + Rich** | Typer for commands, Rich for tables/markdown/progress. First-class channel alongside Telegram/Web. |
| Web | **FastAPI** (keep, restructure) | Split monolith into route modules. Add WebSocket for real-time. |
| Logging | **structlog** | Structured JSON logging. Add OpenTelemetry spans for tool/LLM call tracing. |
| Deployment | **Docker Compose + systemd** | Single container. SQLite file as volume mount. systemd `Restart=always` for bare-metal. |
| Config | **Pydantic Settings** | Replaces manual `os.environ.get()`. Type validation, .env loading, nested config objects. |

**What NOT to use and why:**
- **LangGraph/CrewAI**: Abstraction tax for multi-agent orchestration TARS doesn't need
- **Postgres**: Operational overhead with zero benefit for single-user
- **MCP as internal protocol**: Inter-process overhead for intra-process calls; build MCP-compatible _output_ but not MCP _transport_
- **ORM**: Data model is simple enough for raw SQL + repository classes
- **React/Vue frontend rewrite**: Not this cycle. Improve API layer, leave frontend for later.

### 3. New Architecture

#### 3.1 Directory Structure

```
tars/
  __main__.py                 # Entry point: CLI dispatcher
  config.py                   # Pydantic Settings (typed, validated)

  core/
    agent.py                  # AgentRunner: async agentic loop with streaming
    router.py                 # Model router: task_type → model selection
    memory.py                 # 3-tier memory: session / persistent / semantic
    prompts.py                # System prompts, personality, channel variants

  tools/
    registry.py               # Unified ToolRegistry: one definition → Claude + OpenAI formats
    _base.py                  # ToolDefinition dataclass
    calendar.py               # M365 calendar tools
    mail.py                   # M365 mail tools
    tasks.py                  # M365 To Do tools
    notion.py                 # Notion read/write/search tools
    intel.py                  # Intelligence scan, smart tasks, graph
    strategic.py              # Decisions, initiatives, OKRs, alerts
    agile.py                  # Epics, stories, team portfolio
    people.py                 # People profiles, relationships
    reminders.py              # Reminder CRUD
    briefing.py               # Daily/weekly briefing compilation
    meeting_prep.py           # Meeting prep tool
    obsidian.py               # NEW: Obsidian vault integration
    documents.py              # NEW: File handling, document analysis

  channels/
    _base.py                  # Channel protocol/interface
    telegram.py               # Telegram adapter (webhook + polling modes)
    web.py                    # FastAPI web API + SSE streaming
    cli.py                    # Interactive CLI (Typer + Rich)
    voice.py                  # OpenAI Realtime voice adapter

  integrations/               # External service clients (no business logic)
    microsoft/
      auth.py                 # MSAL OAuth
      graph.py                # MS Graph API client
    notion/
      client.py               # Notion API client (httpx)
    openai/
      realtime.py             # OpenAI Realtime session management
      whisper.py              # Whisper transcription
      tts.py                  # Text-to-speech
    obsidian/
      vault.py                # Obsidian vault filesystem operations

  db/
    engine.py                 # SQLite connection management (aiosqlite)
    migrations/               # Numbered SQL migration files
    repositories/             # One per entity (tasks, decisions, epics, etc.)

  scheduler/
    engine.py                 # APScheduler setup
    jobs/                     # One file per scheduled job
      morning_briefing.py     # 7:00 AM
      notion_scan.py          # Every 4 hours
      reminder_check.py       # Every 30 seconds
      overdue_alerts.py       # 9:00 AM daily
      review_pages.py         # 11:00 PM nightly
      weekly_review.py        # Friday 5:00 PM

  web/
    app.py                    # FastAPI application factory
    routes/                   # Separated route modules
    templates/                # Jinja2 (or keep static HTML)
    static/                   # CSS, JS, assets

  tests/
```

#### 3.2 Unified Tool System (highest priority change)

```python
@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict            # JSON Schema, provider-agnostic
    handler: Callable           # async (input, context) -> dict
    category: str               # "calendar", "intel", "strategic"
    requires: list[str]         # ["ms365"], ["notion"] — conditional registration
    confirm_before: bool        # Require user confirmation (send_email, etc.)

class ToolRegistry:
    def register(self, tool: ToolDefinition) -> None
    def to_claude_format(self) -> list[dict]     # Anthropic tool_use schema
    def to_openai_format(self) -> list[dict]     # OpenAI function-calling schema
    def execute(self, name, input, context) -> dict
    def available_for(self, integrations: set) -> ToolRegistry  # filtered subset
```

Every tool defined ONCE. Eliminates the 35-vs-55 tool parity gap permanently.

#### 3.3 Channel Abstraction

```python
class Channel(Protocol):
    async def send_message(self, chat_id: str, text: str) -> None
    async def send_notification(self, chat_id: str, text: str) -> None  # unsolicited
    channel_type: str   # "telegram", "cli", "web", "voice"
```

Each channel is a thin adapter (100-200 lines) that converts channel-specific I/O into agent calls.

#### 3.4 Agent Core (Enhanced)

```python
class AgentRunner:
    async def run(self, session_id, message, task_type="conversation") -> AsyncIterator[str]:
        model = self.router.select_model(task_type)
        history = await self.memory.get_history(session_id)
        context = await self.memory.get_relevant_context(message)  # semantic search
        tools = self.tool_registry.to_format(model.provider)

        while True:
            response = await self._call_llm(model, history + context, tools)
            if response.has_tool_calls:
                results = await self.tool_registry.execute_batch(response.tool_calls)
                history.extend(results)
                continue
            await self.memory.save(session_id, message, response.text)
            yield response.text
            break
```

Key improvements over current:
- Async-native (no blocking calls)
- Streaming responses
- Model routing (Sonnet for conversation, Haiku for extraction)
- Semantic memory injection (relevant past context added automatically)
- Persistent conversation history (survives restart)

#### 3.5 Memory Architecture (3 tiers)

| Tier | Storage | Purpose |
|------|---------|---------|
| Session | In-memory | Current conversation turns (last N messages) |
| Persistent | SQLite `conversations` table | Full history, survives restart, queryable |
| Semantic | SQLite FTS5 + `memory_facts` table | Key facts extracted from conversations. Agent can search "what did we decide about X?" |

#### 3.6 Model Router

```python
class ModelRouter:
    def select_model(self, task_type: str) -> ModelConfig:
        match task_type:
            case "conversation":  return claude_sonnet_4
            case "extraction":    return claude_haiku_4_5    # intel scanning
            case "rewrite":       return claude_haiku_4_5    # title cleanup, summaries
            case "voice":         return openai_realtime
```

### 4. New Capabilities

#### Obsidian Integration
- `integrations/obsidian/vault.py`: Walk vault directory, parse YAML frontmatter, search markdown content
- Tools: `search_obsidian`, `read_note`, `create_note`, `update_note`, `link_notes`
- Obsidian as complementary personal knowledge base alongside Notion

#### CLI Interface
```
tars chat           # Interactive REPL with Rich formatting
tars briefing       # Print today's briefing
tars tasks          # List smart tasks (Rich table with Eisenhower quadrants)
tars scan           # Run Notion scan with progress bar
tars status         # Show integration status
tars serve          # Start web server only
tars bot            # Start Telegram bot only
tars run            # Start everything (web + bot + scheduler)
```

#### Autonomous Background Operations

| Job | Schedule | Action |
|-----|----------|--------|
| Morning briefing | 7:00 AM | Compile & push to Telegram |
| Notion scan | Every 4 hours | Incremental scan, extract new tasks |
| Reminder check | Every 30 seconds | Fire due reminders |
| Overdue alerts | 9:00 AM daily | Flag overdue tasks, stale decisions |
| Page review | 11:00 PM nightly | Auto-review Notion pages edited today |
| Weekly review | Friday 5:00 PM | Compile weekly summary |

#### Webhook Support
- Telegram webhooks (faster than polling, lower resource usage)
- Microsoft Graph change notifications (calendar/mail triggers)
- Config flag to switch between polling and webhook modes

#### Persistent Conversation Memory
- Full conversation history in SQLite (no more lost-on-restart)
- Semantic fact extraction from conversations → FTS5 searchable
- Agent can query past interactions for context

#### Observability
- structlog for structured JSON logging throughout
- OpenTelemetry spans on tool calls and LLM requests
- Cost tracking per interaction (tokens * price)
- `GET /health` endpoint with scheduler/DB/integration status

### 5. Database Schema

```sql
-- Conversations (replaces in-memory _histories dict)
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY,
    chat_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Smart tasks (replaces notion_intel.json tasks section)
CREATE TABLE smart_tasks (
    id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    owner TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    quadrant INTEGER DEFAULT 4,
    follow_up_date TEXT,
    source_title TEXT, source_url TEXT, source_page_id TEXT, source_context TEXT,
    topics JSON DEFAULT '[]',
    created_at TIMESTAMP, updated_at TIMESTAMP
);

-- Decisions (replaces decisions.json)
CREATE TABLE decisions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    rationale TEXT, decided_by TEXT, stakeholders JSON,
    context TEXT, initiative TEXT,
    status TEXT DEFAULT 'decided',
    outcome_notes TEXT,
    created_at TIMESTAMP, updated_at TIMESTAMP
);

-- Initiatives (replaces initiatives.json)
CREATE TABLE initiatives (
    id TEXT PRIMARY KEY,
    title TEXT, description TEXT, owner TEXT,
    quarter TEXT, status TEXT, priority TEXT,
    milestones JSON, key_results JSON,
    created_at TIMESTAMP, updated_at TIMESTAMP
);

-- Epics, stories (replaces epics.json)
CREATE TABLE epics (...);
CREATE TABLE stories (...);

-- People profiles (replaces people_profiles.json)
CREATE TABLE people (...);

-- Reminders (replaces reminders.json)
CREATE TABLE reminders (...);

-- Intel page index (replaces notion_intel.json page_index)
CREATE TABLE intel_pages (
    page_id TEXT PRIMARY KEY,
    title TEXT, url TEXT, summary TEXT,
    topics JSON, people JSON, projects JSON,
    organizations JSON, decisions JSON, tags JSON,
    last_edited TEXT, scanned_at TIMESTAMP
);

-- Semantic memory (NEW)
CREATE TABLE memory_facts (
    id INTEGER PRIMARY KEY,
    chat_id TEXT, fact TEXT NOT NULL, source TEXT,
    created_at TIMESTAMP
);
CREATE VIRTUAL TABLE memory_fts USING fts5(fact, source, chat_id, content='memory_facts');
```

### 6. Migration Strategy (Strangler Fig Pattern)

Build new system alongside old. Migrate one subsystem at a time. Old code keeps working until replaced.

**Phase 1: Foundation (Week 1-2)**
- New directory structure + Pydantic config
- SQLite database + migrations + JSON-to-SQLite migration script
- Enhanced agent loop (async, streaming, persistent history)
- CLI channel as first working channel
- Port calendar, mail, task tools
- **Milestone**: `tars chat` works with M365 tools, conversations persist across restarts

**Phase 2: Tool Unification (Week 3-4)**
- Unified ToolRegistry (one definition → Claude + OpenAI formats)
- Port all remaining tools (Notion, intel, decisions, initiatives, epics, people, reminders, alerts, briefing, meeting_prep, review)
- Telegram channel with webhook support
- Model router
- **Milestone**: Telegram has FULL tool parity (55 tools everywhere, not 35 vs 55)

**Phase 3: Web & Autonomy (Week 5-6)**
- FastAPI restructured (split into route modules)
- REST APIs call tools through unified registry
- APScheduler with all autonomous jobs
- Voice channel
- **Milestone**: `tars run` starts web + Telegram + scheduler. Morning briefings arrive automatically

**Phase 4: New Capabilities (Week 7-8)**
- Obsidian integration
- Semantic memory (FTS5)
- structlog + OpenTelemetry observability
- Docker Compose deployment
- Comprehensive test suite
- **Milestone**: Full feature parity + Obsidian + persistent memory + autonomous scheduling + observability

### 7. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| SQLite migration loses data | Run migration script in Phase 1, verify integrity, keep JSON files as backup until Phase 4 |
| Webhook setup harder than polling | Support both modes via config flag. Default polling in dev, webhooks in prod |
| Scope creep on frontend | Do NOT rewrite HTML pages this cycle. Port as-is. API layer is what matters |
| APScheduler reliability | Persist jobs to SQLite. systemd `Restart=always`. Jobs resume on restart |
| Tool unification breaks existing behavior | Port one tool category at a time. Run old and new in parallel during migration |

### 8. Key Architectural Decisions Summary

| Decision | Choice | Alternative Rejected | Why |
|----------|--------|---------------------|-----|
| Agent framework | Custom loop | LangGraph, CrewAI | Single-agent. 118 lines vs 5000+ abstraction. |
| Database | SQLite | Postgres, JSON files | Single-user. Zero ops. Portable. ACID. |
| Tool protocol | Unified internal registry | MCP | One app, not inter-process. Avoid serialization overhead. |
| Frontend | Keep existing HTML | React/Vue rewrite | Not this cycle. API layer matters more. |
| ORM | None (raw SQL + repos) | SQLAlchemy ORM | Simple data model. Raw SQL is clearer. |
| Multi-model | Router class | Skip entirely | Already using Haiku + Sonnet. Formalize it. |
| Memory | SQLite FTS5 | Vector DB (ChromaDB) | Good enough for single-user. Add vectors later if needed. |

---

## Files to Create

1. **`/home/user/tars/TARS_REWRITE_PLAN.md`** — The comprehensive document above, formatted for developer audience

## Verification

- Review document completeness against all 8 sections
- Ensure current architecture assessment matches actual code
- Ensure phased migration is realistic and dependency-ordered
- Commit to branch `claude/document-tars-model-nPHVa` and push
