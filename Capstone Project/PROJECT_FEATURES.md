# CodePilot — Project Features & Capabilities

This document provides a comprehensive walkthrough of the user-facing and architectural features built into **CodePilot**, including core capabilities, safety guardrails, and bonus challenges.

---

## 🌟 Executive Feature Matrix

| Feature | Category | Description | Status |
|---|---|---|---|
| **Autonomous Issue Polling** | Automation | Continuously queries GitHub for open, unassigned, or `ai-assignable` issues | ✅ Complete |
| **Task Classification** | AI / NLP | Categorizes tasks into `bug_fix`, `feature_addition`, `dependency_update`, etc. | ✅ Complete |
| **Complexity Triage Scoring** | Bonus | Scores issues 1–10 and skips excessively complex tasks ($> 7$) | ✅ Complete |
| **Repo Map Generation** | Context Eng. | Recursively walks repositories and extracts AST symbols within a 4000-token budget | ✅ Complete |
| **Disk Caching & Invalidation** | Performance | SHA-256 caching over git status; loads repo map in $< 5\text{ms}$ | ✅ Complete |
| **Dual Code Retrieval** | Context Eng. | Fast keyword relevance scoring and ChromaDB vector chunk search | ✅ Complete |
| **Local Sandbox Isolation** | Security | Executes code in `.codepilot_sandbox/<task_id>/` with declarative permissions | ✅ Complete |
| **Unified Diff Preview** | Developer Exp. | Generates unified diffs saved to `working/proposed_diff.txt` | ✅ Complete |
| **Security Guardrails** | Security | Blocks destructive commands (`rm -rf`, `curl`, `pip install`) and sensitive files | ✅ Complete |
| **Human-in-the-Loop (HITL)** | Safety | Interactive approval gates for PR to `main`, $>5$ files, `git push`, retries $\ge 2$ | ✅ Complete |
| **4 Pre-built Skills** | Architecture | Structured workflows for Bug Fixes, Features, Dependencies, and Docs | ✅ Complete |
| **Three-Tier Memory** | Memory | Task-scoped Working, session-scoped Episodic, and ChromaDB Semantic memory | ✅ Complete |
| **Self-Healing Tests** | Bonus | Detects test setup and import errors, applying meta-debugging fixes | ✅ Complete |
| **Structured PR Generation** | Delivery | Formats `fix(#id): ...` commits and opens PRs with verification diffs | ✅ Complete |
| **4-Panel Textual TUI** | User Interface | Real-time terminal dashboard with streaming logs and interactive approvals | ✅ Complete |
| **Direct Task Execution** | Flexibility | `[i] New task` shortcut to execute custom free-form instructions directly | ✅ Complete |
| **Dual Mode Operation** | Portability | Supports Live GitHub API via PyGitHub as well as offline demo simulation | ✅ Complete |
| **LangSmith Tracing** | Observability | Integrated tracing configuration with LangSmith | ✅ Complete |

---

## 🛠️ Deep Dive into Core Features

### 1. Autonomous Issue Polling & Triage
CodePilot acts as an autonomous background engineer for engineering teams:
- **Background Polling Loop**: Polls every $N$ minutes (configurable via `CODEPILOT_POLL_INTERVAL`).
- **Targeted Filtering**: Monitors open, unassigned issues or issues tagged `ai-assignable`.
- **Deduplication**: Automatically excludes issues currently in progress across worker threads.
- **Episodic Failure Memory**: Reads the last 3 session summaries at startup; if an issue failed in recent sessions, it is skipped to avoid repeated failure loops.

### 2. Context Engineering & 4000-Token Repo Map
Solving issues in repositories with hundreds of files requires aggressive context discipline:
- **AST Parsing**: Parses every Python file using `ast.parse` to extract class definitions, methods, function signatures, and docstrings.
- **Strict Token Budgeting**: Maintains a strict 4000-token budget. If the codebase exceeds the budget, CodePilot progressively truncates symbol signatures while preserving file paths and directory trees.
- **Disk Caching**: Hashes git status and commit SHAs to cache the map at `.codepilot_cache/repo_map_{id}.json`. Subsequent reads take $< 5\text{ms}$.
- **Context Hygiene**: The Orchestrator passes strictly file paths to child subagents, prompting them to read files on-demand via `read_file` rather than flooding the context window with raw dumps.

