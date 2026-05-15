# **Technische Spezifikation: Claude Code Orchestrator (Build Blueprint)**

**Ziel:** Implementierung eines wiederverwendbaren, robusten und deterministischen Python-Wrappers (orchestrator.py) für das "Claude Code" CLI.

**Paradigma:** Headless-Ausführung, Defensive Programming, absolute OS- und Git-Sicherheit, Persistenz in Git.

**Arbeitsanweisung für den Coding-Agenten:** Implementiere das System streng sequenziell nach den untenstehenden Phasen. Nutze ausschließlich die Python-Standardbibliothek.

## **Phase 0: Projekt-Setup & Git-Persistenz**

Lege die Grundstruktur an, damit das Projekt versioniert und geteilt werden kann.

### **1\. README.md erstellen**

Erstelle die README.md basierend auf der bereitgestellten Vorlage (siehe separates Dokument), um den Zweck und die Nutzung des Orchestrators zu dokumentieren.

### **2\. .gitignore erstellen**

Verhindere, dass temporäre Dateien und States ins Repo gepusht werden. Füge folgendes hinzu:

.agent\_state.json\*  
out.log  
err.log  
\_\_pycache\_\_/  
\*.pyc  
.venv/  
venv/

### **3\. Git initialisieren**

Führe git init aus und erstelle einen initialen Commit mit README.md und .gitignore.

## **Phase 1: Globale Konstanten & Setup (orchestrator.py)**

Inkludiere folgende Imports und Konstanten am Anfang der Datei:

* Imports: subprocess, json, os, sys, tempfile, re  
* Konstanten:  
  * STATE\_FILE \= ".agent\_state.json"  
  * CONVENTIONS\_FILE \= "CONVENTIONS.md"  
  * HISTORY\_FILE \= "FORTSCHRITT.md"  
  * REQUIREMENTS\_FILE \= "NEUES\_PROJEKT.md"

## **Phase 2: Core Utilities (I/O & Sicherheit)**

### **1\. atomic\_write\_json(filepath: str, data: dict)**

Sicheres Schreiben des States zur Verhinderung von 0-Byte-Dateien bei Abstürzen.

* Nutze tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(filepath)), prefix=".", suffix=".tmp").  
* Öffne den Deskriptor (os.fdopen), schreibe das JSON.  
* **Zwingend:** Führe f.flush() und os.fsync(f.fileno()) aus.  
* Tausche sie atomar via os.replace(tmp\_filename, filepath) aus. Bei Fehler: Temp-Datei löschen und Exception werfen.

### **2\. clean\_json(raw\_string: str) \-\> str**

Bereinigt LLM-Ausgaben von Markdown (\`\`\`json).

* Extrahiere Text zwischen Backticks mittels Regex (re.search(..., re.DOTALL)). Fallback: raw\_string.strip().

## **Phase 3: Git & Workspace Guards**

### **3\. ensure\_sterile\_workspace()**

Gatekeeper vor dem Start.

* Führe aus: git status \--porcelain.  
* Wenn stdout nicht leer ist: Warnung ausgeben ("Bitte committen/stashen") und sys.exit(1).

### **4\. rollback\_workspace()**

Tabula-Rasa nach Halluzinationen.

* Führe aus: git reset \--hard HEAD und git clean \-fd.

### **5\. get\_efficient\_diff() \-\> str**

Diffing-Logik für den Reviewer.

* Führe zwingend git add \-N . aus.  
* Führe git diff \-M \-U10 aus und gib das Ergebnis zurück.

## **Phase 4: Die Subprozess-Engine**

### **6\. run\_claude(prompt, allowed\_tools=None, requires\_json=True, skip\_permissions=False, max\_retries=2, timeout=120) \-\> dict | str | None**

Der abgesicherte Aufruf des CLI-Tools.

**A. Befehlsaufbau:**

* Basis: \["claude", "-p", prompt\]  
* Appends: \--allowedTools, \--dangerously-skip-permissions, \--append-system-prompt-file CONVENTIONS\_FILE, \--output-format json.

**B. Env-Quarantäne:**

* Setze im env: NO\_COLOR=1, TERM=dumb, CI=1, NONINTERACTIVE=1.

**C. File I/O & Execution:**

* Schleife (0 bis max\_retries).  
* Nutze tempfile.TemporaryFile für stdout und stderr.  
* subprocess.run(..., stdout=f\_out, stderr=f\_err, timeout=timeout, env=env). Bei Timeout: return None.  
* Auslesen der Tempfiles via seek(0).

**D. Phantom-Exit & Parsing:**

* Wenn returncode \!= 0: Hartes sys.exit(1) mit stderr-Ausgabe.  
* Versuche json.loads(clean\_json(stdout)).  
* Bei JSONDecodeError: Fehler (und ggf. "KÜRZER FASSEN\!") an Prompt anhängen und Retry starten. Ab attempt \>= max\_retries: return None.

## **Phase 5: Die Agenten-Rollen (State-Machine)**

### **7\. get\_recent\_history(max\_lines=15)**

Liest FORTSCHRITT.md, gibt letzte max\_lines zurück.

### **8\. step\_plan()**

* ensure\_sterile\_workspace().  
* Prompt an run\_claude (Tools: Read, Timeout: 60s): "Ermittle nächste atomare Aufgabe. Antworte in JSON {title, description}."  
* Speichere Erfolg in STATE\_FILE via atomic\_write\_json (status="planned", attempts=0, total\_iterations=0).

### **9\. step\_implement()**

* Lade STATE\_FILE.  
* **Circuit Breaker:** Wenn total\_iterations \> 15, sys.exit(1).  
* **Git Rollback Check:** Erhöhe attempts. Wenn attempts \> 3: rollback\_workspace(), attempts \= 1\.  
* Prompt an run\_claude (Tools: Read,Edit,Bash, Skip Perms, Timeout: 400s): Aufgabe \+ Feedback umsetzen.  
* State Update: status="needs\_review", schreibe State atomar.

### **10\. step\_review()**

* Lade STATE\_FILE.  
* **Lint-before-Review:** subprocess.run(\["python", "-m", "py\_compile", "app.py"\]). Bei Fehler \-\> State auf needs\_rework, abort.  
* Lade Diff via get\_efficient\_diff().  
* Prompt an run\_claude (Tools: Read, Timeout: 120s): Diff prüfen. JSON {status: APPROVED/REJECTED, feedback}.  
* Bei APPROVED: In FORTSCHRITT.md anhängen, STATE\_FILE löschen.  
* Bei REJECTED: State auf needs\_rework, Feedback speichern.

## **Phase 6: CLI Entrypoint**

Implementiere if \_\_name\_\_ \== "\_\_main\_\_":

* Erwarte sys.argv\[1\] (plan, implement, review). Führe entsprechende Funktion aus.