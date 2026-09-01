# ContextAI — AI Desktop Intelligence & Automation Platform

An intelligent Windows desktop companion that understands your computer context and helps you complete everyday tasks through agentic AI, machine learning, and desktop automation.

## Vision

ContextAI combines **Agentic AI**, **Generative AI**, **Machine Learning**, **NLP**, **Computer Vision**, **OCR**, **Semantic Search**, **RAG**, **Vector Search**, **Tool Calling**, **Planning**, **Memory**, **Desktop Automation**, **Human-in-the-loop Security**, **Evaluation**, **Observability**, and **Privacy** into a production-quality Windows desktop application.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    WINDOWS DESKTOP (Tauri + React)              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Main Window │  │  Hotkey UI   │  │  System Tray /       │  │
│  │  (Chat/Query)│  │  (Overlay)   │  │  Notifications       │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
└─────────┼─────────────────┼─────────────────────┼──────────────┘
          │                 │                     │
          ▼                 ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND (Python)                     │
│  ┌─────────────┐ ┌──────────────┐ ┌────────────┐ ┌───────────┐ │
│  │  API Routes │ │  WebSocket   │ │  Auth/     │ │  Config   │ │
│  │  (REST)     │ │  Manager     │ │  Permissions│ │  Manager  │ │
│  └──────┬──────┘ └──────┬───────┘ └─────┬──────┘ └─────┬─────┘ │
└─────────┼────────────────┼───────────────┼──────────────┼───────┘
          │                │               │              │
          ▼                ▼               ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      CORE SERVICES LAYER                        │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌────────┐ ┌────────┐ │
│  │ Context  │ │  Agent    │ │   ML     │ │  RAG   │ │ Memory │ │
│  │ Engine   │ │ Orchestr. │ │ Service  │ │ Service│ │ Manager│ │
│  └────┬─────┘ └─────┬─────┘ └────┬─────┘ └───┬────┘ └────┬───┘ │
└───────┼──────────────┼─────────────┼───────────┼──────────┼──────┘
        │              │             │           │          │
        ▼              ▼             ▼           ▼          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA & ML LAYER                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────┐ │
│  │ SQLite   │ │  FAISS   │ │  ML      │ │  OCR     │ │ Screen│ │
│  │ (Metadata)│ │ (Vectors)│ │ Models   │ │  Engine  │ │ Capture│ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └───────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology |
|-------|------------|
| **Frontend/Desktop** | Tauri 2.x, React 18, TypeScript, Vite |
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy 2.0, Alembic |
| **ML** | PyTorch, scikit-learn, sentence-transformers |
| **OCR** | PaddleOCR |
| **Vector Search** | FAISS |
| **Database** | SQLite (local-first) |
| **Communication** | HTTP REST + WebSocket |

## Features (MVP - Phases 1-7)

### Phase 1: Foundation ✓
- Tauri + React + TypeScript frontend
- FastAPI backend with SQLite
- Configuration system
- Structured logging
- System tray & global hotkey foundation
- Health check endpoints
- Permission system foundation (Green/Yellow/Red)

### Phase 2: Screen Intelligence
- Global hotkey (Ctrl+Space)
- Screenshot capture
- OCR (PaddleOCR)
- Screen classification
- Screen Q&A

### Phase 3: AI Clipboard
- Clipboard history & monitoring
- Content classification
- Semantic search
- Privacy controls

### Phase 4: File Intelligence
- Folder selection & indexing
- Metadata extraction
- Text extraction
- File classification
- Semantic search

### Phase 5: ML System
- 5 ML models (file/screen classification, similarity, importance, anomaly)
- Dataset pipeline
- Evaluation system
- ML dashboard

### Phase 6: RAG + Memory
- Embeddings (sentence-transformers)
- FAISS vector store
- Retrieval & RAG pipeline
- User-controlled memory system

### Phase 7: Agentic AI
- Agent orchestrator
- Planning & tool calling
- Permission system
- Execution & verification
- Retry/recovery

## Quick Start

