# STIHL Analytics Agent

## Project Overview
AI-powered analytics platform for STIHL power equipment data with natural language querying, proactive insights, and semantic product search.

## Tech Stack
- Frontend: React 18, Fluent UI v9, TypeScript, Vite (src/frontend)
- Backend: Python 3.11, FastAPI, Gunicorn/Uvicorn (src/api)
- AI: Azure OpenAI gpt-4o-mini with function calling
- Data: Databricks SQL Warehouse, Unity Catalog, Vector Search (BGE-Large)

## Architecture
- SkillRouter: src/api/agent/skills/router.py (7 skills)
- SQL Tools: src/api/agent/tools/sql_tools.py (8 functions)
- RAG Tools: src/api/agent/tools/rag_tools.py (3 functions)
- API Routes: src/api/routes.py
- Main App: src/api/main.py

## Local Development
- Backend: cd src/api && uvicorn main:app --reload --port 8000
- Frontend: cd src/frontend && npm run dev
- Access: http://localhost:5173

## Deployment
- Azure Container Apps (ca-stihl-rnofgqn7g5tzm)
- Azure Container Registry
- Resource Group: rg-ai-foundry-learning

## Current Status
Deployed and functional. UI refinements in progress.
