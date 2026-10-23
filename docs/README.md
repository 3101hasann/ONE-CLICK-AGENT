# CHEATER.exe — Design Documentation

Every diagram is written in [Mermaid](https://mermaid.js.org), so GitHub renders it inline, and every name matches the real code in `app/`. Pre-rendered SVGs live in [`docs/images/`](images/) for slides.

| # | Document | Diagrams |
|---|---|---|
| 1 | [Agent Orchestrator](01-orchestrator.md) | Orchestration pipeline, thread & event model, guard chain |
| 2 | [Data Flow Diagrams](02-data-flow.md) | DFD level 0 (context), DFD level 1, DFD level 2 (Analyze) |
| 3 | [Use Cases](03-use-cases.md) | UML use case diagram + use case table |
| 4 | [System Sequence Diagrams (SSD)](04-system-sequence-diagrams.md) | Capture Once, Continuous monitoring, Form fill, Feedback on pasted text |
| 5 | [Sequence Diagrams (SD)](05-sequence-diagrams.md) | Capture Once, Monitor loop, Form fill, Rate-limit handling, Stop with stale result |
| 6 | [Class Diagram](06-class-diagram.md) | UML class diagram (all modules) + response-model detail |
| 7 | [State Machine](07-state-diagram.md) | `AgentState` UML state diagram + transition table |
| 8 | [Activity Diagrams](08-activity-diagrams.md) | Continuous monitoring, Form-fill safety, Error handling |
| 9 | [Component & Deployment](09-component-deployment.md) | UML component diagram, UML deployment diagram, package dependencies |

## Architecture in one paragraph

`CheaterApp` (UI, Tk main thread) turns clicks into commands on the **`AgentController`**, the orchestrator. The controller runs every task on background threads. It captures the screen through `ScreenshotService`, uses `ScreenChangeDetector` to decide whether anything meaningful changed, builds a mode-specific request through `ModeSpec`, and sends it through `GeminiService`. Before any request, the quota guard checks for an active 429 block and the session budget. The raw reply is validated with Pydantic (`parse_model_output`), and the form mode adds deterministic safety rules. The controller then publishes an `AgentEvent` on a thread-safe queue. The UI drains that queue on its own thread to render results. The only desktop actions, done through `AutomationService`, are copy, paste-into-focused-field and Tab, and each one happens only after the user confirms.
