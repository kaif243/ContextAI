# CONTEXTAI — AI DESKTOP INTELLIGENCE & AUTOMATION PLATFORM

You are the lead software architect, senior AI/ML engineer, agentic AI engineer, backend engineer, frontend engineer, and security engineer for this project.

We are building a serious, production-quality Windows desktop application called:

**ContextAI — An Agentic AI Desktop Intelligence & Automation Platform**

This is intended to become a real usable product as well as a strong AI/ML portfolio project.

Do NOT build this as a simple chatbot or an LLM wrapper.

The project must combine:

* Agentic AI
* Generative AI
* Machine Learning
* NLP
* Computer Vision
* OCR
* Semantic Search
* RAG
* Vector Search
* Tool Calling
* Planning
* Memory
* Desktop Automation
* Human-in-the-loop security
* Evaluation
* Observability
* Privacy

---

# 1. PRODUCT VISION

ContextAI is an intelligent Windows desktop companion that understands the user's computer context and helps them complete everyday tasks.

The system can understand, with explicit user permission:

* Current screen
* Screenshots
* Clipboard
* Files
* Documents
* Applications
* User-approved memory
* Natural-language commands

The system should be able to:

1. Observe context.
2. Understand context.
3. Use ML models to classify/predict information.
4. Use an LLM for reasoning.
5. Create a plan.
6. Select appropriate tools.
7. Ask for user approval when necessary.
8. Execute actions.
9. Verify the result.
10. Recover from failures when possible.
11. Store useful user-approved information in memory.

The fundamental agent loop is:

OBSERVE → UNDERSTAND → PLAN → ASK PERMISSION → ACT → VERIFY → REMEMBER

---

# 2. MAIN USER EXPERIENCE

The primary interaction should be simple.

The user presses a global hotkey such as:

Ctrl + Space

This opens the ContextAI interface.

The user can then say things such as:

"What's wrong with this error?"

"Explain what's on my screen."

"Find the PDF I was working on last week."

"Organize my Downloads folder."

"Find the FastAPI code I copied yesterday."

"Extract the dates from this timetable."

"Find duplicate documents."

"Summarize this document."

The system should determine the user's intent and decide which tools, ML models, retrieval systems, and AI capabilities are required.

---

# 3. CORE FEATURE 1 — SCREEN INTELLIGENCE

ContextAI should be able to capture the user's current screen.

It should support:

* Global hotkey
* Screenshot capture
* OCR
* Vision analysis
* Screen classification
* Text extraction
* Entity extraction
* User questions about the screen

Classify screen content into categories such as:

* Code
* Programming error
* Document
* Receipt
* Timetable
* Table
* Form
* Webpage
* Image
* General UI

Example:

User sees:

ModuleNotFoundError: No module named 'pandas'

User asks:

"What's wrong?"

ContextAI should:

1. Detect that this is a programming error.
2. Extract the error.
3. Determine likely causes.
4. Explain the problem.
5. Suggest possible solutions.
6. If an executable action is appropriate, ask for permission.

---

# 4. CORE FEATURE 2 — SMART SCREENSHOT INTELLIGENCE

Users should be able to save screenshots into ContextAI.

The system should extract:

* Text
* Dates
* Times
* Names
* Amounts
* URLs
* Important entities
* Document type

Example:

A timetable screenshot:

Machine Learning — September 4 — 10:00 AM
NLP — September 7 — 10:00 AM

ContextAI should convert this into structured information.

The user can then say:

"Remember this."

The information is saved into user-controlled memory.

---

# 5. CORE FEATURE 3 — AI CLIPBOARD

Create an intelligent clipboard history.

ContextAI should maintain a searchable history of user-approved clipboard content.

Classify clipboard content into:

* Code
* URL
* Email
* Education
* Notes
* Financial
* Personal
* Other

Example:

User copies:

"FastAPI is a Python web framework..."

Later:

"Find the FastAPI information I copied yesterday."

ContextAI should perform semantic search and retrieve the correct clipboard item.

Features:

