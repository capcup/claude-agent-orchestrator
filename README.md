# Claude Code Orchestrator

Ein wiederverwendbarer, robuster und deterministischer Python-Wrapper für das "Claude Code" CLI.

## Paradigma

- **Headless-Ausführung:** Kein interaktiver Betrieb – der Orchestrator wird vollständig skriptgesteuert aufgerufen.
- **Defensive Programming:** Jeder Schritt ist gegen Abstürze, Halluzinationen und fehlerhafte LLM-Ausgaben abgesichert.
- **Absolute OS- und Git-Sicherheit:** Workspace-Zustand wird vor jedem Schritt geprüft; atomare Schreiboperationen verhindern korrupte State-Dateien.
- **Persistenz in Git:** Fortschritt und State werden versioniert gespeichert.

## Voraussetzungen

- Python 3.9+
- Claude Code CLI (`claude`) im PATH installiert und authentifiziert
- Git installiert

## Nutzung

```bash
# Nächste atomare Aufgabe planen
python orchestrator.py plan

# Aufgabe implementieren
python orchestrator.py implement

# Implementierung reviewen
python orchestrator.py review
```

## Workflow

Der Orchestrator arbeitet als State-Machine mit drei Schritten:

1. **plan** – Liest Anforderungen (`NEUES_PROJEKT.md`) und Konventionen (`CONVENTIONS.md`), ermittelt die nächste atomare Aufgabe und speichert den State.
2. **implement** – Führt die geplante Aufgabe aus. Beinhaltet Circuit Breaker (max. 15 Iterationen) und automatischen Git-Rollback nach 3 Fehlversuchen.
3. **review** – Prüft den Diff, führt Lint durch und entscheidet APPROVED/REJECTED. Bei Erfolg wird `FORTSCHRITT.md` aktualisiert.

## Konfigurationsdateien

| Datei | Zweck |
|---|---|
| `NEUES_PROJEKT.md` | Anforderungen und Aufgabenbeschreibung für das aktuelle Projekt |
| `CONVENTIONS.md` | Coding-Konventionen, die dem LLM als System-Prompt angehängt werden |
| `FORTSCHRITT.md` | Fortschrittslog – wird automatisch bei jedem APPROVED-Review ergänzt |
| `.agent_state.json` | Temporärer State zwischen den Schritten (nicht eingecheckt) |

## Ausschließlich Python-Standardbibliothek

Keine externen Abhängigkeiten. Benötigt: `subprocess`, `json`, `os`, `sys`, `tempfile`, `re`.