### 3. Isolated Sandboxed Execution
CodePilot never executes unverified code in the live project directory:
- **Workspace Isolation**: Creates a temporary sandbox directory at `.codepilot_sandbox/<task_id>/`.
- **Selective Copying**: Copies only the relevant files identified by the Repo Explorer plus build manifests (`pyproject.toml`, `requirements.txt`).
- **Declarative Permissions**:
  - `/sandbox/` &rarr; `read_write`
  - Outside sandbox &rarr; `read_only`
- **Path Traversal Protection**: Enforces path resolution checks to block directory escape attempts.

### 4. Surgical Code Editing & Diff Preview
- **Targeted Modifications**: Rather than rewriting entire files, the Coder Agent formulates targeted `SEARCH / REPLACE` blocks.
- **Diff Generation**: Automatically compares the modified files against baseline snapshots using `difflib.unified_diff`.
- **Proposed Diff File**: Saves the unified diff to `working/proposed_diff.txt` for review before commits or PR creation.

### 5. Security Guardrails & Human-in-the-Loop (HITL)
CodePilot enforces defense-in-depth safety:
- **Dangerous Command Blocking**: Blocks shell execution containing:
  - `rm -rf`
  - `curl` / `wget`
  - `pip install` (unverified network installs)
  - `npm install -g`
  - `format` / `del /s`
- **Sensitive File Protection**: Blocks write access to:
  - `.env*`
  - `*.secret`, `*.pem`, `*.key`
  - `*credentials*`, `*id_rsa*`
- **Protected Human-in-the-Loop Gates**:
  1. Opening PR to production branches (`main` or `master`).
  2. Committing more than 5 files in a single task.
  3. Any shell command containing `git push`.
  4. Retrying after 2 failed test runs.
  5. Any attempt to modify a protected sensitive file.

### 6. Procedural Skills System
CodePilot includes 4 pre-built, structured engineering skills stored with YAML frontmatter in `SKILL.md` format:

```text
codepilot/skills/
├── bug_fix_skill/            # reproduce → localize → fix → verify
├── feature_addition_skill/   # explore_pattern → design → implement → test → document
├── dependency_update_skill/  # check_changelog → update → resolve_conflicts → test_all
└── documentation_skill/      # read_existing → draft → review_accuracy → update_index
```
Each skill provides domain-specific instructions, checklists, and forbidden actions that are injected into child agent prompts.

### 7. Three-Tier Memory Architecture
CodePilot improves over time through three distinct memory layers:
1. **Working Memory (Task-Scoped)**: Tracks in-memory state during execution, including active todos, file paths, and test outputs. Cleared upon task completion.
2. **Episodic Memory (Session-Scoped)**: Persists session summaries to `.codepilot_data/memory/session_{id}.json`. Inspects the last 3 sessions on startup to avoid retrying recently failed tasks.
3. **Semantic Memory (Cross-Session)**: Persistent ChromaDB vector database (`codepilot_lessons_learned`). Automatically extracts and stores lessons learned upon successful PR completion. Retrieves the top-3 relevant past lessons and injects them into the Coder's prompt.

### 8. PR Agent & Structured Delivery
- **Branch Naming**: Formats branches as `codepilot/issue-{number}-{slug}` (e.g. `codepilot/issue-45-add-csv-export-functionality-to-metrics-`).
- **Structured Commit Messages**: Adheres strictly to the specification:
  ```
  fix(#{issue_number}): {one-line summary}

  - {bullet: what changed}
  - {bullet: why}
  - Closes #{issue_number}
  ```
- **Rich PR Description**: Includes issue summary, implementation approach, test execution logs, and diff previews.
- **Review Requests**: Automatically requests review from the original issue reporter.
- **Conflict Handling**: Detects merge conflicts and marks the task as `FAILED` without attempting unsafe automatic resolution.

### 9. Interactive 4-Panel Textual TUI
Built with **Textual** for a terminal experience:

