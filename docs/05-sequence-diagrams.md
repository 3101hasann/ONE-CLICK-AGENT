# 5. Sequence Diagrams (SD)

These are object-level interactions. The names are the real classes and methods in `app/`. Messages crossing from a worker thread to the UI always go through the `events` queue.

## 5.1 SD — Capture Once (practice mode)

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant UI as CheaterApp (Tk thread)
    participant AC as AgentController
    participant W as one-shot thread
    participant SS as ScreenshotService
    participant MS as ModeSpec (practice)
    participant GS as GeminiService
    participant API as Gemini API
    participant RM as parse_model_output
    participant Q as events Queue

    U->>UI: click "Capture Once"
    UI->>UI: _sync_context()
    UI->>AC: capture_once()
    AC->>AC: checks (not monitoring, not busy)
    AC->>Q: state PROCESSING
    AC->>W: start _one_shot(generation)
    W->>SS: capture()
    SS->>SS: clip region, screenshot, mask own window, validate_image
    SS-->>W: Capture(image, region, warnings)
    W->>Q: capture(image)
    W->>W: prepare_for_upload(image) to PNG bytes
    W->>AC: _run_analysis(generation, payload)
    AC->>AC: _request_lock.acquire(non-blocking)
    AC->>GS: ensure_can_send()
    AC->>Q: task(task_id)
    AC->>MS: build_request(ctx, image_png)
    MS-->>AC: AnalysisRequest(system, user prompt, PracticeResult schema)
    AC->>GS: analyze(request, should_continue)
    GS->>API: models.generate_content(model, parts, config)
    API-->>GS: response.text (JSON)
    GS-->>AC: raw JSON
    AC->>Q: counter(request_count)
    AC->>MS: parse(raw)
    MS->>RM: parse_model_output(PracticeResult, raw)
    RM-->>MS: PracticeResult
    MS-->>AC: result
    AC->>AC: generation == current
    AC->>Q: result(PracticeResult)
    AC->>AC: release lock
    W->>AC: _finish_one_shot()
    AC->>Q: state WAITING_FOR_REVIEW
    loop every 80 ms
        UI->>Q: get_nowait()
    end
    Q-->>UI: state, task, result events
    UI->>UI: _render_practice(result)
    UI-->>U: suggested answer, explanation, confidence
```

## 5.2 SD — Continuous monitoring loop

```mermaid
sequenceDiagram
    autonumber
    participant UI as CheaterApp
    participant AC as AgentController
    participant M as monitor-N thread
    participant SS as ScreenshotService
    participant CD as ScreenChangeDetector
    participant GS as GeminiService
    participant Q as events Queue

    UI->>AC: start()
    AC->>AC: generation += 1, new _Run(stop, resume)
    AC->>Q: state RUNNING
    AC->>M: start _monitor_loop(run)
    loop until run.stop is set
        M->>M: run.resume.wait()
        M->>SS: capture()
        SS-->>M: Capture
        M->>CD: check(image)
        alt UNCHANGED
            CD-->>M: UNCHANGED (diff below threshold)
            M->>Q: log "No relevant change"
        else SETTLING
            CD-->>M: SETTLING (debounce)
        else CHANGED
            CD-->>M: CHANGED, signature
            M->>AC: _process_change(run, capture, signature)
            alt busy or request gap not elapsed
                AC->>Q: log "waiting ... to protect your quota"
            else allowed
                AC->>Q: state PROCESSING
                AC->>GS: analyze via _run_analysis()
                GS-->>AC: result or AgentError
                AC->>CD: mark_processed(signature)
                alt RATE_LIMIT / BUDGET / AUTH / CONFIG error
                    AC->>Q: state PAUSED
                else form mode result
                    AC->>Q: state WAITING_FOR_REVIEW
                else otherwise
                    AC->>Q: state RUNNING
                end
            end
        end
        M->>M: run.stop.wait(monitor_interval_s)
    end
```

## 5.3 SD — Reviewed form fill

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant UI as CheaterApp
    participant FM as form_mode
    participant AS as AutomationService
    participant F as fill thread
    participant OS as pyautogui / pyperclip
    participant T as Target app

    Note over UI: rows rendered with default_approval(field)
    U->>UI: edit values, tick rows
    U->>UI: click "Fill ticked fields"
    UI->>FM: plan_sequential_fill(fields, approved, values)
    FM-->>UI: FillStep list (+ note: stopped before select/radio)
    UI->>U: askokcancel(plan)
    U-->>UI: OK
    loop countdown 3 s
        UI->>UI: after(1000)
    end
    U->>T: click first ticked field
    UI->>F: start run_fill(steps)
    F->>AS: run_fill(steps, progress)
    AS->>OS: save clipboard
    AS->>OS: getActiveWindowTitle()
    alt focus is CHEATER.exe itself
        AS-->>F: abort ("nothing was typed")
    else target focused
        loop each FillStep
            AS->>AS: _check_target(cancel flag, same window)
            alt step.fill
                AS->>OS: pyperclip.copy(value), hotkey ctrl+v
                OS->>T: paste value
            end
            AS->>OS: press tab
        end
    end
    AS->>OS: restore clipboard
    AS-->>F: FillOutcome list
    F->>UI: event fill_done (via queue)
    UI-->>U: fill report, "nothing was submitted"
```

## 5.4 SD — Rate-limit (429) handling and quota block

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant UI as CheaterApp
    participant AC as AgentController
    participant GS as GeminiService
    participant EH as classify_exception
    participant API as Gemini API

    AC->>GS: analyze(request)
    GS->>GS: ensure_can_send() passes
    GS->>API: generate_content()
    API-->>GS: 429 RESOURCE_EXHAUSTED, retry in 68377s
    GS->>EH: classify_exception(exc)
    EH-->>GS: AgentError(RATE_LIMIT, "daily quota used up (resets in ~19.0 h)")
    GS->>GS: _blocked_until = now + 68377 s
    GS-->>AC: raise AgentError
    AC->>UI: error event (banner), state PAUSED / ERROR
    U->>UI: click Retry
    UI->>AC: retry()
    AC->>GS: ensure_can_send()
    GS-->>AC: AgentError "no request sent (try again in ~19.0 h)"
    Note over GS,API: No HTTP request is made while blocked
    AC->>UI: error event
```

## 5.5 SD — Stop while a request is in flight (stale result)

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant UI as CheaterApp
    participant AC as AgentController
    participant W as worker thread
    participant GS as GeminiService

    W->>GS: analyze(request) (generation = 7)
    U->>UI: click Stop
    UI->>AC: stop()
    AC->>AC: run.stop.set(), generation = 8
    AC->>UI: state STOPPED, log "result will be discarded"
    GS-->>W: result arrives
    W->>AC: generation 7 != 8
    AC->>UI: log "Discarded stale result"
    Note over AC: no result event, so the UI never shows an obsolete answer
```