* Clipboard history
* Search
* Semantic search
* Classification
* Pin important items
* Delete items
* Clear history
* Privacy mode
* Disable clipboard monitoring

---

# 6. CORE FEATURE 4 — AI FILE INTELLIGENCE

Allow users to explicitly select folders for indexing.

Do NOT scan the entire computer without permission.

The system should analyze:

* Filename
* Extension
* Metadata
* Text content
* Document content
* Creation/modification dates

Classify files into:

* Education
* Career
* Finance
* Programming
* Projects
* Personal
* Images
* Documents
* Other

The system should support:

* File search
* Semantic search
* Duplicate detection
* Semantic similarity
* File classification
* File summarization
* Organization suggestions

---

# 7. CORE FEATURE 5 — AI FILE ORGANIZER

The user should be able to say:

"Clean my Downloads folder."

The agent must NOT immediately modify files.

It should first generate a plan:

PLAN

1. Scan Downloads.
2. Classify files.
3. Detect duplicates.
4. Detect semantically similar files.
5. Identify potential important files.
6. Generate organization proposal.
7. Show proposed changes.
8. Ask for user approval.
9. Execute approved actions.
10. Verify results.

Example:

Downloads:

ML_notes.pdf
invoice.pdf
resume_final.pdf
project.zip
IMG_123.png

Suggested:

Education/
ML_notes.pdf

Finance/
invoice.pdf

Career/
resume_final.pdf

Projects/
project.zip

Images/
IMG_123.png

The user approves before changes happen.

---

# 8. CORE FEATURE 6 — SEMANTIC COMPUTER SEARCH

Users should be able to search their indexed files using natural language.

Example:

"Find the database architecture document I worked on last week."

The search system should combine:

* Keyword search
* Semantic embeddings
* File metadata
* Modification date
* Content similarity
* Context

Results should be ranked.

Example:

Database_Architecture.pdf

Match: 94%

Why:
Contains PostgreSQL, FastAPI, API architecture and database design.

---

# 9. CORE FEATURE 7 — PERSONAL MEMORY

Implement a user-controlled memory system.

Memory may include:

* Important documents
* Projects
* Saved notes
* Frequently used folders
* Saved snippets
* User-approved preferences
* Extracted information
* Tasks
* Important dates

Users must have complete control.

Settings must allow:

* View memory
* Search memory
* Edit memory
* Delete memory
* Clear all memory
* Disable memory

Do not silently save sensitive information.

---

# 10. CORE FEATURE 8 — AGENTIC AI ENGINE

Build a modular agent orchestration system.

The agent should be capable of:

* Intent understanding
* Context gathering
* Planning
* Tool selection
* Multi-step execution
* Approval requests
* Verification
* Error recovery
* Memory updates

Example:

User:

"Find all my ML notes and organize them."

Agent:

1. Understand request.
2. Search indexed files.
3. Use semantic retrieval.
4. Classify relevant files.
5. Check duplicates.
6. Create organization plan.
7. Ask permission.
8. Move approved files.
9. Verify.
10. Report result.

This must be a real agent workflow rather than a fake sequence of LLM-generated messages.

---

# 11. TOOL SYSTEM

Implement tools as modular functions with strict schemas.

FILE TOOLS:

* list_files
* read_file
* move_file
* rename_file
* copy_file
* create_folder
* delete_file

SCREEN TOOLS:

* take_screenshot
* get_active_window

CLIPBOARD TOOLS:

* get_clipboard
* search_clipboard
* save_clipboard

SEARCH TOOLS:

* semantic_search
* keyword_search

BROWSER TOOLS:

* search_web
* open_url
* extract_page

DEVELOPER TOOLS:

* inspect_project
* run_tests
* run_command

Every tool must define:

* Input schema
* Output schema
* Permission level
* Error handling
* Logging behavior

---

# 12. HUMAN-IN-THE-LOOP SECURITY

Use three permission levels.

GREEN — Safe

Can run automatically:

* Read
* Search
* Analyze
* Classify
* Summarize