```
┌────────────────────────────────┬────────────────────────────────────────────┐
│  🐙 GitHub Issues Feed         │  ⚡ Active Task Details                     │
│  ────────────────────────────  │  ────────────────────────────────────────  │
│  #42 Fix null pointer ●        │  Issue #45: Add CSV export metrics API     │
│  #45 Add CSV export ●          │  Status: IMPLEMENTING                      │
│  #48 Upgrade pydantic ●        │  Agent: Coder (retry 1/3)                  │
│                                │  Skill: feature_addition_skill             │
│                                │  Todo: [✓] Explore pattern                 │
│                                │        [✓] Design interface                │
│                                │        [ ] Implement & test                │
├────────────────────────────────┼────────────────────────────────────────────┤
│  📜 Agent Activity & Logs      │  🛡️ Human-In-The-Loop Approval Gate       │
│  ────────────────────────────  │  ────────────────────────────────────────  │
│  [Orchestrator] Spawning...    │  ⚠ Coder wants to open PR to main          │
│  [RepoExplorer] 4 files found  │  (target is default production branch)     │
│  [Coder] Applied surgical fix  │                                            │
│  [TestAgent] All tests passed  │  [Approve (a)]  [Reject (r)]  [Inspect]    │
└────────────────────────────────┴────────────────────────────────────────────┘
  [i] New task   [s] Skip issue   [q] Quit   [l] Logs   [a] Approve   [r] Reject
```

- **Issues Panel**: Updates in real-time as the polling loop detects issues.
- **Active Task Panel**: Displays active issue metadata, current agent, and dynamic checklist items with `[✓]` and `[ ]`.
- **Logs Panel**: Streams agent thoughts, reasoning, and tool calls.
- **Approval Panel**: Prompts the user with `Approve (a)`, `Reject (r)`, and `Inspect` buttons during HITL interrupts.
- **Direct Task Input**: Press `i` to open an input modal and type a direct coding instruction.

---

## 🚀 Bonus Challenges Implemented

### Bonus 1: Issue Triage Complexity Scoring
Before attempting an issue, CodePilot calculates an estimated complexity score on a 1–10 scale:
- Evaluates keywords, scope, architectural impact, and Repo Map size.
- If complexity exceeds `config.complexity_threshold` (default 7), the issue is skipped:
  ```text
  [Orchestrator] Skipping Issue #59: Complexity score 10/10 exceeds threshold (7)
  Task finished with status: SKIPPED
  ```

### Bonus 2: Self-Healing Tests
If a test failure is caused by a syntax error, import failure, or missing test runner:
- The Test Agent catches the condition via `_is_test_setup_error()`.
- Automatically applies `_self_heal_test_setup()`, resolving runner configuration or AST syntax before retrying.

### Bonus 3: Dual Mode (Live GitHub + Offline Simulation)
- **Live Mode**: When `GITHUB_TOKEN` is supplied and `CODEPILOT_DEMO_MODE=false`, CodePilot integrates with GitHub repositories using PyGitHub.
- **Offline / Demo Mode**: When running locally without external credentials, CodePilot uses a local simulated GitHub provider. This ensures evaluation, automated testing, and demos run smoothly anywhere.

### Bonus 4: LangSmith Tracing & Observability
- Fully instrumented for LangSmith tracing via environment variables:
  ```env
  LANGSMITH_TRACING=true
  LANGSMITH_API_KEY=your_key
  LANGSMITH_PROJECT=codepilot-devstream
  ```
- All multi-agent invocations, tool calls, and prompt streams can be inspected in the LangSmith dashboard.

---

## 💻 User Interaction Walkthroughs

### Scenario 1: Autonomous TUI Operation
1. Launch the TUI:
   ```powershell
   .\.venv\Scripts\python.exe -m codepilot.cli --mode tui
   ```
2. The Issues panel populates with open issues.
3. The Orchestrator automatically triages Issue #45, loads `feature_addition_skill`, and starts the Repo Explorer.
4. When the PR Agent prepares to open the PR to `main`, the **Human Approval Panel** highlights in red.
5. Press `a` on the keyboard (or click **Approve**); the PR is submitted and the lesson is stored in ChromaDB.

### Scenario 2: Direct Task via Shortcut (`[i]`)
1. In the TUI, press `i`.
2. A modal dialog appears:  
   *`"Enter Direct Coding Task for CodePilot:"`*
3. Type:  
   `"Add CSV export functionality to metrics report API"`
4. Click **Submit Task**.
5. CodePilot packages the request into an ad-hoc task and executes the full pipeline.

### Scenario 3: Headless CI Execution
To run in automated CI pipelines or headless servers:
```powershell
# Solve a specific issue
.\.venv\Scripts\python.exe -m codepilot.cli --mode headless --issue 45

# Or run a custom task directly
.\.venv\Scripts\python.exe -m codepilot.cli --task "Fix null pointer in auth redirect"
```
Output is rendered using Rich console tables and formatted logs.
