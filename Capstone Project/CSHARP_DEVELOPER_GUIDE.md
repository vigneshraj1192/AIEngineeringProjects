# CodePilot — A Guide for C# / .NET Developers (12+ Years Experience)

Welcome! If you come from a strong **C# / .NET** background (ASP.NET Core, Roslyn, MediatR, WPF/Terminal.Gui, Entity Framework, Semantic Kernel), Python code can sometimes look unstructured or overly dynamic. 

However, **CodePilot was built using strict typed patterns, object-oriented design, domain-driven boundaries, and enterprise architectural principles**. 

This guide maps every single file, class, concurrency construct, and pattern in CodePilot directly to its **C# / .NET 8 / 9 equivalent**.

---

## 🏛️ High-Level "Rosetta Stone" (.NET vs. CodePilot)

| Python Concept / Tool | .NET / C# Equivalent | How It's Used in CodePilot |
|---|---|---|
| **`pydantic.BaseModel`** | `record` or `class` with `System.Text.Json` & Data Annotations | Strongly-typed DTOs, request models, validation schemas ([`state.py`](file:///c:/AI%20Engineering%20Course/Projects/Capstone%20Project/codepilot/state.py)). |
| **`Enum(str, Enum)`** | `public enum TaskStatus` with `[JsonStringEnumConverter]` | String-backed state machine and task category enums. |
| **`ast` (Abstract Syntax Tree)** | **Roslyn (`Microsoft.CodeAnalysis.CSharp.SyntaxTree`)** | Static code analysis extracting class/method signatures without compiling ([`repo_map.py`](file:///c:/AI%20Engineering%20Course/Projects/Capstone%20Project/codepilot/context/repo_map.py)). |
| **`EventBus`** | **MediatR (`INotificationHandler<T>`)** / C# `event Action<T>` | Decoupled in-process publish/subscribe message bus ([`event_bus.py`](file:///c:/AI%20Engineering%20Course/Projects/Capstone%20Project/codepilot/tui/event_bus.py)). |
| **`threading.Event`** | **`ManualResetEventSlim`** / **`TaskCompletionSource<T>`** | Halts agent threads while waiting for human UI approval ([`hitl.py`](file:///c:/AI%20Engineering%20Course/Projects/Capstone%20Project/codepilot/guardrails/hitl.py)). |
| **`threading.Lock`** | **`lock (_lock)`** / **`Monitor`** | Thread synchronization around event handler collections. |
| **`Textual`** | **`Terminal.Gui`** / **WPF / Blazor** | Terminal GUI with reactive layout, widgets, and CSS-like styling ([`app.py`](file:///c:/AI%20Engineering%20Course/Projects/Capstone%20Project/codepilot/tui/app.py)). |
| **`self.call_from_thread()`** | **`Dispatcher.InvokeAsync()`** / `MainThread.BeginInvokeOnMainThread()` | Marshaling background agent events back to the UI thread. |
| **`subprocess.run`** | **`System.Diagnostics.Process.Start()`** | Executing sandboxed test runners and shell commands. |
| **`difflib.unified_diff`** | **`DiffPlex`** | Generating standard git unified diffs between initial and modified files. |
| **`ChromaDB`** | **Microsoft Semantic Kernel / Qdrant / Pinecone** | Local persistent vector database storing text embeddings for lessons and code chunks. |
| **`DeepAgents` / `LangGraph`** | **Semantic Kernel Agent Framework / AutoGen** | Hierarchical multi-agent coordinator delegating to subagents via tools. |
| **`pytest`** | **`xUnit` / `NUnit`** | Test runner for executing unit and integration tests. |
| **`pyproject.toml`** | **`.csproj`** | Package dependencies, metadata, and tool configuration. |
| **`python-dotenv`** | **`appsettings.json` / `IConfiguration`** | Configuration settings loaded into strongly-typed objects. |

---

## 📂 File-by-File Technical Comparison

---

### 1. `codepilot/config.py`
#### 🔹 C# Equivalent: `IOptions<CodePilotOptions>` & `IConfiguration`
In ASP.NET Core, you configure strongly-typed settings using `services.Configure<CodePilotOptions>(Configuration.GetSection("CodePilot"))`.

In [`codepilot/config.py`](file:///c:/AI%20Engineering%20Course/Projects/Capstone%20Project/codepilot/config.py), we use Pydantic `BaseModel` with environment variable defaults:

```csharp
// C# Equivalent
public class CodePilotOptions
{
    public string ModelName { get; set; } = "gemini-3.8-flash";
    public string GithubRepository { get; set; } = "devstream-labs/sample-repo";
    public int PollIntervalSeconds { get; set; } = 300;
    public int RepoMapTokenBudget { get; set; } = 4000;
    public int ComplexityThreshold { get; set; } = 7;
    public bool DemoMode { get; set; } = true;
}
```

---

### 2. `codepilot/state.py`
#### 🔹 C# Equivalent: Domain Enums, Immutable Records, and State DTOs
In C#, you would write domain records with `[JsonConverter(typeof(JsonStringEnumConverter))]`.

* **`TaskStatus` & `TaskType`** &rarr; Strongly-typed C# Enums:
  ```csharp
  public enum TaskStatus { PENDING, TRIAGED, EXPLORING, IMPLEMENTING, TESTING, PR_OPENED, DONE, FAILED, SKIPPED }
  public enum TaskType { BugFix, FeatureAddition, DependencyUpdate, Documentation, ConfigChange }
  ```
* **`IssueItem`** &rarr; Immutable C# Record:
  ```csharp
  public record IssueItem(
      int Number, 
      string Title, 
      string Body, 
      List<string> Labels, 
      string State = "open", 
      string Author = "engineer", 
      int? ComplexityScore = null);
  ```
* **`TaskWorkingMemory`** &rarr; State Machine Context (like a workflow state in **MassTransit** or **Stateless**):
  Tracks the current state of a task as it transitions from `TRIAGED` to `DONE`.

---

### 3. `codepilot/tui/event_bus.py`
#### 🔹 C# Equivalent: In-Memory Message Bus / MediatR / Pub-Sub
In C#, you might use `MediatR` (`IMediator.Publish`) or a simple delegate bus:

```csharp
// C# Equivalent of EventBus in codepilot/tui/event_bus.py
public class EventBus
{
    private readonly Dictionary<string, List<Action<Dictionary<string, object>>>> _subscribers = new();
    private readonly object _lock = new();

    public void Subscribe(string eventType, Action<Dictionary<string, object>> handler)
    {
        lock (_lock)
        {
            if (!_subscribers.ContainsKey(eventType))
                _subscribers[eventType] = new List<Action<Dictionary<string, object>>>();
            _subscribers[eventType].Add(handler);
        }
    }

    public void Emit(string eventType, Dictionary<string, object> data)
    {
        List<Action<Dictionary<string, object>>> handlers;
        lock (_lock)
        {
            if (!_subscribers.TryGetValue(eventType, out var list)) return;
            handlers = list.ToList(); // thread-safe snapshot copy
        }
        foreach (var handler in handlers) handler(data);
    }
}
```
**Why it matters**: The background agents running in background threads emit progress logs and status changes. The UI subscribes to these events and renders them without locking the worker threads.

---

### 4. `codepilot/guardrails/rules.py` & `hitl.py`
#### 🔹 C# Equivalent: Authorization Policy Filters & `ManualResetEventSlim`

#### `rules.py` (Security Filters)
Acts like an ASP.NET Core Action Filter or Security Pipeline:
- Evaluates command strings against dangerous regexes (`rm -rf`, `curl`, `wget`, `pip install`).
- Evaluates file paths against blacklisted globs (`.env*`, `*.secret`, `*.pem`, `*.key`).

#### `hitl.py` (Human-in-the-Loop Pause & Resume)
How do we pause an autonomous AI agent in the middle of execution, show a prompt on the UI, wait for the user to press a button, and then resume execution?

In C#, you would use **`ManualResetEventSlim`** or **`TaskCompletionSource<bool>`**:

```csharp
// C# Equivalent of HITLController in codepilot/guardrails/hitl.py
public class HitlController
{
    private readonly ConcurrentDictionary<string, ManualResetEventSlim> _waitHandles = new();
    private readonly ConcurrentDictionary<string, string> _decisions = new();

    public bool RequestApproval(string taskId, string operation, string reason)
    {
        var requestId = Guid.NewGuid().ToString()[..8];
        var waitHandle = new ManualResetEventSlim(false);
        _waitHandles[requestId] = waitHandle;

        // 1. Emit event to UI (Textual TUI receives this and highlights red panel)
        EventBus.Emit("hitl_prompt", new { id = requestId, operation, reason });

        // 2. BLOCK the current agent worker thread!
        waitHandle.Wait();

        // 3. User clicked Approve ('a') or Reject ('r') in UI
        _decisions.TryGetValue(requestId, out var decision);
        return decision == "approve";
    }

    public void Resolve(string requestId, string decision)
    {
        _decisions[requestId] = decision;
        if (_waitHandles.TryGetValue(requestId, out var handle))
        {
            handle.Set(); // Unblocks the waiting agent thread!
        }
    }
}
```

---

### 5. `codepilot/context/repo_map.py` & `retrieval.py`
#### 🔹 C# Equivalent: Roslyn Syntax Analysis (`Microsoft.CodeAnalysis`)

In C#, you inspect code structures using **Roslyn**:
```csharp
// C# Equivalent using Microsoft.CodeAnalysis.CSharp
SyntaxTree tree = CSharpSyntaxTree.ParseText(sourceCode);
CompilationUnitSyntax root = tree.GetCompilationUnitRoot();
var classes = root.DescendantNodes().OfType<ClassDeclarationSyntax>();
var methods = root.DescendantNodes().OfType<MethodDeclarationSyntax>();
```

In [`codepilot/context/repo_map.py`](file:///c:/AI%20Engineering%20Course/Projects/Capstone%20Project/codepilot/context/repo_map.py), Python's built-in **`ast`** does the exact same thing:
- Recursively walks `.py` files.
- Extracts `ast.ClassDef`, `ast.FunctionDef`, and docstrings.
- Builds an in-memory directory tree.
- Calculates an estimated token count ($len / 4$). If $> 4000$ tokens, it progressively strips method signatures to fit within budget.
- Caches the serialized map to `.codepilot_cache/` using an MD5 hash of git commit + git status (instant cache hit $< 5\text{ms}$).

---

### 6. `codepilot/sandbox/local_sandbox.py`
#### 🔹 C# Equivalent: Isolated Workspace with `ProcessStartInfo` and `DiffPlex`

In C#, when you need to run an isolated tool:
1. Create a temporary folder in `Path.GetTempPath()`.
2. Copy files there.
3. Start a process via `System.Diagnostics.ProcessStartInfo` with `WorkingDirectory = sandboxDir` and custom `EnvironmentVariables["PYTHONPATH"]`.
4. Capture `stdout` and `stderr`.
5. Compute a unified diff using a diff library (like **DiffPlex**).

In [`codepilot/sandbox/local_sandbox.py`](file:///c:/AI%20Engineering%20Course/Projects/Capstone%20Project/codepilot/sandbox/local_sandbox.py):
- `_resolve_sandbox_path()` enforces path validation: ensures no `../../` escapes the sandbox folder (raising `GuardrailViolation`).
- `generate_diff()` compares baseline snapshots against modified files and writes `working/proposed_diff.txt`.

---

### 7. `codepilot/skills/`
#### 🔹 C# Equivalent: The Strategy Pattern / Workflow Definition

In C#, you would define an `ISkill` interface:
```csharp
public interface ISkill
{
    string Name { get; }
    TaskType Type { get; }
    IReadOnlyList<string> WorkflowSteps { get; }
    IReadOnlyList<string> Checklist { get; }
    IReadOnlyList<string> ForbiddenActions { get; }
    string GetSystemPromptExtension();
}
```

In [`codepilot/skills/loader.py`](file:///c:/AI%20Engineering%20Course/Projects/Capstone%20Project/codepilot/skills/loader.py), we register:
- **`bug_fix_skill`**: `reproduce → localize → fix → verify`
- **`feature_addition_skill`**: `explore_pattern → design → implement → test → document`
- **`dependency_update_skill`**: `check_changelog → update → resolve_conflicts → test_all`
- **`documentation_skill`**: `read_existing → draft → review_accuracy → update_index`

When the Orchestrator triages an issue, it resolves the appropriate skill and injects it into the Coder Agent's system prompt.

---

### 8. `codepilot/memory/`
#### 🔹 C# Equivalent: Three-Tier Storage (Scoped State + JSON File Store + Vector Store)

CodePilot implements 3 tiers of memory:

```
┌────────────────────────────────────────────────────────┐
│ 1. Working Memory (codepilot/memory/working.py)        │
│    C# Equivalent: Scoped Service (DI / HttpContext)    │
│    Holds current task state in memory; cleared on end. │
├────────────────────────────────────────────────────────┤
│ 2. Episodic Memory (codepilot/memory/episodic.py)      │
│    C# Equivalent: File-based JSON Repository           │
│    Saves session summaries to disk; looks back at      │
│    the last 3 sessions to skip recently failed issues. │
├────────────────────────────────────────────────────────┤
│ 3. Semantic Memory (codepilot/memory/semantic.py)      │
│    C# Equivalent: Microsoft Semantic Kernel VectorStore│
│    ChromaDB stores embeddings of past merged PRs       │
│    and performs cosine similarity retrieval.           │
└────────────────────────────────────────────────────────┘
```

---

### 9. `codepilot/agents/` (The Multi-Agent Hierarchy)
#### 🔹 C# Equivalent: Semantic Kernel Multi-Agent / AutoGen / Saga Pattern

In .NET, orchestrating multiple AI agents uses Microsoft Semantic Kernel or AutoGen:
- **`OrchestratorAgent`**: The Saga / Workflow Coordinator. It receives the issue, classifies it, initiates the state machine, and spawns subagents.
- **`RepoExplorerAgent`**: Context engineering agent that queries the Repo Map.
- **`CoderAgent`**: Developer agent that applies edits to the sandbox.
- **`TestAgent`**: QA agent that runs tests and self-heals setup errors.
- **`PRAgent`**: Release engineering agent that handles git branches and GitHub PRs.

---

### 10. `codepilot/tui/app.py`
#### 🔹 C# Equivalent: `Terminal.Gui` / WPF / Avalonia UI

If you have built desktop or terminal UIs in C# using **Terminal.Gui** or **WPF**:
- `Screen` &rarr; `Window` / `UserControl` with a $2 \times 2$ Grid layout.
- `Static` &rarr; `Label` / `TextBlock`.
- `RichLog` &rarr; `RichTextBox` (formatted terminal log stream).
- `ModalScreen` &rarr; `Window.ShowDialog()`.
- **`self.call_from_thread(callback)`**: Exactly equivalent to **`Dispatcher.InvokeAsync(callback)`** in WPF or `Application.MainLoop.Invoke()` in Terminal.Gui! Because the AI agents run in background worker threads, any UI updates must be marshaled back to the UI thread.

---

## 🚀 Side-by-Side Code Comparison

Here are side-by-side examples illustrating how familiar C# patterns map directly to our Python implementation:

### Example 1: Human-in-the-Loop Barrier

#### 🔷 C# (.NET 8):
```csharp
public class HitlGate
{
    private readonly ManualResetEventSlim _event = new(false);
    private bool _approved = false;

    public bool WaitForHumanApproval(string operation, string reason)
    {
        Console.WriteLine($"[HITL] Paused for: {operation} - {reason}");
        _event.Wait(); // Halts thread until Set() is called
        return _approved;
    }

    public void OnUserDecision(bool approved)
    {
        _approved = approved;
        _event.Set(); // Resumes waiting thread
    }
}
```

#### 🐍 CodePilot (`codepilot/guardrails/hitl.py`):
```python
class HITLController:
    def __init__(self):
        self._events: Dict[str, threading.Event] = {}
        self._decisions: Dict[str, str] = {}

    def request_approval(self, task_id: str, operation: str, reason: str) -> bool:
        event = threading.Event()
        self._events[req_id] = event
        event_bus.emit(EventType.HITL_PROMPT, {...})
        event.wait() # Halts thread until set() is called
        return self._decisions.get(req_id) == "approve"

    def resolve(self, request_id: str, decision: str) -> None:
        self._decisions[request_id] = decision
        self._events[request_id].set() # Resumes waiting thread
```

---

### Example 2: Thread-Safe Event Bus

#### 🔷 C# (.NET 8):
```csharp
public class EventBus
{
    private readonly Dictionary<string, List<Action<object>>> _handlers = new();
    private readonly object _syncRoot = new();

    public void Subscribe(string eventType, Action<object> handler)
    {
        lock (_syncRoot)
        {
            if (!_handlers.ContainsKey(eventType))
                _handlers[eventType] = new();
            _handlers[eventType].Add(handler);
        }
    }

    public void Emit(string eventType, object data)
    {
        List<Action<object>> snapshot;
        lock (_syncRoot)
        {
            if (!_handlers.TryGetValue(eventType, out var list)) return;
            snapshot = list.ToList();
        }
        foreach (var action in snapshot) action(data);
    }
}
```

#### 🐍 CodePilot (`codepilot/tui/event_bus.py`):
```python
class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, callback: Callable) -> None:
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)

    def emit(self, event_type: str, data: Dict[str, Any]) -> None:
        with self._lock:
            callbacks = list(self._subscribers.get(event_type, []))
        for callback in callbacks:
            callback(data)
```

---

### Example 3: Marshaling Background Events to the UI

#### 🔷 C# (WPF / Avalonia):
```csharp
// Inside background agent task
eventBus.Subscribe("agent_log", data => 
{
    // Marshal to UI thread
    Application.Current.Dispatcher.InvokeAsync(() => 
    {
        logTextBox.AppendText($"[{data.Agent}] {data.Message}\n");
    });
});
```

#### 🐍 CodePilot (`codepilot/tui/app.py`):
```python
# Inside Textual App
event_bus.subscribe(EventType.AGENT_LOG, self._on_agent_log)

def _on_agent_log(self, data: dict) -> None:
    # Marshal to UI thread
    self.call_from_thread(
        self.query_one("#panel_logs", AgentLogsPanel).write_log,
        data.get("agent"),
        data.get("message")
    )
```

---

## 🎯 Summary

As a seasoned C# developer, you can think of CodePilot as:
1. **A Semantic Kernel / AutoGen orchestrator** managing 5 specialized agents.
2. **A Roslyn-based static analyzer** that extracts signatures into a 4000-token compressed map.
3. **An isolated Process sandbox** enforcing declarative permissions and unified diffing.
4. **A Terminal.Gui / WPF application** powered by a MediatR-style in-memory event bus and `ManualResetEvent` approval gates.
5. **A 3-tier memory store** combining in-memory state, disk-based session JSONs, and ChromaDB vector embeddings.

For the full architectural and feature documentation, see:
* [**`IMPLEMENTATION_DETAILS.md`**](file:///c:/AI%20Engineering%20Course/Projects/Capstone%20Project/IMPLEMENTATION_DETAILS.md): In-depth state machines and algorithms.
* [**`PROJECT_STRUCTURE.md`**](file:///c:/AI%20Engineering%20Course/Projects/Capstone%20Project/PROJECT_STRUCTURE.md): Detailed module breakdown.
* [**`PROJECT_FEATURES.md`**](file:///c:/AI%20Engineering%20Course/Projects/Capstone%20Project/PROJECT_FEATURES.md): Feature showcase and bonus challenges.
