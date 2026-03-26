# TARS — Comprehensive Handoff Document

> **Version:** 2.0  
> **Date:** 2026-03-26  
> **Purpose:** Complete technical and functional handoff for the TARS Executive Assistant Platform

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture & Tech Stack](#2-architecture--tech-stack)
3. [Getting Started](#3-getting-started)
4. [Frontend — Pages, Components & User Flows](#4-frontend--pages-components--user-flows)
5. [Backend — API, Agent & Database](#5-backend--api-agent--database)
6. [AI Agent System](#6-ai-agent-system)
7. [Tool Registry — All 55+ Tools](#7-tool-registry--all-55-tools)
8. [External Service Integrations](#8-external-service-integrations)
9. [Database Schema](#9-database-schema)
10. [Intelligence & Classification Engine](#10-intelligence--classification-engine)
11. [Telegram Bot](#11-telegram-bot)
12. [Voice Interface](#12-voice-interface)
13. [Authentication & Security](#13-authentication--security)
14. [Theme System](#14-theme-system)
15. [Feature Completeness & Gaps](#15-feature-completeness--gaps)
16. [File Map](#16-file-map)

---

## 1. Project Overview

TARS is an AI-powered executive assistant platform that integrates with Microsoft 365 (calendar, email, tasks), Notion (knowledge base), and provides strategic planning tools. Users interact with TARS through a React web dashboard, Telegram bot, or voice interface.

**What TARS does:**
- Manages calendar events, emails, and tasks via Microsoft 365
- Scans Notion pages to extract actionable intelligence (tasks, decisions, people, topics)
- Provides an Eisenhower priority matrix for task management
- Tracks strategic initiatives, OKRs, decisions, epics, and user stories
- Generates daily briefings, weekly reviews, and meeting prep briefs
- Offers proactive alerts for overdue tasks, stale decisions, and at-risk initiatives
- Auto-classifies tasks into a full agile hierarchy (Theme → Initiative → Epic → Story → Task)
- Supports real-time streaming chat with tool calling via WebSocket

**Named after** the robot from Interstellar — direct, efficient, and occasionally witty. Humor setting: 75%.

---

## 2. Architecture & Tech Stack

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER INTERFACES                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────┐  │
│  │  React SPA   │  │ Telegram Bot │  │  Voice Call  │  │  CLI   │  │
│  │  (Vite/TS)   │  │ (polling)    │  │  (Realtime)  │  │(planned│  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └────────┘  │
│         │                 │                 │                        │
│  ┌──────┴─────────────────┴─────────────────┴──────────────────┐    │
│  │                    FastAPI Backend                           │    │
│  │  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │    │
│  │  │ Auth API│  │ Chat API │  │ Data API │  │  WebSocket  │  │    │
│  │  └────┬────┘  └────┬─────┘  └────┬─────┘  └──────┬──────┘  │    │
│  │       │             │             │               │          │    │
│  │  ┌────┴─────────────┴─────────────┴───────────────┴──────┐   │    │
│  │  │              AI Agent (Claude Sonnet 4)               │   │    │
│  │  │         Streaming + Tool Calling Loop                  │   │    │
│  │  └─────────────────────┬──────────────────────────────────┘   │    │
│  │                        │                                      │    │
│  │  ┌─────────────────────┴──────────────────────────────────┐   │    │
│  │  │            Unified Tool Registry (55+ tools)           │   │    │
│  │  └─────────────────────┬──────────────────────────────────┘   │    │
│  └────────────────────────┼──────────────────────────────────────┘    │
│                           │                                          │
│  ┌────────────────────────┴──────────────────────────────────────┐   │
│  │                     INTEGRATIONS                               │   │
│  │  ┌──────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐  │   │
│  │  │MS Graph  │ │ Notion │ │Anthropic│ │ OpenAI │ │ Telegram │  │   │
│  │  │Calendar  │ │  API   │ │Claude   │ │Whisper │ │  Bot API │  │   │
│  │  │Mail/Tasks│ │        │ │Sonnet/  │ │TTS     │ │          │  │   │
│  │  │          │ │        │ │Haiku/   │ │Realtime│ │          │  │   │
│  │  │          │ │        │ │Opus     │ │        │ │          │  │   │
│  │  └──────────┘ └────────┘ └────────┘ └────────┘ └──────────┘  │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                           │                                          │
│  ┌────────────────────────┴──────────────────────────────────────┐   │
│  │                     PERSISTENCE                                │   │
│  │  ┌──────────────────┐  ┌──────────────────────────────────┐   │   │
│  │  │  SQLite (tars.db) │  │  JSON Files (legacy, migrating) │   │   │
│  │  │  WAL mode, FTS5   │  │  decisions/epics/initiatives/   │   │   │
│  │  │  5 migrations     │  │  themes/intel/people            │   │   │
│  │  └──────────────────┘  └──────────────────────────────────┘   │   │
│  └───────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

**Tech Stack:**

| Layer | Technology |
|-------|-----------|
| Frontend | React 19 + TypeScript 5.9, Vite, Zustand, TailwindCSS 4, Lucide icons, D3.js |
| Backend | Python, FastAPI, uvicorn, SQLite (WAL + FTS5) |
| AI Models | Claude Sonnet 4 (conversation), Claude Haiku 4.5 (extraction), Claude Opus 4 (classification) |
| Voice | OpenAI Whisper (STT), OpenAI TTS, OpenAI Realtime API |
| Auth | Custom JWT (HS256, 7-day expiry), MSAL device-code flow (M365) |
| Bot | python-telegram-bot (polling mode) |
| External APIs | Microsoft Graph, Notion API, Anthropic, OpenAI, Telegram Bot API |

---

## 3. Getting Started

### Environment Variables (`.env`)

```
TELEGRAM_BOT_TOKEN=         # Telegram bot token
ANTHROPIC_API_KEY=           # Claude API key
OPENAI_API_KEY=              # OpenAI API key (voice features)
MS_CLIENT_ID=                # Azure AD application ID
MS_TENANT_ID=                # Azure AD tenant ID
NOTION_API_KEY=              # Notion integration token
```

### Running

```bash
# Backend (FastAPI)
uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload

# Frontend (Vite dev server)
cd frontend && npm run dev    # port 5173

# Telegram bot
python app.py
```

### Auto-Generated Files
- `.jwt_secret` — JWT signing key (created on first run)
- `token_cache.json` — M365 MSAL token cache
- `tars.db` — SQLite database (created with migrations on startup)


---

## 4. Frontend — Pages, Components & User Flows

### 4.1 Application Shell

The app uses `BrowserRouter` with a `ProtectedRoute` wrapper that redirects to `/login` if no auth token exists.

**Layout structure:**
```
┌──────────────────────────────────────────────────┐
│ Sidebar (240px)  │  TopBar (56px)                │
│                  │──────────────────────────────  │
│  Logo + v2.0     │  Search │ ⌘K │ ☀ │ 🔔 │ TARS │
│  Team Switcher   │──────────────────────────────  │
│                  │                                │
│  Command Center  │       Page Content             │
│  Work            │       (React Router Outlet)    │
│  Strategy        │                                │
│  People          │                                │
│  Settings        │                                │
│                  │                     ┌─────────┐│
│  ──────────────  │                     │  Chat   ││
│  Avatar + Name   │                     │  Panel  ││
│  Logout          │                     │ (380px) ││
│                  │                     └─────────┘│
└──────────────────────────────────────────────────┘
```

**Shared Components:**
- **Sidebar** — Navigation, team switcher, user profile, logout
- **TopBar** — Search bar, Quick Action (⌘K), dark mode toggle, notifications, TARS chat toggle
- **CommandPalette** — ⌘K launcher with search, navigation, and quick actions
- **ChatPanel** — WebSocket streaming chat with TARS (right panel, 380px)
- **DetailPanel** — Slide-over panel (480px) for viewing/editing any entity with inline field editing

### 4.2 Login Page (`/login`)

**User Story:** *As a new user, I can register or sign in to access TARS.*

- Toggle between Sign In and Register modes
- Fields: Email, Name (register only), Password
- On success: stores JWT token + user profile in Zustand, navigates to `/`
- On error: shows error banner
- API: `POST /api/auth/login` or `POST /api/auth/register`

### 4.3 Command Center (`/`) — Home Dashboard

**User Story:** *As an executive, I want a single dashboard showing what needs my attention today.*

**Sections:**

1. **Greeting Header** — "Good morning, Jonas" with date and critical alert count
2. **Alert Banner** — Red-bordered box showing first 2 critical alerts (if any)
3. **Stats Cards** (4-column grid):
   - Open Tasks (blue) — clickable, navigates to Work
   - Alerts (yellow) — count of active alerts
   - Overdue (red) — tasks past due
   - Completed (green) — done tasks
4. **Meeting Review Card** — Recent meeting summaries
5. **Two-Column Layout:**
   - **Left: Alerts & Attention** — Expandable alert cards with severity colors (critical=red, warning=yellow, info=cyan), suggested actions
   - **Right: Strategic Overview** — Initiative/decision/epic counts with status breakdown, links to Strategy page

**API Calls:** `/api/alerts`, `/api/strategic-summary`, `/api/review/weekly`, `/api/meeting-prep`, `/api/meeting-review`

### 4.4 Work Page (`/work`) — Task Management

**User Story:** *As a manager, I want to see all my tasks organized by priority and status, and quickly reassign or reschedule them.*

**4 Tab Views:**

| Tab | View | Interaction |
|-----|------|-------------|
| **Matrix** | 2×2 Eisenhower grid (Do First / Schedule / Delegate / Defer) | Drag-drop between quadrants |
| **Board** | 3-column Kanban (Open / In Progress / Done) | Drag-drop between columns |
| **List** | Sortable table (Task, Owner, Status, Priority, Due Date) | Inline editing |
| **Timeline** | Gantt-style time view | Drag to adjust dates |

**Task Detail Panel** (opens on click):
- Status select (open / in_progress / done)
- Owner select (auto-populated from existing owners)
- Priority/Quadrant select (Do First=Q1, Schedule=Q2, Delegate=Q3, Defer=Q4)
- Follow-up date picker
- Classification badge (strategic / operational / unclassified)
- Source badge (confirmed / auto)
- Meeting source (readonly, formatted date)
- Source link (opens in new tab)
- Context lines (expandable, from Notion source)
- Next steps (expandable list with "Create as task" action per step)
- Age in days (readonly)
- Delegated indicator (readonly)

**User Actions:**
- Search/filter tasks by text
- Switch between 4 views
- Drag-drop to change priority or status
- Click task → edit in DetailPanel → saves via `PATCH /api/intel/tasks/{id}`
- Create new task from a next-step line item

**API:** `GET /api/intel/tasks`, `PATCH /api/intel/tasks/{id}`, `POST /api/intel/tasks/{id}/create-from-step`, `GET /api/hierarchy`

### 4.5 Strategy Page (`/strategy`) — Strategic Planning

**User Story:** *As an executive, I want to see the full strategic hierarchy and manage initiatives, decisions, and portfolio health.*

**5 Tab Views:**

#### Hierarchy Tab
- Full agile tree: **Themes → Initiatives → Epics → Stories**
- Expand/collapse tree nodes
- Status colors: on_track (green), at_risk (yellow), off_track (red), completed (gray), paused (gray)
- Unclassified tasks section at bottom
- **Auto-Classification button** — triggers Claude Opus classification pipeline:
  - Progress bar with phase indicators (context → phase 1 → phase 2 → grammar)
  - Polls `/api/classify/status` every 1.5s
  - On completion: reloads hierarchy
- Decision bubbles linked to nodes
- Undo system (toast with undo button, 8s timeout)

#### Health Tab
- Initiative health metrics with Red/Yellow/Green indicators
- Blockers list and risk assessment

#### Decisions Tab
- Table of decisions filterable by status (decided / pending / revisit / request)
- Add new decision form (title, rationale, decided_by, stakeholders, context, initiative link)
- Edit decision status and outcome notes

#### Portfolio Tab
- Heatmap/matrix of initiatives by quarter and owner
- Drag-drop to reorganize

#### Review Tab (Weekly)
- Smart task completion stats
- Pending vs completed breakdown
- Next week outlook

**API:** `/api/hierarchy`, `/api/strategic-summary`, `/api/decisions`, `/api/health`, `/api/portfolio`, `/api/review/weekly`, `/api/classify`, `/api/classify/status`

### 4.6 People Page (`/people`) — Network & Relationships

**User Story:** *As a manager, I want to see everyone I work with, their roles, and prepare for 1:1 meetings.*

**3 Tab Views:**

#### Directory Tab
- Grid of person cards (280px min columns)
- Each card shows: avatar (initial circle), name, role, organization, mention count, related pages, open tasks, topic tags (max 4 + overflow)
- Search by name, role, organization, email
- Sort toggle: "By mentions" vs "A-Z"
- Click card → DetailPanel with editable fields:
  - Role, Relationship (colleague/manager/report/stakeholder/client/vendor/other)
  - Organization, Email, Notes
  - Topics (editable tag list)
  - Mentions count, 1:1s indicator, related pages, open tasks (all readonly)

#### Graph Tab
- Interactive D3 network visualization
- Nodes = people, edges = relationships, color by organization
- Click node for details

#### Meeting Prep Tab
- Upcoming meetings with attendees
- Per-person talking points and recent activity

**API:** `GET /api/people`, `PATCH /api/people/{name}`, `/api/relationship-graph`, `/api/meeting-prep`

### 4.7 Settings Page (`/settings`)

**User Story:** *As a user, I want to customize the look and feel and manage my team.*

**Sections:**
1. **Appearance** — Theme selector (4 themes), dark mode toggle, density selector (compact/comfortable/spacious)
2. **Integration Status** — Connected services with status indicators
3. **Team Management** — Member list, add/remove members

### 4.8 Chat Panel (Global)

**User Story:** *As a user, I can chat with TARS from any page and ask it to take actions on my behalf.*

- Toggle via "TARS" button in TopBar
- WebSocket connection to `/api/chat/ws?token={jwt}`
- Streaming token display (tokens appear as received)
- Tool call notices ("Using get_calendar_events...")
- Auto-reconnect after 3s on disconnect
- Enter to send, Shift+Enter for newline
- Message types: user (right-aligned), assistant (left-aligned), system (centered), tool (gray)
- Empty state: TARS logo + instruction text

**WebSocket Protocol:**
```
Client → {"type": "message", "content": "...", "conversation_id": "..."}
Server → {"type": "token", "content": "..."}           (streaming)
Server → {"type": "tool_call", "name": "...", "arguments": {...}}
Server → {"type": "tool_result", "name": "...", "result": {...}}
Server → {"type": "message_complete", "content": "...", "message_id": "..."}
Server → {"type": "error", "detail": "..."}
```

### 4.9 State Management (Zustand)

**Store (`/store/index.ts`):**
```typescript
{
  // Auth
  token, user, teams, activeTeamId
  
  // Theme
  themeId, darkMode, density
  
  // Chat
  chatOpen, chatMessages, conversationId, isStreaming
  
  // Actions
  setAuth, logout, setTeams, setActiveTeam,
  setTheme, setDarkMode, setDensity,
  toggleChat, setChatOpen, addChatMessage, appendToLastMessage,
  clearChat, setConversationId, setIsStreaming
}
```
- Persisted to localStorage via Zustand `persist` middleware (key: `tars-store`)
- Syncs across browser tabs

### 4.10 API Client (`/api/client.ts`)

```typescript
api.get<T>(path)          // GET with Bearer token
api.post<T>(path, body?)  // POST with JSON body
api.patch<T>(path, body)  // PATCH with JSON body
api.delete<T>(path)       // DELETE

createChatWebSocket()     // ws:// or wss:// to /api/chat/ws?token=...
```
- Automatic 401 handling → logout + "Session expired" error
- Token read from Zustand store on every request


---

## 5. Backend — API, Agent & Database

### 5.1 Entry Points

| Entry Point | Purpose | Command |
|-------------|---------|---------|
| `backend/main.py` | FastAPI web server | `uvicorn backend.main:app --port 8080 --reload` |
| `app.py` | Telegram bot (polling) | `python app.py` |
| `__main__.py` | Module entry | `python -m tars` |

**Startup Flow (FastAPI):**
1. Initialize SQLite database (run migrations)
2. Register all 55+ tools via `register_all_tools()`
3. Mount CORS middleware (localhost:5173, :3000, :8080)
4. Mount API routers: `/api/auth`, `/api/chat`, `/api/data`
5. Serve frontend static files (`frontend/dist/`)
6. Legacy voice UI at `/call` → `web/static/call.html`

### 5.2 API Routes Overview

#### Auth Router (`/api/auth`) — 10 endpoints

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| POST | `/register` | Create user account | No |
| POST | `/login` | Login → JWT + cookie | No |
| POST | `/logout` | Clear auth cookie | Yes |
| GET | `/me` | Current user profile + teams | Yes |
| PATCH | `/me/preferences` | Update theme/dark_mode/density | Yes |
| POST | `/teams` | Create new team | Yes |
| GET | `/teams` | List user's teams | Yes |
| GET | `/teams/{id}/members` | List team members | Yes |
| POST | `/teams/{id}/invite` | Invite by email (admin+) | Yes |
| POST | `/teams/{id}/switch` | Switch active team | Yes |

#### Chat Router (`/api/chat`) — 5 REST + 1 WebSocket

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/conversations` | List conversations | Yes |
| POST | `/conversations` | Create conversation | Yes |
| GET | `/conversations/{id}` | Get conversation + messages | Yes |
| GET | `/conversations/{id}/messages` | Paginated messages | Yes |
| DELETE | `/conversations/{id}` | Archive conversation | Yes |
| WS | `/ws` | Real-time streaming chat | Yes (query param) |

#### Data Router (`/api`) — 50+ endpoints

**Intelligence & Scanning:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/intel` | Intelligence summary (topics, people, tasks) |
| GET | `/intel/graph` | Entity relationship graph |
| POST | `/intel/scan` | Trigger Notion scan |
| POST | `/intel/scan/stream` | SSE streaming scan progress |
| POST | `/intel/scan/cancel` | Cancel active scan |

**Smart Tasks (Eisenhower Matrix):**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/intel/tasks` | List tasks (filter: owner, topic, quadrant) |
| PATCH | `/intel/tasks/{id}` | Update task (status, owner, quadrant, steps) |
| DELETE | `/intel/tasks/{id}` | Delete task |
| POST | `/intel/tasks/rewrite-titles` | AI-rewrite task titles |
| POST | `/intel/tasks/{id}/create-from-step` | Create task from next-step |
| POST | `/intel/tasks/{id}/assign` | Assign to person |

**Tracked Tasks (Notion-backed):**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/tasks` | Get tracked tasks (filter: owner, topic, status) |
| PATCH | `/tasks/{id}` | Update tracked task |
| GET | `/tasks/owners` | Owner frequency distribution |

**Briefing & Reviews:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/briefing` | Daily end-of-day briefing |
| GET | `/review/weekly` | Weekly review statistics |
| GET | `/meeting-review` | Recently created items by meeting |
| GET | `/analytics/completion-trend` | 30-day completion chart data |

**Meeting Prep:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/meeting-prep` | Prep for upcoming meeting (event_id or minutes_ahead) |
| GET | `/meeting-prep/one-on-one/{person}` | Structured 1:1 prep |

**Decisions:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/decisions` | List decisions (filter: status, initiative, stakeholder) |
| POST | `/decisions` | Create decision record |
| PATCH | `/decisions/{id}` | Update decision (status, rationale, outcome) |
| DELETE | `/decisions/{id}` | Delete decision |
| GET | `/decisions/notion-preview` | Preview Notion decisions for import |
| POST | `/decisions/notion-import` | Bulk import from Notion |

**Initiatives & OKRs:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/initiatives` | List initiatives (filter: status, owner, quarter) |
| POST | `/initiatives` | Create initiative |
| PATCH | `/initiatives/{id}` | Update initiative |
| DELETE | `/initiatives/{id}` | Delete initiative |
| POST | `/initiatives/{id}/milestones/{idx}/complete` | Mark milestone done |
| POST | `/initiatives/key-results` | Add key result to initiative |
| PATCH | `/initiatives/key-results/{id}` | Update key result progress |

**Epics & Stories:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/epics` | List epics (filter: status, owner, initiative_id) |
| POST | `/epics` | Create epic |
| PATCH | `/epics/{id}` | Update epic |
| DELETE | `/epics/{id}` | Delete epic |
| GET | `/stories` | List stories (filter: epic_id, status, owner) |
| POST | `/stories` | Create story |
| PATCH | `/stories/{id}` | Update story |
| DELETE | `/stories/{id}` | Delete story |
| POST | `/stories/{id}/link-task` | Link smart task to story |

**Themes:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/themes` | List themes |
| POST | `/themes` | Create theme |
| PATCH | `/themes/{id}` | Update theme |
| DELETE | `/themes/{id}` | Delete theme |

**Portfolio & Workload:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/portfolio` | Team portfolio overview |
| GET | `/portfolio/{name}` | Individual member portfolio |

**Classification:**

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/classify` | Trigger auto-classification |
| GET | `/classify/status` | Classification job progress |
| POST | `/classify/stream` | SSE streaming classification |

**People:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/people` | List all people |
| GET | `/people/{name}` | Get person details |
| POST | `/people` | Add person |
| PATCH | `/people/{name}` | Update person |
| DELETE | `/people/{name}` | Delete person |

**Other:**

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/approve/{entity_type}/{id}` | Approve auto-generated item |
| POST | `/dismiss/{entity_type}/{id}` | Dismiss auto-generated item |
| GET | `/hierarchy` | Full theme→initiative→epic→story→task tree |
| GET | `/alerts` | Proactive alerts (overdue, risks, conflicts) |
| GET | `/strategic-summary` | High-level strategic view |
| GET | `/settings/status` | Integration connection status |
| GET | `/token` | Ephemeral token for OpenAI Realtime API |
| POST | `/tool` | Execute tool on behalf of voice client |


---

## 6. AI Agent System

### 6.1 System Prompt

```
You are TARS, an executive assistant AI. You are direct, efficient, and 
occasionally witty — like the robot from Interstellar, but focused on 
productivity instead of space travel. Your humor setting is at 75%.

You help your user manage their calendar, email, tasks, and documents 
through Microsoft 365. When a user asks you to do something, use the 
available tools to accomplish it. If no tools are available for a request, 
say so clearly and suggest what you can help with.

Keep responses concise. Use bullet points for lists. When presenting 
calendar events or emails, format them cleanly. Always confirm before 
taking actions that send emails, create events, or modify tasks.

AGILE WORK BREAKDOWN — You structure deliverables using Scrum methodology:
  Initiative → Epic (large deliverable) → User Story → Task.
Be pragmatic: use epics/stories for structured deliverables (features, 
projects, migrations) where team members need the bigger picture. 
Operational/admin work (hiring, vendor mgmt, ad-hoc asks) can stay as 
standalone tasks — don't over-structure what doesn't need it.

STRATEGIC LAYER — You have executive-grade strategic tools:
- Meeting prep: Before any meeting, use meeting_prep or next_meeting_brief.
- Decision register: Use log_decision, get_decisions for decision tracking.
- Initiatives & OKRs: Use create_initiative, get_initiatives for goals.
- Proactive alerts: Use get_alerts for risk scanning.

TEAM PORTFOLIO — get_team_portfolio for workload overview, 
get_member_portfolio for individual view.

When referencing an epic, story, initiative, or decision by name, 
first look it up to resolve the ID. Never ask the user for an ID directly.

When using tools, tell the user what you're doing. 
Always confirm before sending emails or creating events.
```

### 6.2 Agent Loop (`backend/agent/core.py`)

**Model:** `claude-sonnet-4-20250514` | **Max tokens:** 4096 | **Streaming:** Yes  
**Max history:** 40 messages loaded from SQLite per conversation

**Flow:**
```
1. Load conversation history from SQLite (up to 40 messages)
2. Append new user message
3. Get tool definitions from registry (Claude format)
4. LOOP:
   a. Call Claude API with messages + tools (streaming)
   b. Stream tokens → yield {"type": "token", "content": "..."}
   c. If stop_reason == "tool_use":
      - Yield {"type": "tool_call", "name": "...", "arguments": {...}}
      - Execute tool via registry.execute(name, args, user_id, team_id)
      - Yield {"type": "tool_result", "name": "...", "result": {...}}
      - Append tool result to messages
      - CONTINUE LOOP
   d. If stop_reason == "end_turn":
      - BREAK
5. Return complete response
```

### 6.3 Tool Registry (`backend/tools/registry.py`)

**Singleton** pattern — all tools registered once on startup, used across WebSocket and Telegram.

**ToolDefinition fields:**
- `name` — unique identifier
- `description` — shown to Claude for tool selection
- `parameters` — JSON Schema for arguments
- `handler` — async function to execute
- `category` — grouping (calendar, email, tasks, etc.)
- `requires_confirmation` — UI should confirm before executing
- `requires_auth` — needs M365 token
- `inject_user_id` — auto-pass user_id to handler
- `inject_chat_id` — auto-pass chat_id to handler (for reminders)

**Export formats:**
- `to_claude_format()` → `[{"name": "...", "description": "...", "input_schema": {...}}]`
- `to_openai_format()` → `[{"type": "function", "function": {"name": "...", "parameters": {...}}}]`

---

## 7. Tool Registry — All 55+ Tools

### Calendar (3 tools)

| Tool | Parameters | Confirmation | Description |
|------|-----------|--------------|-------------|
| `get_calendar_events` | days(int=7), max_results(int=20) | No | Fetch upcoming events |
| `create_calendar_event` | subject, start_time, end_time, timezone(=UTC), location, body, attendees[] | **Yes** | Create event |
| `search_calendar` | query, days(=30), max_results(=10) | No | Search events |

### Tasks (4 tools)

| Tool | Parameters | Confirmation | Description |
|------|-----------|--------------|-------------|
| `get_task_lists` | — | No | List all task lists |
| `get_tasks` | list_id, include_completed(=false), max_results(=25) | No | Get tasks |
| `create_task` | title, list_id, due_date, importance(low/normal/high), body | **Yes** | Create task |
| `complete_task` | task_id, list_id | No | Mark done |

### Email (5 tools)

| Tool | Parameters | Confirmation | Description |
|------|-----------|--------------|-------------|
| `get_emails` | folder(inbox/sentitems/drafts), unread_only(=false), max_results(=15) | No | Fetch messages |
| `read_email` | message_id | No | Read full email |
| `send_email` | to[], subject, body, cc[], importance | **Yes** | Send email |
| `reply_email` | message_id, body, reply_all(=false) | **Yes** | Reply to email |
| `search_emails` | query, max_results(=10) | No | Search mail |

### Reminders (3 tools)

| Tool | Parameters | Confirmation | Description |
|------|-----------|--------------|-------------|
| `create_reminder` | message, remind_at(ISO 8601) | **Yes** | Create reminder |
| `get_reminders` | — | No | List reminders |
| `delete_reminder` | reminder_id | No | Delete reminder |

### Notion (9 tools)

| Tool | Parameters | Description |
|------|-----------|-------------|
| `search_notion` | query, max_results(=10) | Search pages |
| `read_notion_page` | page_id | Read page content |
| `list_notion_databases` | max_results(=20) | List databases |
| `query_notion_database` | database_id, filter, max_results(=50) | Query database |
| `extract_meeting_tasks` | page_id | Extract TODOs from page |
| `track_meeting_tasks` | page_id | Track extracted tasks |
| `get_tracked_tasks` | owner, topic, status, include_completed | Get tracked tasks |
| `search_meeting_notes` | query, max_results(=5) | Search meetings |
| `update_tracked_task` | task_id, status, owner, topic, description, follow_up_date | Update task |

### Intelligence (6 tools)

| Tool | Parameters | Confirmation | Description |
|------|-----------|--------------|-------------|
| `scan_notion` | max_pages(=50) | No | Full Notion scan |
| `get_intel` | — | No | Get intelligence summary |
| `get_smart_tasks` | owner, topic, quadrant(1-4), include_done | No | Filter tasks |
| `update_smart_task` | task_id, status, follow_up_date, owner, quadrant, description, steps | No | Update task |
| `delete_smart_task` | task_id | **Yes** | Delete task |
| `search_intel` | query, max_results(=10) | No | Search knowledge |

### Strategic (10+ tools)

| Tool | Parameters | Confirmation | Description |
|------|-----------|--------------|-------------|
| `log_decision` | title, rationale, decided_by, stakeholders[], context, initiative, status | No | Create decision |
| `get_decisions` | status, initiative, stakeholder | No | List decisions |
| `update_decision` | decision_id, status, rationale, outcome_notes, title | No | Update decision |
| `create_initiative` | title, description, owner, quarter, status, priority, milestones[] | No | Create initiative |
| `get_initiatives` | status, owner, quarter, priority | No | List initiatives |
| `update_initiative` | initiative_id, title, description, owner, quarter, status, priority | No | Update initiative |
| `complete_milestone` | initiative_id, milestone_index | No | Mark milestone done |
| `add_key_result` | initiative_id, description, target, current, owner | No | Add OKR |
| `update_key_result` | kr_id, current, status, description | No | Update OKR |
| `meeting_prep` | event_id, minutes_ahead(=30) | No | Pre-meeting brief |
| `next_meeting_brief` | — | No | Quick next-meeting brief |
| `get_alerts` | — | No | Proactive risk alerts |

### Agile (11 tools)

| Tool | Parameters | Description |
|------|-----------|-------------|
| `create_epic` | title, description, owner, initiative_id, quarter, priority, acceptance_criteria[] | Create epic |
| `get_epics` | status, owner, initiative_id, quarter, priority | List epics |
| `update_epic` | epic_id, title, description, owner, status, priority, quarter, initiative_id, acceptance_criteria[] | Update epic |
| `create_story` | epic_id, title, description, owner, size(XS-XL), priority, acceptance_criteria[] | Create story |
| `get_stories` | epic_id, owner, status, priority, size | List stories |
| `update_story` | story_id, title, description, owner, status, priority, size, acceptance_criteria[] | Update story |
| `link_task_to_story` | story_id, task_id | Link task to story |
| `get_team_portfolio` | owner, quarter, include_done | Team workload overview |
| `get_member_portfolio` | name, include_done | Individual portfolio |
| `create_theme` | title, description, status | Create strategic theme |
| `get_themes` | — | List themes |

### Briefing (2 tools)

| Tool | Parameters | Description |
|------|-----------|-------------|
| `daily_briefing` | — | End-of-day executive briefing |
| `weekly_review` | — | Weekly summary statistics |

### People (3 tools)

| Tool | Parameters | Description |
|------|-----------|-------------|
| `get_people` | — | List all people |
| `get_person` | name | Get person details |
| `update_person` | name, role, relationship, organization, notes, email | Update person |

### Notion Review (4 tools)

| Tool | Parameters | Description |
|------|-----------|-------------|
| `review_notion_pages` | auto_fix(=false) | Review pages for issues |
| `review_notion_page` | page_id, auto_fix(=false) | Review single page |
| `add_known_names` | names[] | Add names to dictionary |
| `get_known_names` | — | List known names |


---

## 8. External Service Integrations

### 8.1 Anthropic Claude API

| Aspect | Detail |
|--------|--------|
| **SDK** | `anthropic` Python SDK |
| **Auth** | `ANTHROPIC_API_KEY` env var |
| **Models Used** | Sonnet 4 (conversation), Haiku 4.5 (extraction), Opus 4 (classification) |
| **Features** | Streaming messages, tool use (function calling), async support |

**Usage by module:**
- `backend/agent/core.py` — Main agent loop with Sonnet 4 (streaming, tool calling)
- `integrations/intel.py` — Metadata extraction with Haiku 4.5 (cost-optimized)
- `integrations/classifier.py` — Full hierarchy classification with Opus 4 (highest accuracy)

### 8.2 Microsoft Graph API (M365)

| Aspect | Detail |
|--------|--------|
| **SDK** | Custom `httpx` async wrapper + MSAL |
| **Auth** | Device-code OAuth2 flow (`MS_CLIENT_ID`, `MS_TENANT_ID`) |
| **Base URL** | `https://graph.microsoft.com/v1.0` |
| **Scopes** | `Calendars.ReadWrite`, `Tasks.ReadWrite`, `Mail.ReadWrite`, `Mail.Send`, `User.Read` |

**Endpoints used:**

| Service | Endpoints |
|---------|-----------|
| Calendar | `GET /me/calendarView`, `POST /me/events`, `GET /me/events` |
| Mail | `GET /me/mailFolders/{folder}/messages`, `GET /me/messages/{id}`, `POST /me/sendMail`, `POST /me/messages/{id}/reply`, `POST /me/messages/{id}/replyAll` |
| Tasks | `GET /me/todo/lists`, `GET /me/todo/lists/{id}/tasks`, `POST /me/todo/lists/{id}/tasks` |

**Auth flow:**
1. `start_device_flow()` → user gets verification code + URL
2. User authenticates at `microsoft.com/devicelogin`
3. `complete_device_flow()` → blocks until auth completes
4. Tokens cached to `token_cache.json` for silent renewal

### 8.3 Notion API

| Aspect | Detail |
|--------|--------|
| **SDK** | Custom `httpx` async wrapper |
| **Auth** | `NOTION_API_KEY` (integration token) |
| **Base URL** | `https://api.notion.com/v1` |
| **API Version** | `2022-06-28` |

**Endpoints used:**
- `POST /search` — Full-text page search
- `GET /pages/{id}` — Page properties and metadata
- `GET /blocks/{id}/children` — Recursive block content extraction
- `POST /databases/{id}/query` — Database queries with filters
- `PATCH /blocks/{id}` — Update block content

**Block types parsed:** headings (H1-H3), bulleted/numbered lists, to-do items, toggles, dividers, code blocks, paragraphs

### 8.4 OpenAI API

| Aspect | Detail |
|--------|--------|
| **SDK** | `openai` Python SDK |
| **Auth** | `OPENAI_API_KEY` env var |

**Services:**

| Service | Model | Endpoint | Purpose |
|---------|-------|----------|---------|
| Whisper | `whisper-1` | `audio.transcriptions.create()` | Voice message → text |
| TTS | `tts-1` | `audio.speech.create()` | Text → voice (opus format) |
| Realtime | `gpt-4o-mini-realtime-preview` | `realtime/sessions` | Live voice calls |

**Voice options:** alloy, ash, coral, echo, fable, onyx (default), nova, sage, shimmer

### 8.5 Telegram Bot API

| Aspect | Detail |
|--------|--------|
| **SDK** | `python-telegram-bot` library |
| **Auth** | `TELEGRAM_BOT_TOKEN` env var |
| **Mode** | Polling (not webhooks) |

**Commands:** `/start`, `/login`, `/briefing`, `/status`, `/clear`

### 8.6 Integration Status Summary

| Service | Auth Type | Library | Config Keys |
|---------|-----------|---------|-------------|
| Anthropic Claude | API Key | `anthropic` | `ANTHROPIC_API_KEY` |
| Microsoft Graph | Device-code OAuth2 | `httpx` + `msal` | `MS_CLIENT_ID`, `MS_TENANT_ID` |
| Notion | API Key | `httpx` | `NOTION_API_KEY` |
| OpenAI | API Key | `openai` | `OPENAI_API_KEY` |
| Telegram | Bot Token | `python-telegram-bot` | `TELEGRAM_BOT_TOKEN` |

---

## 9. Database Schema

**Engine:** SQLite with WAL mode, foreign keys enabled, 5000ms busy timeout  
**Location:** `tars.db` (repository root)  
**Migrations:** 5 versions, applied sequentially on startup  
**ID format:** 12-character hex string (`uuid4().hex[:12]`)

### Core Tables (Migration v1)

```sql
-- Users
users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,    -- PBKDF2-SHA256
    avatar_url TEXT,
    preferences TEXT,               -- JSON: {theme, dark_mode, density}
    created_at TEXT, updated_at TEXT, last_login_at TEXT
)

-- Teams
teams (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    owner_id TEXT REFERENCES users(id),
    settings TEXT,                   -- JSON
    created_at TEXT, updated_at TEXT
)

-- Team membership with roles
team_members (
    user_id TEXT REFERENCES users(id),
    team_id TEXT REFERENCES teams(id),
    role TEXT CHECK(role IN ('owner','admin','member')),
    joined_at TEXT,
    PRIMARY KEY (user_id, team_id)
)

-- Conversations (multi-channel)
conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id),
    team_id TEXT REFERENCES teams(id),
    channel TEXT CHECK(channel IN ('web','telegram','cli','voice')),
    title TEXT,
    is_archived INTEGER DEFAULT 0,
    created_at TEXT, updated_at TEXT
)

-- Messages with tool call tracking
messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(id),
    role TEXT CHECK(role IN ('user','assistant','system','tool')),
    content TEXT,
    tool_calls TEXT,      -- JSON: [{name, arguments, result}]
    tool_results TEXT,    -- JSON
    model TEXT,
    tokens_used INTEGER,
    created_at TEXT
)

-- Semantic memory with FTS5
memory (
    id TEXT PRIMARY KEY,
    scope TEXT CHECK(scope IN ('user','team','global')),
    owner_id TEXT,
    category TEXT DEFAULT 'general',
    key TEXT, value TEXT,
    UNIQUE(scope, owner_id, category, key)
)
-- + memory_fts (FTS5 virtual table) with sync triggers
```

### Strategic Tables (Migration v2)

```sql
-- Smart tasks with Eisenhower matrix
smart_tasks (
    id TEXT PRIMARY KEY,
    team_id TEXT REFERENCES teams(id),
    description TEXT, owner TEXT,
    status TEXT CHECK(status IN ('open','in_progress','done')),
    quadrant INTEGER CHECK(quadrant BETWEEN 1 AND 4),
    topic TEXT, follow_up_date TEXT,
    source_page_id TEXT, source_context TEXT, steps TEXT,
    story_id TEXT,                    -- link to user story
    classification TEXT,              -- unclassified|operational|strategic
    manual_override INTEGER DEFAULT 0,
    confidence REAL DEFAULT 0.0,
    source TEXT DEFAULT 'confirmed',  -- confirmed|auto
    created_at TEXT, updated_at TEXT
)

-- Decision register
decisions (
    id TEXT PRIMARY KEY,
    team_id TEXT, title TEXT, rationale TEXT,
    decided_by TEXT, stakeholders TEXT,   -- JSON array
    context TEXT, initiative_id TEXT,
    status TEXT CHECK(status IN ('decided','pending','revisit')),
    outcome_notes TEXT,
    created_at TEXT, updated_at TEXT
)

-- Strategic initiatives with OKRs
initiatives (
    id TEXT PRIMARY KEY,
    team_id TEXT, title TEXT, description TEXT,
    owner TEXT, quarter TEXT,
    status TEXT CHECK(status IN ('on_track','at_risk','off_track','completed','paused')),
    priority TEXT, milestones TEXT,    -- JSON array [{text, completed, completed_at}]
    theme_id TEXT, source TEXT,
    created_at TEXT, updated_at TEXT
)

-- Key results (OKRs)
key_results (
    id TEXT PRIMARY KEY,
    initiative_id TEXT REFERENCES initiatives(id),
    description TEXT, target TEXT, current TEXT,
    owner TEXT,
    status TEXT CHECK(status IN ('in_progress','achieved','missed')),
    created_at TEXT, updated_at TEXT
)

-- Agile epics
epics (
    id TEXT PRIMARY KEY,
    team_id TEXT, initiative_id TEXT REFERENCES initiatives(id),
    title TEXT, description TEXT, owner TEXT,
    status TEXT CHECK(status IN ('backlog','in_progress','done','cancelled')),
    priority TEXT, quarter TEXT,
    acceptance_criteria TEXT,    -- JSON array
    source TEXT,
    created_at TEXT, updated_at TEXT
)

-- User stories
stories (
    id TEXT PRIMARY KEY,
    epic_id TEXT REFERENCES epics(id),
    title TEXT, description TEXT, owner TEXT,
    status TEXT CHECK(status IN ('backlog','ready','in_progress','in_review','done','blocked')),
    priority TEXT,
    size TEXT CHECK(size IN ('XS','S','M','L','XL')),
    acceptance_criteria TEXT,    -- JSON array
    linked_task_ids TEXT,        -- JSON array
    source TEXT,
    created_at TEXT, updated_at TEXT
)

-- People profiles
people (
    id TEXT PRIMARY KEY,
    team_id TEXT, name TEXT, role TEXT,
    relationship TEXT, organization TEXT,
    email TEXT, notes TEXT,
    manually_added INTEGER DEFAULT 0,
    created_at TEXT, updated_at TEXT,
    UNIQUE(team_id, name)
)

-- Strategic themes
themes (
    id TEXT PRIMARY KEY,
    team_id TEXT, title TEXT, description TEXT,
    status TEXT CHECK(status IN ('active','completed','paused')),
    source TEXT, created_at TEXT, updated_at TEXT
)
```

### System Tables (Migration v3-v5)

```sql
-- Telegram user mapping
telegram_users (
    telegram_id INTEGER PRIMARY KEY,
    user_id TEXT REFERENCES users(id),
    username TEXT, linked_at TEXT
)

-- API key storage
api_keys (
    id TEXT PRIMARY KEY,
    scope TEXT, owner_id TEXT, service TEXT,
    key_name TEXT, encrypted_value TEXT,
    created_at TEXT,
    UNIQUE(scope, owner_id, service, key_name)
)

-- Audit trail
audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT, team_id TEXT, action TEXT,
    entity_type TEXT, entity_id TEXT,
    details TEXT,    -- JSON
    created_at TEXT
)

-- Reminders
reminders (
    id TEXT PRIMARY KEY,
    chat_id TEXT, message TEXT,
    remind_at TEXT, created_at TEXT
)
```

### Query Helpers (`backend/database/queries.py`)

```python
generate_id()                           # → 12-char hex UUID
insert_row(conn, table, data)           # Auto ID, timestamps, JSON serialization
update_row(conn, table, id, updates)    # Auto updated_at timestamp
delete_row(conn, table, id)             # Hard delete
get_row(conn, table, id)                # Single row fetch
list_rows(conn, table, filters, ...)    # Filtered listing with ordering
search_memory(conn, query, ...)         # FTS5 semantic search
get_conversation_messages(conn, id)     # Chronological message fetch
```


---

## 10. Intelligence & Classification Engine

### 10.1 Notion Intelligence Scan (`integrations/intel.py`)

**Purpose:** Scan all Notion pages to build a comprehensive knowledge profile — extracting topics, people, tasks, decisions, and relationships.

**Scan Flow:**
1. Fetch all accessible Notion pages (incremental or full)
2. For each page:
   - Extract title, content, last_edited metadata
   - **Keyword-based topic detection** across 10 categories: strategy, engineering, product, finance, hiring, operations, sales, marketing, management, planning
   - **People extraction** via @mentions and 1:1 meeting patterns
   - **LLM metadata extraction** (Claude Haiku) — returns structured JSON:
     - People mentioned, organizations, projects, topics, decisions, tags, summary
3. Build executive summary with topic/people frequency maps
4. Persist to `notion_intel.json` with scan history

**Smart Task Extraction:**
- Detects action items from page content
- Assigns Eisenhower quadrant (1=urgent+important, 2=important, 3=urgent, 4=neither)
- Tracks owner, delegation status, follow-up dates
- Links back to source page for context

**Output structure:**
```json
{
  "last_scan_at": "ISO timestamp",
  "pages_scanned": 42,
  "topics": {"strategy": 15, "engineering": 23, ...},
  "people": {"Alice": {"mentions": 8, "pages": [...], "has_1on1s": true}, ...},
  "smart_tasks": [{
    "id": "abc123", "description": "...", "owner": "...",
    "quadrant": 2, "status": "open", "steps": ["..."],
    "source_page_id": "...", "classification": "strategic",
    "confidence": 0.85
  }],
  "page_index": {"page_id": {"title": "...", "topics": [...], "summary": "..."}},
  "executive_summary": {...},
  "scan_history": [{"at": "...", "pages": 42}]
}
```

### 10.2 Auto-Classification (`integrations/classifier.py`)

**Purpose:** Automatically organize extracted tasks into a full agile hierarchy using Claude Opus for semantic understanding.

**Pipeline:**

```
Phase 0: Build Knowledge Map
  └─ Aggregate topic/project context from all scanned Notion pages
  └─ Compact to top 50 entries by mention frequency
  └─ Serialize with dates, people involved, summaries

Phase 1: Theme + Initiative Discovery (Claude Opus)
  └─ Input: all smart tasks + knowledge map
  └─ Output: themes[], initiatives[], proposed_initiatives[]
  └─ Also marks: operational_task_ids[], unclassified_task_ids[]

Phase 2: Epic + Story Breakdown (Claude Opus, per initiative)
  └─ Input: initiative + its linked tasks + context
  └─ Output: epics[] with stories[], proposed_stories[]
  └─ Gap-fill: identifies missing epics/stories/tasks for completeness
  └─ Links tasks ↔ stories bidirectionally

Phase 3: Grammar Normalization
  └─ Capitalize first letters
  └─ Remove trailing punctuation
  └─ Ensure consistent title formatting
```

**Key behaviors:**
- Respects `manual_override` flag — never reclassifies manually assigned items
- All auto-generated items marked with `source="auto"` (visually distinct in UI)
- Sets `classification` (strategic/operational/unclassified) and `confidence` (0.0-1.0)
- Progress callback for UI status bar updates

### 10.3 Daily Briefing (`integrations/briefing_daily.py`)

**Purpose:** End-of-day executive summary aggregating all data sources.

**Sections compiled:**
1. **Calendar** — Today's events (time, subject, location, attendees)
2. **Notion Activity** — Recently edited pages with content preview
3. **Task Analysis** — Open/stale/delegated counts with owner breakdown
4. **Email** — Unread count + recent messages
5. **Strategic** — At-risk initiatives count, pending decisions count
6. **Recommendations** — Proactive suggestions:
   - Stale task follow-ups (age ≥ 7 days = high priority)
   - Owner check-ins (3+ open tasks → suggest meeting)
   - Email backlog (10+ unread → suggest review)
   - Missing meeting action items
   - Uncategorized tasks
7. **Voice Summary** — Natural language narrative for TTS

### 10.4 Meeting Prep (`integrations/meeting_prep.py`)

**Purpose:** Pre-meeting context brief with attendee profiles, history, and talking points.

**Data assembled:**
- Meeting details (subject, time, attendees, web link)
- Attendee profiles from people database (role, relationship, open tasks, topics, 1:1 history)
- Past meeting history (by attendee overlap and subject similarity)
- Open items for attendees (smart tasks filtered by owner)
- Pending decisions related to meeting context
- Auto-generated talking points (prioritized by urgency)

**Talking point types:** urgent_task, follow_up, decision, workload, recurring_topic

### 10.5 Weekly Review (`integrations/review.py`)

**Metrics compiled:**
- Open vs. completed task counts
- Quadrant distribution (Q1-Q4)
- Overdue tracking (days per task)
- Delegation overview (tasks per owner)
- Stale task detection (open 7+ days)
- Top 5 topics by frequency

### 10.6 Alerts (`integrations/alerts.py`)

**Alert types:**
- `overdue_tasks` — Tasks past follow-up date
- `stale_decisions` — Pending decisions older than threshold
- `unassigned_work` — Tasks without owners
- At-risk initiatives
- Capacity warnings

**Severity levels:** critical, warning, info  
**Each alert includes:** title, detail, severity, suggested_action

---

## 11. Telegram Bot

### Entry Point & Setup

**File:** `telegram_bot/handlers.py`  
**Started via:** `app.py` (uses `python-telegram-bot` with polling)

### Commands

| Command | Action |
|---------|--------|
| `/start` | Welcome message with available commands |
| `/login` | Initiate M365 device-code flow — shows verification code + URL |
| `/briefing` | Compile and send full daily briefing |
| `/status` | Show connection status (M365, OpenAI, Telegram) |
| `/clear` | Reset conversation history |

### Message Handling

**Text messages:**
1. User sends text → routed to `agent.core.run()` (non-streaming)
2. Agent processes with full tool calling
3. Response sent back (split into 4096-char chunks for Telegram limit)

**Voice messages:**
1. User sends voice → download audio file
2. Transcribe via OpenAI Whisper → text
3. Run through agent → response text
4. Convert response to speech via OpenAI TTS (opus format)
5. Send voice reply to user

### Background Jobs
- `_check_reminders()` — Periodic check for due reminders, sends notification

---

## 12. Voice Interface

### Web Voice Call (`web/server.py`)

**URL:** `/call` (serves `web/static/call.html`)

**Flow:**
1. Frontend calls `GET /api/token` → ephemeral OpenAI Realtime session token (60min TTL)
2. Frontend opens WebRTC connection to OpenAI Realtime API
3. Voice input/output streamed directly to OpenAI
4. Tool calls proxied back to backend via `POST /api/tool`

**Model:** `gpt-4o-mini-realtime-preview`

### Voice Integration (`integrations/voice.py`)

| Function | API | Model | Format |
|----------|-----|-------|--------|
| `transcribe(audio_path)` | OpenAI | whisper-1 | ogg/mp3/wav → text |
| `text_to_speech(text, voice)` | OpenAI | tts-1 | text → opus (ogg container) |

---

## 13. Authentication & Security

### JWT Implementation (`backend/auth/jwt.py`)

| Aspect | Detail |
|--------|--------|
| Algorithm | HS256 (custom implementation) |
| Expiry | 7 days (604800 seconds) |
| Secret | Stored in `.jwt_secret` file (auto-generated) |
| Password hashing | PBKDF2-SHA256 with random salt |

**Token payload:** `{sub: user_id, email, name, team_id, iat, exp}`

### Auth Middleware (`backend/auth/middleware.py`)

**Token extraction order:**
1. `Authorization: Bearer {token}` header
2. `tars_token` HTTP-only cookie
3. `?token=` query parameter (WebSocket only)

**Role hierarchy:** owner (3) ≥ admin (2) ≥ member (1)

**Cookie settings:**
- Name: `tars_token`
- HTTP-only: yes
- SameSite: lax
- Expiry: 7 days

### CORS Configuration
- Allowed origins: `http://localhost:5173`, `http://localhost:3000`, `http://localhost:8080`

---

## 14. Theme System

### Theme Definitions

Each theme configures layout defaults, density, and visual style:

```typescript
{
  id: string,
  label: string,
  description: string,
  layout: {
    commandCenter: string[],        // which panels to show
    defaultWorkTab: 'matrix' | 'board' | 'list' | 'timeline',
    defaultStrategyTab: 'health' | 'portfolio' | 'decisions',
    density: 'compact' | 'comfortable' | 'spacious',
    chatPanel: 'expanded' | 'collapsed'
  },
  cssClass: string,
  forceDark: boolean,
  tone: string
}
```

### Available Themes

| Theme | Accent | Density | Dark Mode | Default Work Tab | Tone |
|-------|--------|---------|-----------|-----------------|------|
| **Executive** (default) | Blue | Comfortable | Optional | Matrix | Professional |
| **War Room** | Red | Compact | Forced | Board | Crisis management |
| **Ops/Sprint** | Purple | Compact | Optional | Board | Agile execution |
| **Personal Focus** | Orange | Spacious | Optional | List | Supportive |

### CSS Variables

```css
--bg-primary, --bg-secondary, --bg-tertiary, --bg-sidebar, --bg-card, --bg-hover
--text-primary, --text-secondary, --text-muted
--border, --accent, --accent-light
--success (#22c55e), --warning (#f59e0b), --danger (#ef4444)
--radius (8px), --radius-lg (12px)
--sidebar-width (240px), --chat-width (380px), --topbar-height (56px)
```

Dark mode and theme-specific overrides via CSS classes (`.dark`, `.theme-war-room`, `.theme-ops`, `.theme-focus`).


---

## 15. Feature Completeness & Gaps

### Fully Working (55+ features)

| Category | Features | Status |
|----------|----------|--------|
| AI Agent | Streaming conversation, tool calling, multi-turn history | Production |
| Calendar | View, create, search events (M365) | Production |
| Email | Read, send, reply, search (M365) | Production |
| Tasks | List, create, complete (M365 To Do) | Production |
| Notion | Search, read pages, query databases, extract tasks | Production |
| Intelligence | Full Notion scan, topic/people extraction, smart tasks | Production |
| Classification | Auto-hierarchy (Theme→Initiative→Epic→Story→Task) | Production |
| Decisions | Full CRUD, status tracking, Notion import | Production |
| Initiatives | Full CRUD, OKRs, milestones, quarter tracking | Production |
| Epics & Stories | Full CRUD, sizing (XS-XL), acceptance criteria | Production |
| Themes | Full CRUD, initiative linking | Production |
| People | Profiles, relationship tracking, inference from scans | Production |
| Briefing | Daily compilation from all sources + recommendations | Production |
| Weekly Review | Task stats, delegation overview, topic frequency | Production |
| Meeting Prep | Attendee profiles, history, talking points, 1:1 prep | Production |
| Alerts | Overdue tasks, stale decisions, at-risk initiatives | Production |
| Voice | Whisper transcription, TTS with voice options | Production |
| Reminders | Create, list, delete with background check | Production |
| Auth | JWT, teams, roles, user preferences | Production |
| Frontend | 5 pages, 4 themes, streaming chat, detail panels | Production |
| Database | SQLite WAL, FTS5, 5 migrations | Production |

### Partially Implemented (7 features)

| Feature | What exists | What's missing |
|---------|-------------|----------------|
| **Obsidian Integration** | Designed in rewrite plan | No implementation — no vault.py, no tool handlers |
| **APScheduler** | Endpoints exist for manual trigger | No background job scheduling (morning briefing, periodic scan, reminder check) |
| **CLI Interface** | Designed (tars chat, tars briefing, tars scan, tars serve) | No Typer/Rich implementation |
| **Semantic Memory** | DB table + FTS5 index created | Agent doesn't query/inject facts from history |
| **Telegram Webhooks** | Polling works | No webhook mode, no job queue integration |
| **Voice Realtime** | Transcribe + TTS work, legacy call.html served | OpenAI Realtime session management incomplete |
| **Structured Logging** | Basic Python logging | No structlog, no OpenTelemetry, no cost tracking |

### Not Started (2 features)

| Feature | Status |
|---------|--------|
| **Health endpoint** (`/health`) | Planned but not implemented |
| **Docker/systemd deployment** | No containerization or service files |

### Known Issues

1. **Form validation** — Client-side only, minimal; no Pydantic validation on most POST bodies
2. **Hardcoded greeting** — CommandCenter says "Jonas" (should use user.name)
3. **Notifications button** — Placeholder only (bell icon in TopBar)
4. **Search bar** — TopBar search not fully wired to backend
5. **JSON ↔ SQLite migration** — Old JSON files still exist alongside SQLite; no automatic sync
6. **Race conditions** — SQLite WAL handles single-instance concurrency; no distributed lock for multi-instance

---

## 16. File Map

### Backend

```
backend/
├── main.py                    # FastAPI app entry, startup, router mounting
├── agent/
│   └── core.py                # AI agent loop (streaming, tool calling, history)
├── api/
│   ├── auth.py                # Auth endpoints (register, login, teams)
│   ├── chat.py                # Chat endpoints + WebSocket
│   └── data.py                # All data REST endpoints (1600+ lines)
├── auth/
│   ├── jwt.py                 # JWT create/verify, password hashing
│   └── middleware.py          # Auth middleware, role checks
├── database/
│   ├── engine.py              # SQLite init, migrations v1-v5
│   └── queries.py             # CRUD helpers, FTS5 search
├── tools/
│   ├── registry.py            # Unified tool registry (Claude + OpenAI export)
│   └── handlers.py            # All 55+ tool handler implementations
└── channels/
    └── __init__.py             # (empty — planned channel abstraction)
```

### Integrations

```
integrations/
├── ms_auth.py                 # MSAL device-code flow for M365
├── ms_graph.py                # Microsoft Graph HTTP wrapper
├── calendar.py                # Calendar read/create/search
├── mail.py                    # Email read/send/reply/search
├── tasks.py                   # M365 To Do tasks
├── notion.py                  # Notion API client (search, read, query)
├── notion_tasks.py            # Extract + track tasks from Notion pages
├── notion_review.py           # Review Notion pages for consistency
├── intel.py                   # Intelligence scanning engine
├── classifier.py              # Auto-classification pipeline (Opus)
├── voice.py                   # OpenAI Whisper + TTS
├── decisions.py               # Decision register
├── initiatives.py             # Initiatives + OKRs
├── epics.py                   # Epics + user stories
├── themes.py                  # Strategic themes
├── people.py                  # People profiles
├── team_portfolio.py          # Workload overview
├── alerts.py                  # Proactive risk alerts
├── reminders.py               # Reminder scheduling
├── briefing_daily.py          # Daily briefing compilation
├── briefing.py                # Briefing helpers
├── review.py                  # Weekly review summary
└── meeting_prep.py            # Pre-meeting context brief
```

### Frontend

```
frontend/src/
├── App.tsx                    # Router + ProtectedRoute + AppLayout
├── main.tsx                   # React entry point
├── index.css                  # TailwindCSS + CSS variables + themes
├── api/
│   └── client.ts              # Typed API client (get/post/patch/delete + WebSocket)
├── store/
│   └── index.ts               # Zustand store (auth, theme, chat state)
├── hooks/
│   └── useApi.ts              # React data fetching hook
├── themes/
│   └── index.ts               # Theme definitions (Executive, War Room, Ops, Focus)
├── pages/
│   ├── Login.tsx              # Auth page (login/register)
│   ├── CommandCenter.tsx      # Home dashboard (alerts, stats, strategic overview)
│   ├── Work.tsx               # Task management (Matrix/Board/List/Timeline)
│   ├── Strategy.tsx           # Strategic planning (Hierarchy/Health/Decisions/Portfolio/Review)
│   ├── People.tsx             # Network directory (Directory/Graph/MeetingPrep)
│   └── SettingsPage.tsx       # Appearance + integrations + team management
└── components/
    ├── Sidebar.tsx            # Left navigation (240px)
    ├── TopBar.tsx             # Top bar (search, actions, chat toggle)
    ├── ChatPanel.tsx          # WebSocket streaming chat (380px right panel)
    ├── DetailPanel.tsx        # Slide-over entity editor (480px)
    └── CommandPalette.tsx     # ⌘K action launcher
```

### Other

```
telegram_bot/
└── handlers.py                # Telegram bot command/message handlers

web/
├── server.py                  # Legacy FastAPI server (voice call)
└── static/
    ├── call.html              # Voice call UI
    └── js/                    # Voice call JavaScript

tests/
├── test_calendar.py           # Calendar integration tests
├── test_mail.py               # Email integration tests
├── test_tasks.py              # Task integration tests
├── test_notion.py             # Notion integration tests
├── test_notion_tasks.py       # Notion task extraction tests
├── test_intel.py              # Intelligence engine tests
├── test_voice.py              # Voice integration tests
├── test_people.py             # People module tests
├── test_reminders.py          # Reminder tests
├── test_epics.py              # Epic/story tests
├── test_briefing.py           # Briefing tests
├── test_briefing_daily.py     # Daily briefing tests
└── test_ms_auth.py            # Auth tests

config.py                      # Environment variable loader
app.py                         # Telegram bot entry point
__main__.py                    # Module entry (python -m tars)
tars.db                        # SQLite database (auto-created)
```

---

## Appendix: Data Flow Diagrams

### User sends a chat message (Web)

```
Browser                  FastAPI                   Agent                    Claude API
  │                        │                         │                         │
  │── WS: {message} ──────>│                         │                         │
  │                        │── run_streaming() ──────>│                         │
  │                        │                         │── messages.stream() ───>│
  │                        │                         │<── token ──────────────│
  │<── {type: token} ──────│<── yield token ─────────│                         │
  │                        │                         │<── tool_use ───────────│
  │<── {type: tool_call} ──│<── yield tool_call ─────│                         │
  │                        │                         │── execute(tool) ──> Integration
  │                        │                         │<── result ─────────────│
  │<── {type: tool_result} │<── yield tool_result ───│                         │
  │                        │                         │── messages.stream() ───>│
  │                        │                         │<── tokens ─────────────│
  │<── {type: token}(s) ───│<── yield tokens ────────│                         │
  │<── {type: complete} ───│── save to DB ───────────│                         │
  │                        │                         │                         │
```

### Notion Intelligence Scan

```
User triggers scan
  │
  ▼
scan_notion(max_pages=50)
  │
  ├── Notion API: POST /search (fetch all pages)
  │
  ├── For each page:
  │     ├── Notion API: GET /blocks/{id}/children (content)
  │     ├── Keyword topic detection (10 categories)
  │     ├── People extraction (@mentions, 1:1 patterns)
  │     └── Claude Haiku: Extract metadata (people, orgs, projects, decisions)
  │
  ├── Build smart tasks with Eisenhower quadrants
  ├── Build topic/people frequency maps
  ├── Generate executive summary
  │
  └── Save to notion_intel.json
```

### Auto-Classification Pipeline

```
classify_tasks()
  │
  ├── Phase 0: Build knowledge map from page_index
  │     └── Top 50 topics with dates, people, summaries
  │
  ├── Phase 1: Claude Opus → Theme + Initiative discovery
  │     ├── Input: all tasks + knowledge map
  │     └── Output: themes[], initiatives[], task classifications
  │
  ├── Phase 2: Claude Opus → Epic + Story breakdown (per initiative)
  │     ├── Input: initiative + linked tasks
  │     ├── Output: epics[], stories[], gap-fill proposals
  │     └── Links: tasks ↔ stories (bidirectional)
  │
  └── Phase 3: Grammar normalization
        └── Capitalize, remove trailing punctuation
```

---

*This document was generated on 2026-03-26 as a comprehensive handoff for the TARS Executive Assistant Platform.*