### Prerequisites
- **Rust** 1.75+ (`curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`)
- **Node.js** 20+ (`winget install OpenJS.NodeJS`)
- **Python** 3.11+ (`winget install Python.Python.3.11`)
- **pnpm** (`npm install -g pnpm`)

### Development Setup

```bash
# Clone and enter repository
cd ContextAI

# Install frontend dependencies
cd src/frontend && pnpm install && cd ../..

# Install backend dependencies
cd src/backend && python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt && cd ../..

# Build Tauri (Rust) dependencies
cd src/tauri && cargo build && cd ../..

# Run development servers
# Terminal 1: FastAPI backend
cd src/backend && .venv\Scripts\activate && uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend dev server
cd src/frontend && pnpm dev

# Terminal 3: Tauri app
cd src/tauri && cargo tauri dev
```

### Building for Production

```bash
# Build frontend
cd src/frontend && pnpm build

# Build backend (creates standalone executable with PyInstaller or similar)
cd src/backend && .venv\Scripts\activate && pip install pyinstaller && pyinstaller --onefile app/main.py

# Build Tauri app
cd src/tauri && cargo tauri build
```

## Project Structure

```
contextai/
├── src/
│   ├── tauri/                 # Tauri Rust backend
│   │   ├── src/
│   │   │   ├── main.rs
│   │   │   ├── commands/      # Tauri commands
│   │   │   ├── hotkey.rs      # Global hotkey handling
│   │   │   ├── tray.rs        # System tray
│   │   │   └── ipc.rs         # Frontend-backend communication
│   │   ├── Cargo.toml
│   │   └── tauri.conf.json
│   ├── frontend/              # React + TypeScript
│   │   ├── src/
│   │   │   ├── components/
│   │   │   ├── pages/
│   │   │   ├── hooks/
│   │   │   ├── services/
│   │   │   ├── store/
│   │   │   ├── types/
│   │   │   └── utils/
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   └── vite.config.ts
│   └── backend/               # FastAPI Python backend
│       ├── app/
│       │   ├── api/v1/        # REST routes
│       │   ├── core/          # Config, security, permissions, logging
│       │   ├── services/      # Business logic services
│       │   ├── models/        # Database & Pydantic models
│       │   ├── tools/         # Tool system
│       │   └── llm/           # LLM provider abstraction
│       ├── tests/
│       ├── requirements.txt
│       └── alembic/           # Database migrations
├── ml/                        # ML models & training
├── scripts/                   # Build & dev scripts
├── docker/                    # Docker configuration
├── docs/                      # Documentation
├── README.md
├── LICENSE
├── .env.example
└── .gitignore
```

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Backend
DATABASE_URL=sqlite:///./contextai.db
FASTAPI_HOST=127.0.0.1
FASTAPI_PORT=8000
LOG_LEVEL=INFO

# LLM Providers (optional - for future phases)
CLAUDE_API_KEY=
OPENAI_API_KEY=
GEMINI_API_KEY=
OLLAMA_BASE_URL=http://localhost:11434

# Frontend
VITE_API_URL=http://127.0.0.1:8000
VITE_WS_URL=ws://127.0.0.1:8000
```

## Security & Privacy

- **Local-first**: All data stays on your machine
- **Permission system**: Green (auto), Yellow (confirm), Red (always confirm)
- **No silent uploads**: Explicit user consent required for any external communication
- **Privacy mode**: Disable any context source individually
- **Complete data deletion**: One-click wipe of all stored data

## Development Phases

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | Foundation | 🚧 In Progress |
| 2 | Screen Intelligence | ⏳ Planned |
| 3 | AI Clipboard | ⏳ Planned |
| 4 | File Intelligence | ⏳ Planned |
| 5 | ML System | ⏳ Planned |
| 6 | RAG + Memory | ⏳ Planned |
| 7 | Agentic AI | ⏳ Planned |
| 8 | Automation | ⏳ Planned |
| 9 | Security Hardening | ⏳ Planned |
| 10 | Evaluation | ⏳ Planned |
| 11 | Release | ⏳ Planned |

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for development guidelines.