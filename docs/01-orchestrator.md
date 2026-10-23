# 1. Agent Orchestrator

`AgentController` (`app/agent_controller.py`) is the orchestrator. It owns the agent's state machine, decides **when** work happens, and coordinates every other component. It never touches widgets. Its only output to the UI is `AgentEvent` objects on a queue.

## 1.1 Orchestration pipeline

Each task passes through this pipeline. The guards are filters: a task that fails one of them stops there and **costs no API quota**.

```mermaid
flowchart TB
    subgraph TRIGGER["Triggers"]
        T1["Capture Once"]
        T2["Monitor tick<br/>(every N s)"]
        T3["Analyze Pasted Text"]
        T4["Retry<br/>(last payload)"]
    end

    subgraph PERCEIVE["Perceive"]
        C1["ScreenshotService.capture()<br/>clip region · mask own window"]
        C2["validate_image()<br/>size · not blank"]
    end

    subgraph DECIDE["Decide (continuous only)"]
        D1{"ScreenChangeDetector.check()<br/>UNCHANGED / SETTLING / CHANGED"}
        D2{"busy?<br/>(_request_lock)"}
        D3{"min_request_gap_s<br/>elapsed?"}
    end

    subgraph GUARD["Quota guard"]
        G1{"GeminiService.ensure_can_send()<br/>429 block · session budget"}
    end

    subgraph THINK["Reason"]
        R1["ModeSpec.build_request()<br/>prompt + schema + image"]
        R2["GeminiService.analyze()<br/>google-genai · timeout"]
    end

    subgraph VERIFY["Verify"]
        V1["parse_model_output()<br/>Pydantic validation"]
        V2["mode post-process<br/>form_mode.apply_safety_rules()"]
        V3{"generation still current?<br/>(stale-result check)"}
    end

    subgraph ACT["Act (human-in-the-loop)"]
        A1["AgentEvent 'result' → UI render"]
        A2["User reviews · edits · ticks"]
        A3["AutomationService<br/>copy / paste / Tab only"]
    end

    T1 --> C1
    T2 --> C1
    T3 --> G1
    T4 --> G1
    C1 --> C2
    C2 -->|"once"| G1
    C2 -->|"monitor"| D1
    D1 -->|"CHANGED"| D2
    D1 -->|"UNCHANGED / SETTLING"| X1(["skip — no request"])
    D2 -->|"free"| D3
    D2 -->|"busy"| X1
    D3 -->|"yes"| G1
    D3 -->|"no"| X1
    G1 -->|"allowed"| R1
    G1 -->|"blocked"| X2(["error event — no request sent"])
    R1 --> R2 --> V1 --> V2 --> V3
    V3 -->|"current"| A1
    V3 -->|"stale"| X3(["discard result"])
    A1 --> A2 --> A3
```

## 1.2 Responsibilities of the orchestrator

| Concern | How `AgentController` handles it |
|---|---|
| **Lifecycle** | `start()`, `pause()`, `resume()`, `stop()`, `capture_once()`, `analyze_text()`, `retry()`, `clear()`, `shutdown()` |
| **State** | Explicit `AgentState` machine; `_transition()` rejects invalid moves (see [State Machine](07-state-diagram.md)) |
| **One request at a time** | Non-blocking `_request_lock`. A second request is refused, never queued. |
| **No duplicate workers** | `start()` refuses while `monitoring`. Each run gets its own `_Run` (stop/resume events), so a stopped run can never be revived. |
| **Stale results** | `_generation` is incremented on Stop/Start. A result whose generation no longer matches is discarded. |
| **Quota protection** | `ensure_can_send()` before every request. Continuous mode adds `min_request_gap_s` and change detection. It pauses on `RATE_LIMIT`, `BUDGET`, `AUTH` and `CONFIG` errors. |
| **Review gate** | Form mode (`pause_for_review=True`) moves to `WAITING_FOR_REVIEW` after each result |
| **Recovery** | Errors become `AgentError` (category, message, hint). The last payload is kept in memory so the user can Retry. |

## 1.3 Thread & event model

Background threads **never** touch Tk widgets. Everything crosses to the UI through one `queue.Queue` of `AgentEvent`s, which the UI drains every 80 ms in `_poll_events()`.

```mermaid
flowchart TB
    subgraph MAIN["Tk main thread"]
        UI["CheaterApp<br/>buttons · rendering"]
        POLL["_poll_events()<br/>every 80 ms"]
    end

    subgraph WORKERS["Background threads (daemon)"]
        MON["monitor-N<br/>_monitor_loop(run)"]
        ONE["one-shot<br/>_one_shot()"]
        FILL["fill<br/>AutomationService.run_fill()"]
        VER["verify<br/>GeminiService.verify()"]
    end

    Q[("events: queue.Queue[AgentEvent]")]
    LOG["ActivityLogger<br/>(listener → queue)"]

    UI -->|"commands"| CTRL["AgentController"]
    CTRL -->|"spawns"| MON
    CTRL -->|"spawns"| ONE
    UI -->|"spawns"| FILL
    UI -->|"spawns"| VER
    MON -->|"put"| Q
    ONE -->|"put"| Q
    FILL -->|"put"| Q
    VER -->|"put"| Q
    LOG -->|"put 'log'"| Q
    Q -->|"get_nowait"| POLL
    POLL -->|"render"| UI
```

### Event kinds

| `AgentEvent.kind` | Producer | UI reaction |
|---|---|---|
| `state` | `_transition()` | Status pill, status card, enable/disable controls |
| `task` | `_run_analysis()` | Current task number, hide error banner |
| `result` | `_run_analysis()` | Render the mode's result view (MOCK badge if mock) |
| `error` | `_report_error()` | Error banner with category, message, hint, Retry |
| `capture` | capture paths | Keep the last image for Preview |
| `counter` | `_run_analysis()` | Footer "API requests N / budget" |
| `log` | `ActivityLogger` listener | Append a colored line to the activity log |
| `verify` | startup thread | Footer Gemini connection status |
| `preview` | Preview button thread | Open the screenshot preview window |
| `fill_progress` / `fill_done` | fill thread | Status text / fill report |

## 1.4 Guard chain before any API call

```mermaid
flowchart TD
    S(["Request wanted"]) --> A{"Another request<br/>in flight?"}
    A -->|"yes"| N1(["refused: busy"])
    A -->|"no"| B{"429 block active?<br/>blocked_for > 0"}
    B -->|"yes"| N2(["refused locally<br/>'no request sent'"])
    B -->|"no"| C{"Session budget left?<br/>budget_left > 0"}
    C -->|"no"| N3(["refused locally<br/>BUDGET error → pause"])
    C -->|"yes"| D{"Cancelled?<br/>generation changed"}
    D -->|"yes"| N4(["CANCELLED"])
    D -->|"no"| E["generate_content()<br/>request_count += 1"]
    E -->|"429"| F["set _blocked_until = now + retry_after"]
    E -->|"ok"| G(["raw JSON → validation"])
```
