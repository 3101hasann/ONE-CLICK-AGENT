# 4. System Sequence Diagrams (SSD)

An SSD treats **CHEATER.exe as a black box**. It shows only the system events that actors send and the responses they get back. The internals are in [Sequence Diagrams](05-sequence-diagrams.md).

## 4.1 SSD — Solve a practice question (Capture Once)

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant S as CHEATER.exe
    participant G as Gemini API

    U->>S: selectMode(practice)
    S-->>U: practice view, status READY
    opt optional
        U->>S: selectRegion(rect)
        S-->>U: capture area set
        U->>S: setContext(text, studyOnly)
    end
    U->>S: captureOnce()
    S-->>U: status PROCESSING, log "Screenshot captured"
    S->>G: generateContent(image, prompt, schema)
    G-->>S: JSON result
    alt valid response
        S-->>U: question, options, suggested answer, explanation, confidence (status REVIEW)
        U->>S: copyResult()
        S-->>U: "Copied result to clipboard"
    else error (429 / timeout / malformed)
        S-->>U: error banner with category, hint and Retry (status ERROR)
        U->>S: retry()
        S-->>U: result, or "no request sent" while quota is blocked
    end
```

## 4.2 SSD — Continuous monitoring

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant S as CHEATER.exe
    participant G as Gemini API

    U->>S: startAgent()
    S-->>U: status RUNNING, "current screen is sent first"
    S->>G: generateContent(first screen)
    G-->>S: JSON
    S-->>U: result
    loop every monitor_interval_s
        alt screen unchanged
            S-->>U: log "No relevant change — not sending"
        else meaningful change, settled, gap elapsed
            S->>G: generateContent(changed screen)
            G-->>S: JSON
            S-->>U: new result
        end
    end
    U->>S: pause()
    S-->>U: status PAUSED
    U->>S: resume()
    S-->>U: status RUNNING
    U->>S: stop()
    S-->>U: status STOPPED, any in-flight result discarded
```

## 4.3 SSD — Fill a form

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant S as CHEATER.exe
    participant G as Gemini API
    participant T as Target app

    U->>S: selectMode(form)
    U->>S: enterDetails(name, email, ...)
    U->>S: captureOnce()
    S->>G: generateContent(form image, details)
    G-->>S: fields JSON
    S-->>U: field rows (value, source, confidence), missing info, sensitive fields locked
    U->>S: editValue(field, value)
    U->>S: tick(field)
    U->>S: fillTickedFields()
    S-->>U: confirmation dialog listing the plan
    U->>S: confirm()
    S-->>U: countdown 3, 2, 1 ("click into the first field")
    U->>T: click first ticked field
    S->>T: paste value, Tab, paste value ...
    S-->>U: fill report (entered / skipped / failed), form NOT submitted
```

## 4.4 SSD — Feedback on pasted text

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant S as CHEATER.exe
    participant G as Gemini API

    U->>S: selectMode(feedback)
    U->>S: pasteText(paragraph)
    U->>S: analyzePastedText()
    S->>G: generateContent(text, prompt, schema)
    G-->>S: JSON feedback
    S-->>U: overall assessment, strengths, improvements, original vs improved, notes
    U->>S: copy(improved version)
    S-->>U: "Copied improved version to clipboard"
```
