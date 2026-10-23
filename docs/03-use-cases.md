# 3. Use Cases

## 3.1 UML use case diagram

Mermaid has no native use-case syntax, so this follows UML notation: the actors are outside the system boundary, the use cases are ovals (stadium shapes), and `«include»` / `«extend»` are labelled dashed arrows.

```mermaid
flowchart LR
    USER["👤 User<br/>(student / worker)"]
    GEM["☁ Gemini API<br/>«secondary actor»"]
    OS["🖥 Operating system<br/>«secondary actor»"]

    subgraph SYSTEM["CHEATER.exe — system boundary"]
        UC1(["UC1 Select mode"])
        UC2(["UC2 Solve practice question"])
        UC3(["UC3 Fill form from my details"])
        UC4(["UC4 Get writing feedback"])
        UC5(["UC5 Run continuous agent<br/>(Start / Pause / Resume / Stop)"])
        UC6(["UC6 Select capture region"])
        UC7(["UC7 Preview screenshot"])
        UC8(["UC8 Copy result"])
        UC9(["UC9 Retry failed task"])
        UC10(["UC10 Configure settings"])
        UC11(["UC11 Review activity log"])
        INC1(["Capture screen"])
        INC2(["Analyze with Gemini"])
        INC3(["Validate response"])
        EXT1(["Type into focused field"])
        EXT2(["Study-only hints"])
        EXT3(["Analyze pasted text"])
    end

    USER --- UC1
    USER --- UC2
    USER --- UC3
    USER --- UC4
    USER --- UC5
    USER --- UC6
    USER --- UC7
    USER --- UC8
    USER --- UC9
    USER --- UC10
    USER --- UC11

    UC2 -.->|"«include»"| INC1
    UC3 -.->|"«include»"| INC1
    UC4 -.->|"«include»"| INC2
    UC5 -.->|"«include»"| INC1
    UC2 -.->|"«include»"| INC2
    UC3 -.->|"«include»"| INC2
    INC2 -.->|"«include»"| INC3
    EXT1 -.->|"«extend»"| UC2
    EXT1 -.->|"«extend»"| UC3
    EXT2 -.->|"«extend»"| UC2
    EXT3 -.->|"«extend»"| UC4

    INC1 --- OS
    EXT1 --- OS
    INC2 --- GEM
```

## 3.2 Use case summary

| ID | Use case | Primary flow | Key alternate / exception flows |
|---|---|---|---|
| UC2 | Solve practice question | Capture Once → question, options, suggested answer, explanation, confidence | No question found. Study-only shows a hint, no answer. Graded exam suspected disables answer entry. Low confidence shows a warning. |
| UC3 | Fill form from my details | Type details → Capture → review rows (pre-ticked only if confident and user-sourced) → confirm → 3 s countdown → paste + Tab | Sensitive field (password, card, ID) is never filled. Invented personal value is removed. Non-text field stops the sequence. Focus lost or the app focused itself aborts. Stop or mouse in a corner aborts (fail-safe). |
| UC4 | Get writing feedback | Paste text → Analyze, or capture → feedback + improved version → Copy | No readable text: ask for paste or a clearer region |
| UC5 | Run continuous agent | Start → send the current screen → only meaningful changes, at most one request every 20 s | Unchanged screen is not sent. A 429 blocks requests until reset and pauses. Budget reached pauses. Stop discards in-flight results. |
| UC9 | Retry failed task | Re-send the in-memory last payload | Refused locally while a quota block is active or the budget is used up |
| UC10 | Configure settings | Edit interval, sensitivity, settle time, image size, timeout, retries, request gap, budget → saved to `settings.json` | Invalid numbers are rejected. Values are clamped to safe ranges. |
