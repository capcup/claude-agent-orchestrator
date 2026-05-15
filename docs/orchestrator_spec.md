# **Technical Specification: Claude Code Orchestrator (Build Blueprint)**

**Goal:** Implement a reusable, robust, and deterministic Python wrapper (orchestrator.py) around the "Claude Code" CLI.

**Paradigm:** Headless execution, defensive programming, absolute OS and Git safety, persistence in Git.

**Instructions for the coding agent:** Implement the system strictly sequentially following the phases below. Use the Python standard library exclusively.

## **Phase 0: Project Setup & Git Persistence**

Create the base structure so the project can be versioned and shared.

### **1\. Create README.md**

Create README.md based on the provided template (see separate document) to document the purpose and usage of the orchestrator.

### **2\. Create .gitignore**

Prevent temporary files and state from being pushed to the repo. Add the following:

.agent\_state.json\*  
out.log  
err.log  
\_\_pycache\_\_/  
\*.pyc  
.venv/  
venv/

### **3\. Initialize Git**

Run git init and create an initial commit with README.md and .gitignore.

## **Phase 1: Global Constants & Setup (orchestrator.py)**

Include the following imports and constants at the top of the file:

* Imports: subprocess, json, os, sys, tempfile, re  
* Constants:  
  * STATE\_FILE \= ".agent\_state.json"  
  * CONVENTIONS\_FILE \= "CONVENTIONS.md"  
  * HISTORY\_FILE \= "PROGRESS.md"  
  * REQUIREMENTS\_FILE \= "NEW\_PROJECT.md"

## **Phase 2: Core Utilities (I/O & Safety)**

### **1\. atomic\_write\_json(filepath: str, data: dict)**

Safe state writing to prevent 0-byte files on crashes.

* Use tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(filepath)), prefix=".", suffix=".tmp").  
* Open the descriptor (os.fdopen), write the JSON.  
* **Mandatory:** Run f.flush() and os.fsync(f.fileno()).  
* Swap atomically via os.replace(tmp\_filename, filepath). On error: delete the temp file and raise the exception.

### **2\. clean\_json(raw\_string: str) \-\> str**

Strips Markdown (\`\`\`json) from LLM output.

* Extract the text between backticks using a regex (re.search(..., re.DOTALL)). Fallback: raw\_string.strip().

## **Phase 3: Git & Workspace Guards**

### **3\. ensure\_sterile\_workspace()**

Gatekeeper before the start.

* Run: git status \--porcelain.  
* If stdout is not empty: print a warning ("Please commit/stash") and sys.exit(1).

### **4\. rollback\_workspace()**

Tabula rasa after hallucinations.

* Run: git reset \--hard HEAD and git clean \-fd.

### **5\. get\_efficient\_diff() \-\> str**

Diffing logic for the reviewer.

* Mandatorily run git add \-N . first.  
* Run git diff \-M \-U10 and return the result.

### **6\. get\_changed\_python\_files() \-\> list\[str\]**

Determines which Python files the lint step must compile, instead of hardcoding a single filename.

* Run git status \--porcelain to capture staged, unstaged, and untracked changes.  
* For each line, parse the path (strip the 2-char status \+ space prefix; for renames take the part after " \-\> "; strip surrounding quotes).  
* Keep only paths that end with ".py" **and** still exist on disk (os.path.isfile) — deleted files must be excluded.  
* Return the de-duplicated list (may be empty).

## **Phase 4: The Subprocess Engine**

### **7\. run\_claude(prompt, allowed\_tools=None, requires\_json=True, skip\_permissions=False, max\_retries=2, timeout=120) \-\> dict | str | None**

The hardened invocation of the CLI tool.

**A. Command assembly:**

* Base: \["claude", "-p", prompt\]  
* Appends: \--allowedTools, \--dangerously-skip-permissions, \--append-system-prompt-file CONVENTIONS\_FILE (only if the file exists), \--output-format json.

**B. Env quarantine:**

* Set in env: NO\_COLOR=1, TERM=dumb, CI=1, NONINTERACTIVE=1.

**C. File I/O & execution:**

* Loop (0 to max\_retries).  
* Use tempfile.TemporaryFile for stdout and stderr.  
* subprocess.run(..., stdout=f\_out, stderr=f\_err, timeout=timeout, env=env). On timeout: return None.  
* Read the temp files via seek(0).

**D. Phantom exit & parsing:**

* If returncode \!= 0: hard sys.exit(1) printing stderr.  
* Try json.loads(clean\_json(stdout)).  
* On JSONDecodeError: append the error (and a "BE MORE CONCISE\!" hint) to the prompt and retry. Once attempt \>= max\_retries: return None.

## **Phase 5: The Agent Roles (State Machine)**

### **8\. get\_recent\_history(max\_lines=15)**

Reads PROGRESS.md, returns the last max\_lines.

### **9\. step\_plan()**

* ensure\_sterile\_workspace().  
* Prompt to run\_claude (Tools: Read, Timeout: 60s): read REQUIREMENTS\_FILE \+ recent history, "Determine the next atomic task. Respond in JSON {title, description}."  
* Persist success in STATE\_FILE via atomic\_write\_json (status="planned", attempts=0, total\_iterations=0).

### **10\. step\_implement()**

* Load STATE\_FILE.  
* **Circuit breaker:** If total\_iterations \> 15, sys.exit(1).  
* **Git rollback check:** Increment attempts. If attempts \> 3: rollback\_workspace(), attempts \= 1\.  
* Prompt to run\_claude (Tools: Read,Edit,Bash, Skip Perms, Timeout: 400s): implement the task \+ feedback.  
* State update: status="needs\_review", write the state atomically.

### **11\. step\_review()**

* Load STATE\_FILE.  
* **Lint before review:** Collect the changed Python files via get\_changed\_python\_files(). If the list is non-empty, run subprocess.run(\[sys.executable, "-m", "py\_compile", \*py\_files\]) — use sys.executable rather than a bare "python" so the running interpreter is guaranteed. On a non-zero return code → set state to needs\_rework (with the compiler stderr as feedback), persist, abort. If there are no changed Python files, skip the lint step (it is not a failure) and continue.  
* Load the diff via get\_efficient\_diff().  
* Prompt to run\_claude (Tools: Read, Timeout: 120s): review the diff. JSON {status: APPROVED/REJECTED, feedback}.  
* On APPROVED: append to PROGRESS.md, delete STATE\_FILE.  
* On REJECTED: set state to needs\_rework, store the feedback.

## **Phase 6: CLI Entrypoint**

Implement if \_\_name\_\_ \== "\_\_main\_\_":

* Expect sys.argv\[1\] (plan, implement, review). Run the corresponding function.