YELLOW — Confirmation required

* Rename
* Move
* Copy
* Modify documents
* Install packages

RED — Always confirmation required

* Delete files
* Execute arbitrary commands
* Send messages
* Upload files
* Modify system settings

Never bypass these permissions.

The user should be able to see exactly what action is going to happen.

Example:

"ContextAI wants to move:

ML_notes.pdf

from:

Downloads/

to:

Education/ML/

[Approve] [Reject]"

---

# 13. MACHINE LEARNING SYSTEM

The project must contain a genuine ML subsystem.

Do not route every decision through the LLM.

Create modular ML services.

## ML MODEL 1 — FILE CLASSIFICATION

Classify files into categories:

Education
Finance
Career
Programming
Projects
Personal
Other

Start with a practical baseline model.

Possible approaches:

* TF-IDF + Logistic Regression
* Random Forest
* Gradient Boosting
* Transformer embeddings + classifier

Choose the simplest approach that performs well.

---

## ML MODEL 2 — SCREEN CLASSIFICATION

Classify screenshots:

* Code
* Error
* Document
* Receipt
* Table
* Timetable
* Webpage
* Form
* Image
* Other

Use a practical computer vision approach.

Do not over-engineer the first version.

---

## ML MODEL 3 — SEMANTIC SIMILARITY

Detect whether two documents are semantically similar.

Use embeddings and similarity scoring.

Example:

resume.pdf
resume_final.pdf
resume_latest.pdf

The system should determine whether they represent the same underlying document/version.

---

## ML MODEL 4 — IMPORTANCE PREDICTION

Predict:

* Important
* Normal
* Low importance

for clipboard items or other user-approved information.

---

## ML MODEL 5 — ANOMALY DETECTION

Detect unusual patterns such as:

* Large unexpected file operations
* Sudden unusual activity
* Abnormal behavior

This should be advisory and must not silently block legitimate user activity.

---

# 14. ML EVALUATION

Every ML model must have measurable evaluation.

Track:

* Accuracy
* Precision
* Recall
* F1 score
* Confusion matrix
* Dataset size
* Inference time

Where applicable.

Do not fabricate metrics.

Only display metrics calculated from actual evaluation runs.

---

# 15. AI / LLM LAYER

Use an LLM for:

* Natural language understanding
* Reasoning
* Planning
* Tool selection
* Summarization
* Explanation
* Structured information extraction
* Agent orchestration

Keep the LLM provider abstract.

The application should not be tightly coupled to a single model provider.

Design an AI provider interface so models can be swapped.

Potential providers may include:

* Claude
* GPT
* Gemini
* Local models through Ollama

Do not hardcode API keys.

Use environment variables.

---

# 16. RAG SYSTEM

Implement Retrieval-Augmented Generation.

Use RAG for:

* User documents
* Clipboard history
* Saved memories
* Indexed files

Pipeline:

DOCUMENT
→ TEXT EXTRACTION
→ CHUNKING
→ EMBEDDING
→ VECTOR STORE
→ RETRIEVAL
→ CONTEXT
→ LLM

The system should show which sources were used when appropriate.

---

# 17. DESKTOP ARCHITECTURE

Preferred technology stack:

Frontend/Desktop:

Tauri
React
TypeScript

Backend:

Python
FastAPI

ML:

Python
PyTorch
scikit-learn
sentence-transformers

OCR:

PaddleOCR or Tesseract

Vector Search:

FAISS initially

Database:

SQLite initially

Use PostgreSQL only if there is a clear architectural reason.

---

# 18. ARCHITECTURE

Preferred high-level architecture:

WINDOWS DESKTOP
│
▼
TAURI + REACT
│
▼
FASTAPI BACKEND
│
├───────────────┐
▼               ▼
CONTEXT ENGINE      USER REQUEST
│               │
├──────┬────────┤
▼      ▼        ▼
SCREEN      CLIPBOARD  FILES
│      │        │
└──────┼────────┘
▼
ML LAYER
│
▼
RAG / MEMORY
│
▼
AGENT ORCHESTRATOR
│
┌──────┼──────┐
▼      ▼      ▼
TOOLS  PLANNER  LLM
│      │      │
└──────┼──────┘
▼
PERMISSION SYSTEM
│
▼
ACTION
│
▼
VERIFICATION
│
▼
MEMORY

