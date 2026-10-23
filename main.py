"""CHEATER.exe — The One-Click Agent. Entry point."""
import sys

REQUIRED = ["customtkinter", "PIL", "pyautogui", "pyperclip", "pydantic", "dotenv", "google.genai"]


def _missing_dependencies() -> list[str]:
    import importlib.util
    missing = []
    for name in REQUIRED:
        try:
            if importlib.util.find_spec(name) is None:
                missing.append(name)
        except ModuleNotFoundError:
            missing.append(name)
    return missing


def main() -> int:
    if sys.version_info < (3, 11):
        print("CHEATER.exe needs Python 3.11 or newer.")
        return 1
    missing = _missing_dependencies()
    if missing:
        message = (f"Missing dependencies: {', '.join(missing)}\n\n"
                   "Install them with:\n    pip install -r requirements.txt")
        print(message)
        try:
            import tkinter.messagebox as mb
            mb.showerror("CHEATER.exe — setup needed", message)
        except Exception:
            pass
        return 1

    from app.config import load_config
    from app.ui import CheaterApp

    app = CheaterApp(load_config())
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
