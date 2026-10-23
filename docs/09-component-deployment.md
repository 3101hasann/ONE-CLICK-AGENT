# 9. Component & Deployment Diagrams

## 9.1 UML component diagram

The components are the Python modules. Interfaces are shown as the main calls between them. Arrows point from the consumer to the provider.

```mermaid
flowchart TB
    subgraph PRES["«layer» Presentation"]
        MAIN["main.py<br/>«entry point»<br/>dependency check"]
        UI["ui.py<br/>«component» CheaterApp,<br/>RegionSelector, SettingsDialog"]
        THEME["theme.py<br/>«design tokens»"]
    end

    subgraph ENGINE["«layer» Agent engine"]
        CTRL["agent_controller.py<br/>«orchestrator» AgentController"]
        DET["screen_change_detector.py<br/>«component»"]
        SHOT["screenshot_service.py<br/>«component»"]
        AUTO["automation_service.py<br/>«component» allow-listed actions"]
    end

    subgraph DOMAIN["«layer» Modes & domain"]
        MODES["modes.py<br/>«registry» MODES"]
        PM["practice_mode.py"]
        FM["form_mode.py<br/>«safety rules»"]
        FBM["feedback_mode.py"]
        RESP["response_models.py<br/>«Pydantic schemas»"]
    end

    subgraph INFRA["«layer» Infrastructure"]
        GEM["gemini_service.py<br/>«gateway» GeminiService / Mock"]
        CFG["config.py<br/>AppConfig, AgentSettings"]
        ERR["error_handler.py<br/>AgentError, classify_exception"]
        LOG["activity_logger.py<br/>ActivityLogger (redaction)"]
    end

    subgraph EXT["«external libraries»"]
        CTK[["customtkinter / tkinter"]]
        GENAI[["google-genai SDK"]]
        PAG[["pyautogui + Pillow"]]
        PYP[["pyperclip"]]
        PYD[["pydantic"]]
        DOT[["python-dotenv"]]
    end

    MAIN --> UI
    MAIN --> CFG
    UI --> THEME
    UI -->|"commands"| CTRL
    UI -->|"FillStep list"| AUTO
    UI --> MODES
    UI --> FM
    UI --> PM
    UI --> CTK
    CTRL -->|"capture()"| SHOT
    CTRL -->|"check()"| DET
    CTRL -->|"analyze()"| GEM
    CTRL -->|"build_request() / parse()"| MODES
    CTRL --> LOG
    CTRL --> ERR
    MODES --> PM
    MODES --> FM
    MODES --> FBM
    MODES --> RESP
    FM --> RESP
    RESP --> PYD
    RESP --> ERR
    GEM --> GENAI
    GEM --> CFG
    GEM --> ERR
    SHOT --> PAG
    DET --> PAG
    AUTO --> PAG
    AUTO --> PYP
    AUTO --> FM
    CFG --> DOT
```

## 9.2 UML deployment diagram

```mermaid
flowchart LR
    subgraph PC["«device» User's Windows 10/11 PC"]
        subgraph PROC["«execution environment» CHEATER.exe process<br/>(PyInstaller one-file, or .venv python)"]
            APP["«artifact» CHEATER.exe / main.py"]
            T1["Tk main thread"]
            T2["monitor / one-shot / fill threads"]
        end
        subgraph FILES["«file system» app folder"]
            ENV[(".env<br/>GEMINI_API_KEY, model")]
            SET[("settings.json")]
            LOGF[("logs/cheater.log")]
        end
        OSN["«OS» Windows desktop<br/>screen capture · keyboard · clipboard"]
        TGT["«application» Browser / target app"]
    end

    subgraph GOOGLE["«cloud» Google AI"]
        API["«service» Gemini API<br/>generativelanguage.googleapis.com<br/>model: gemini-3.8-flash (configurable)"]
    end

    APP --- T1
    APP --- T2
    APP -->|"reads"| ENV
    APP <-->|"reads / writes"| SET
    APP -->|"appends (redacted)"| LOGF
    T2 <-->|"screenshot · paste · Tab"| OSN
    OSN <--> TGT
    T2 -->|"HTTPS (TLS) · PNG + prompt"| API
    API -->|"JSON"| T2
```

### Deployment options

| Option | Artifact | Python on target? | Config location |
|---|---|---|---|
| Launcher | `run.bat` → `.venv\Scripts\pythonw.exe main.py` | Yes (auto-creates venv) | Project folder |
| Standalone | `dist\CHEATER.exe` built by `build_exe.bat` (PyInstaller `--onefile --windowed`) | No | Folder next to the exe |

## 9.3 Package dependency rules

- `ui.py` is the only module that imports `customtkinter`.
- `agent_controller.py` never imports `ui.py`. It talks to the UI only through `AgentEvent`s.
- `gemini_service.py` is the only module that talks to the network.
- `automation_service.py` is the only module that sends keystrokes or touches the clipboard.
- There are no circular imports. The dependency direction is Presentation → Engine → Domain → Infrastructure.