Keep the architecture modular but avoid unnecessary microservices.

---

# 19. DATABASE

Use SQLite for the first version.

Design tables/entities for:

* users/settings
* files
* file_chunks
* embeddings
* clipboard_items
* screenshots
* memories
* agent_tasks
* agent_steps
* tool_calls
* approvals
* activity_logs

Use migrations.

Keep the schema extensible.

---

# 20. UI

Build a modern, professional desktop interface.

Main screen:

ContextAI

"What can I help you with?"

Quick actions:

* Screen
* Clipboard
* Files
* Search

Sections:

* Recent Activity
* Agent Activity
* Memory
* Files
* Settings
* Privacy
* ML Dashboard

The interface should look like a real commercial product.

Avoid making it look like a generic AI chat website.

---

# 21. AGENT ACTIVITY PANEL

Show transparent execution.

Example:

ContextAI Activity

✓ Received request
✓ Inspected Downloads
✓ Classified 132 files
✓ Found 7 duplicates
✓ Generated organization plan

Waiting for approval...

After approval:

✓ Moved 24 files
✓ Created 4 folders
✓ Verified changes

The user should understand what the agent is doing.

---

# 22. ML DASHBOARD

Create an ML evaluation dashboard.

Show:

File Classification
Accuracy
Precision
Recall
F1

Screenshot Classification
Accuracy
Precision
Recall
F1

Semantic Similarity
Precision@K
Recall@K where applicable

Also show:

* Dataset size
* Inference time
* Confusion matrix

Only use real measured results.

---

# 23. AGENT OBSERVABILITY

Track:

* User request
* Agent plan
* Tool calls
* Tool results
* Approval events
* Errors
* Retry attempts
* Final outcome
* Execution time

Do not log sensitive user content unnecessarily.

---

# 24. PRIVACY

The application should be local-first.

Important principles:

* Do not scan the entire computer without permission.
* Do not upload files silently.
* Do not upload screenshots silently.
* Do not store clipboard content without user consent.
* Provide privacy mode.
* Provide incognito mode.
* Allow memory deletion.
* Allow complete data deletion.
* Allow disabling individual context sources.

The user must always know what data ContextAI is accessing.

---

# 25. ERROR HANDLING

Every component needs proper error handling.

Examples:

* LLM unavailable
* OCR failure
* File permission denied
* File moved externally
* Vector database failure
* ML model failure
* Tool timeout
* Agent planning failure
* Invalid tool arguments

The agent should never claim an action succeeded if it did not.

---

# 26. TESTING

Create:

* Unit tests
* Integration tests
* API tests
* ML tests
* Agent tests
* Tool tests
* Permission tests
* RAG retrieval tests
* Security tests

Important agent scenarios should have automated tests.

Example:

"Organize Downloads"

Expected:

* Files classified
* Plan created
* Approval requested
* Approved files moved
* Result verified

---

# 27. ADVANCED FEATURES — AFTER MVP

Only implement these after the core system is stable.

## Developer Mode

ContextAI understands:

* VS Code
* Terminal
* Git
* Project structure
* Programming errors

Example:

"Fix this error."

The agent can inspect the project, diagnose the issue, propose a change, ask for permission, make the change, run tests, and report the result.

---

## Smart Notifications

Predict notification importance.

Classify:

Important
Normal
Low priority

---

## Browser Intelligence

Understand the current webpage.

Example:

User:

"Summarize this page and save the important points."

---

## Voice Interaction

Allow:

"Find my ML notes."

"Open my project."

"Organize these files."

---

## Workflow Learning

Learn repetitive user-approved workflows.

Example:

Every Monday:

Open VS Code
→ Open project
→ Start backend
→ Start frontend
→ Open browser

