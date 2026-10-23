# 2. Data Flow Diagrams (DFD)

The notation follows Gane–Sarson / Yourdon conventions, drawn in Mermaid:

- **Rectangles**: external entities
- **Rounded boxes**: processes, numbered
- **Cylinders**: data stores
- **Arrows**: data flows, labelled with the data that moves

## 2.1 Level 0 — Context diagram

The whole system is one process. Screenshots leave the machine **only** in the flow to the Gemini API.

```mermaid
flowchart LR
    USER["👤 User"]
    SCREEN["🖥 Screen / OS<br/>(pixels, active window)"]
    GEMINI["☁ Google Gemini API"]
    TARGET["📝 Target application<br/>(focused form field)"]
    CLIP["📋 Clipboard"]

    SYS(("0<br/>CHEATER.exe<br/>One-Click Agent"))

    USER -->|"mode, commands, details / pasted text,<br/>region, approvals, edited values"| SYS
    SYS -->|"results, errors, activity log, previews"| USER
    SCREEN -->|"screenshot pixels, window title"| SYS
    SYS -->|"PNG image + prompt + JSON schema"| GEMINI
    GEMINI -->|"structured JSON / error (429, 5xx…)"| SYS
    SYS -->|"approved values (paste) + Tab keys"| TARGET
    SYS -->|"copied answer / values / rewrite"| CLIP
```

## 2.2 Level 1 — Main processes

```mermaid
flowchart TB
    USER["👤 User"]
    SCREEN["🖥 Screen / OS"]
    GEMINI["☁ Gemini API"]
    TARGET["📝 Target app"]
    CLIP["📋 Clipboard"]

    P1("1.0<br/>Configure<br/>(config.py, Settings)")
    P2("2.0<br/>Capture screen<br/>(ScreenshotService)")
    P3("3.0<br/>Detect change<br/>(ScreenChangeDetector)")
    P4("4.0<br/>Analyze with AI<br/>(ModeSpec + GeminiService)")
    P5("5.0<br/>Validate & secure<br/>(Pydantic + safety rules)")
    P6("6.0<br/>Present & review<br/>(CheaterApp UI)")
    P7("7.0<br/>Act<br/>(AutomationService)")
    P8("8.0<br/>Log activity<br/>(ActivityLogger)")

    D1[(".env<br/>API key, model")]
    D2[("settings.json<br/>agent tuning")]
    D3[("Last payload (RAM)<br/>image bytes, context")]
    D4[("Processed signature (RAM)<br/>96×64 grid hash")]
    D5[("logs/cheater.log<br/>redacted events")]

    USER -->|"settings edits"| P1
    D1 -->|"key, model, thinking level"| P1
    P1 <-->|"AgentSettings"| D2
    P1 -->|"config"| P4

    USER -->|"region"| P2
    SCREEN -->|"pixels"| P2
    P2 -->|"masked image"| P3
    P3 <-->|"signature"| D4
    P3 -->|"changed image"| P4
    P2 -->|"image (Capture Once)"| P4

    USER -->|"details / pasted text / study-only"| P4
    P4 -->|"image + prompt + schema"| GEMINI
    GEMINI -->|"raw JSON"| P4
    P4 <-->|"payload for Retry"| D3
    P4 -->|"raw JSON"| P5
    P5 -->|"validated result"| P6
    P5 -->|"validation error"| P6

    P6 -->|"result view"| USER
    USER -->|"approve, edit, confirm"| P6
    P6 -->|"FillStep list"| P7
    P7 -->|"paste + Tab"| TARGET
    P7 -->|"text"| CLIP
    P7 -->|"FillOutcome list"| P6

    P2 -.->|"events"| P8
    P4 -.->|"events"| P8
    P5 -.->|"events"| P8
    P7 -.->|"events"| P8
    P8 -->|"redacted lines"| D5
    P8 -->|"log view"| USER
```

**Privacy properties visible in this DFD**
- D3 and D4 exist **only in memory**. No screenshot is ever written to disk. *Clear Results* drops D3.
- D5 receives only redacted event text: no images, form values, API keys or e-mail addresses.
- D1 (`.env`) is read once and is git-ignored.

## 2.3 Level 2 — Process 4.0 "Analyze with AI" (with 5.0)

```mermaid
flowchart LR
    IN["image PNG / pasted text<br/>+ ModeContext"]
    P41("4.1<br/>Build request<br/>ModeSpec.build_request()")
    P42("4.2<br/>Quota guard<br/>ensure_can_send()")
    P43("4.3<br/>Call Gemini<br/>_generate()")
    P44("4.4<br/>Classify errors<br/>classify_exception()")
    P51("5.1<br/>Parse JSON<br/>strip fences")
    P52("5.2<br/>Validate schema<br/>Pydantic model")
    P53("5.3<br/>Safety rules<br/>(form mode)")
    P54("5.4<br/>Stale check<br/>generation")
    OUT["AgentEvent 'result'"]
    ERR["AgentEvent 'error'"]
    D6[("_blocked_until<br/>request_count")]
    GEM["☁ Gemini API"]

    IN --> P41 -->|"AnalysisRequest"| P42
    D6 -->|"block / budget"| P42
    P42 -->|"allowed"| P43
    P42 -->|"refused"| ERR
    P43 -->|"contents + config"| GEM
    GEM -->|"response.text"| P43
    P43 -->|"exception"| P44
    P44 -->|"AgentError"| ERR
    P44 -->|"429 retry_after"| D6
    P43 -->|"count++"| D6
    P43 -->|"raw text"| P51 -->|"dict"| P52 -->|"model"| P53 -->|"safe result"| P54
    P51 -->|"bad JSON"| ERR
    P52 -->|"ValidationError"| ERR
    P54 -->|"current"| OUT
    P54 -->|"stale → discarded"| X(["dropped"])
```
