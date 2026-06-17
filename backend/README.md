# DS-STAR: Data Science - Stateful Task & Reasoning

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/release/python-3100/)

DS-STAR is an autonomous platform that translates natural language queries into executable data science workflows. By leveraging FastAPI and LangGraph, the system coordinates a team of specialized AI agents to analyze datasets, plan multi-step processes, write Python code, and safely execute it within an isolated Docker sandbox.

## Table of Contents
- [Features](#features)
- [Architecture](#architecture)
- [Technologies Used](#technologies-used)
- [Installation & Setup](#installation--setup)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Agentic Workflow Orchestration:** Implements a state machine using LangGraph to sequence and manage Analyzer, Planner, Coder, Verifier, and Debugger agents.
- **Self-Correcting Execution Loop:** Automatically catches runtime exceptions, analyzes tracebacks, patches the generated code, and re-executes until the output satisfies verification criteria.
- **Secure Sandbox Environment:** All generated Python scripts execute inside an ephemeral, network-isolated Docker container with read-only data mounts to ensure system security and data integrity.
- **Tiered LLM Routing:** Optimizes operational cost and response latency by routing complex reasoning tasks to `gemini-2.5-pro` and classification/formatting tasks to `gemini-2.5-flash`.
- **Persistent State Management:** Utilizes a Supabase backend to track task queries, execution plans, and outcomes across distributed agent sessions.

## Architecture

The backend architecture consists of four primary components:

1. **API Layer (`main.py`)**: A FastAPI application exposing endpoints for task submission and status polling.
2. **LLM Router (`llm_router.py`)**: A centralized gateway for all external LLM API calls, enforcing tier-based model assignment.
3. **Graph Engine (`agents/graph.py`)**: The core LangGraph state machine maintaining the `TaskState` single source of truth throughout the execution lifecycle.
4. **Execution Sandbox (`agents/executor.py`)**: An integration layer that manages the lifecycle of the `dsstar-sandbox:latest` Docker container for secure script execution.

## Technologies Used

- **Backend:** Python, FastAPI
- **AI/Orchestration:** LangGraph, LangChain, Google GenAI (Gemini 2.5 Pro / Flash)
- **Database:** Supabase (PostgreSQL)
- **Infrastructure:** Docker

## Installation & Setup

### Prerequisites
- Python 3.10 or higher
- Docker (daemon must be running)
- Supabase account and API credentials
- Google Gemini API Key

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/AzharuddinKazi/Agent-DASC.git
   cd Agent-DASC
   ```

2. **Configure Environment Variables**
   Create a `.env` file in the `backend/` directory with the following variables:
   ```env
   SUPABASE_URL="your-supabase-url"
   SUPABASE_SERVICE_KEY="your-supabase-key"
   GEMINI_API_KEY="your-gemini-key"
   DSSTAR="/absolute/path/to/DSStar"
   ```

3. **Build the Execution Sandbox**
   ```bash
   cd sandbox
   docker build -t dsstar-sandbox:latest .
   ```

4. **Run the API Server**
   ```bash
   cd backend
   uv run uvicorn main:app --reload
   ```

## Roadmap

- [x] **Phase 1:** Docker sandbox setup and isolation testing
- [x] **Phase 2:** FastAPI + Supabase integration for task persistence
- [x] **Phase 3:** LLM Router implementation and Gemini API testing
- [x] **Phase 4:** LangGraph agent wiring and end-to-end testing
- [ ] **Phase 5:** Asynchronous FastAPI integration for the DS-STAR loop
- [ ] **Phase 6:** WebSocket streaming and real-time task status updates
- [ ] **Phase 7:** Automated data ingestion pipeline (inbox watcher, restructure script)
- [ ] **Phase 8:** React frontend interface development
- [ ] **Phase 9:** DS-STAR+ integration and automated document generation
- [ ] **Phase 10:** System hardening, observability implementation, and cost controls

## Contributing
Contributions, issues, and feature requests are welcome. Feel free to check the issues page if you want to contribute.

## License
Distributed under the MIT License. See `LICENSE` for more information.