ContextAI can recognize the pattern and offer:

"Run your usual development setup?"

Never execute learned workflows silently without appropriate permission.

---

# 28. DEVELOPMENT PHASES

Build the system incrementally.

## PHASE 1 — FOUNDATION

Implement:

* Repository
* Tauri
* React
* TypeScript
* FastAPI
* SQLite
* Basic UI
* Backend communication
* Configuration system
* Logging

## PHASE 2 — SCREEN INTELLIGENCE

Implement:

* Global hotkey
* Screenshot capture
* OCR
* Screen analysis
* Screen classification
* Screen Q&A

## PHASE 3 — CLIPBOARD

Implement:

* Clipboard history
* Classification
* Search
* Semantic retrieval
* Privacy controls

## PHASE 4 — FILE INTELLIGENCE

Implement:

* Folder selection
* File indexing
* Metadata
* Text extraction
* File classification
* Semantic search

## PHASE 5 — ML

Implement:

* Dataset pipeline
* File classifier
* Screenshot classifier
* Similarity model
* Importance model
* Evaluation system
* ML dashboard

## PHASE 6 — RAG + MEMORY

Implement:

* Embeddings
* Vector search
* Retrieval
* RAG
* Memory
* Memory management UI

## PHASE 7 — AGENTIC AI

Implement:

* Agent orchestrator
* Planning
* Tool calling
* Permission system
* Execution
* Verification
* Retry/recovery

## PHASE 8 — AUTOMATION

Implement:

* File organization
* Duplicate detection
* Developer tools
* Browser tools

## PHASE 9 — SECURITY

Implement:

* Permission system
* Audit logs
* Privacy controls
* Data deletion
* Secure tool execution

## PHASE 10 — EVALUATION

Implement:

* Unit tests
* Integration tests
* Agent benchmarks
* ML benchmarks
* Performance testing
* Security testing

## PHASE 11 — RELEASE

Implement:

* Windows packaging
* Installer
* Configuration
* Documentation
* User guide
* Demo workflow

---

# 29. DEVELOPMENT RULES

IMPORTANT:

Do NOT attempt to implement the entire project at once.

Build one phase at a time.

For every phase:

1. Understand requirements.
2. Inspect current code.
3. Design implementation.
4. Implement.
5. Run tests.
6. Fix errors.
7. Verify functionality.
8. Update documentation.
9. Show what changed.
10. Wait for approval before starting the next major phase.

Never generate fake implementations.

Never claim a feature is complete if it is not working.

Never fabricate ML metrics.

Never hardcode API keys.

Never silently perform dangerous computer actions.

Do not over-engineer.

Do not introduce unnecessary microservices.

Prefer modular code inside a manageable application.

Use type hints and validation.

Use proper logging.

Use configuration/environment variables.

---

# 30. GITHUB QUALITY

The repository should eventually contain:

README.md
LICENSE
.env.example
.gitignore

/docs
architecture.md
agent-design.md
ml-design.md
security.md
privacy.md
setup.md

/tests

The README should explain:

* Problem
* Solution
* Features
* Architecture
* AI components
* ML components
* Agent architecture
* Security
* Installation
* Usage
* Evaluation
* Future work

---

# 31. FIRST TASK — DO NOT CODE YET

For this first interaction, DO NOT start implementing the application.

First:

1. Analyze the complete ContextAI requirements.
2. Identify contradictions or risks.
3. Propose the final architecture.
4. Propose the repository structure.
5. Propose the database schema.
6. Define the ML architecture.
7. Define the Agent architecture.
8. Define the RAG architecture.
9. Define the permission/security architecture.
10. Define the development roadmap.
11. Identify difficult technical problems.
12. Identify what should be MVP versus future features.
13. Create/update README.md with the project vision and architecture.

Then STOP.

Do not implement Phase 1 until I explicitly tell you:

"Start Phase 1."

When I approve a phase, implement ONLY that phase, test it thoroughly, fix errors, and then wait for the next instruction.

You are building a real product, not a demonstration mockup.
