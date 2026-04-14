# MoodMap — Product Requirements Document & Development Plan
**Version:** 1.0 | **Author:** Claude (Anthropic) | **Date:** April 2026  
**Target:** Student Developer | **Timeline:** 14 Days | **Primary Tool:** Claude Code

---

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Solution Overview](#3-solution-overview)
4. [System Architecture](#4-system-architecture)
5. [Feature Specifications](#5-feature-specifications)
6. [ML Model Specifications](#6-ml-model-specifications)
7. [Tech Stack & APIs](#7-tech-stack--apis)
8. [Database Schema](#8-database-schema)
9. [API Endpoint Specifications](#9-api-endpoint-specifications)
10. [CI/CD Pipeline](#10-cicd-pipeline)
11. [Day-by-Day Development Plan](#11-day-by-day-development-plan)
12. [Deployment Guide](#12-deployment-guide)
13. [Folder Structure](#13-folder-structure)

---

## 1. Executive Summary

MoodMap is a multimodal emotional intelligence companion that combines NLP, audio analysis, and agentic AI to detect early signs of emotional distress and proactively recommend personalized, evidence-based interventions. It processes daily journal entries and optional voice recordings to build a personal emotional model per user, then deploys a LangGraph-powered agent that monitors patterns, detects anomalies, and nudges users before distress escalates.

**Core differentiator:** Unlike passive mood trackers (Daylio, Reflectly), MoodMap is *proactive* — it comes to you with a nudge when it detects a concerning emotional trajectory, rather than waiting for you to self-report.

---

## 2. Problem Statement

### The Gap
- 1 in 4 people globally experience a mental health issue each year
- 75% of those affected never receive any professional support
- The average delay between symptom onset and treatment is **11 years**
- Existing apps are passive loggers — they only act when the user initiates

### Who This Is For
**Primary user:** University students or young professionals aged 18–30 experiencing stress, anxiety, or low mood, who are not in acute crisis but would benefit from early, gentle intervention.

### Jobs to Be Done
1. "I want to track how I'm feeling without it feeling like a chore"
2. "I want something to notice when I'm spiralling before I do"
3. "I want personalised, science-backed suggestions — not generic tips"
4. "I want to be able to share my mood patterns with a therapist easily"

---

## 3. Solution Overview

### How It Works
```
User writes journal / records voice note
        ↓
Preprocessing pipeline (text cleaning, audio transcription)
        ↓
Multimodal sentiment analysis (RoBERTa + Wav2Vec2)
        ↓
Personal emotional trajectory model (per-user LSTM)
        ↓
LangGraph distress detection agent
        ↓
Personalised CBT nudge or proactive check-in
        ↓
Dashboard updates with mood heatmap + trends
```

### Key Outcomes
- Users log in under 2 minutes per day
- Agent detects 3-day negative trajectories and proactively sends nudges
- Weekly therapist-ready reports generated automatically
- Model improves with every correction the user gives

---

## 4. System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────┐
│                 FRONTEND (Next.js)               │
│  Journal UI | Voice Recorder | Dashboard | Auth  │
└───────────────────┬─────────────────────────────┘
                    │ HTTPS REST / WebSocket
┌───────────────────▼─────────────────────────────┐
│              BACKEND (FastAPI)                   │
│  /journal  /voice  /insights  /report  /agent   │
└────┬──────────────┬──────────────┬──────────────┘
     │              │              │
┌────▼────┐  ┌──────▼──────┐  ┌───▼──────────────┐
│ ML      │  │  LangGraph  │  │  TimescaleDB      │
│ Service │  │  Agent      │  │  (mood history)   │
│         │  │  (distress  │  │                   │
│ RoBERTa │  │  detection) │  │  Supabase Auth    │
│ Wav2Vec2│  │             │  │  (users/sessions) │
│ LSTM    │  │  Claude API │  │                   │
└─────────┘  └─────────────┘  └──────────────────┘
```

### Components
| Component | Technology | Purpose |
|-----------|------------|---------|
| Frontend | Next.js 14 + Tailwind | User interface |
| Backend API | FastAPI (Python) | Business logic, routing |
| ML Service | PyTorch + HuggingFace | Model inference |
| Agent | LangGraph + Claude API | Proactive nudges |
| Primary DB | TimescaleDB (PostgreSQL) | Time-series mood data |
| Auth | Supabase | User auth, sessions |
| Queue | Celery + Redis | Async analysis jobs |
| Tracking | MLflow | ML experiment tracking |
| CI/CD | GitHub Actions | Automated testing + deploy |
| Deploy | Vercel (FE) + Railway (BE) | Hosting |

---

## 5. Feature Specifications

### Feature 1: Daily Journal Entry
**What it does:** User writes a free-text journal entry. Optionally records a voice note. Both are saved and queued for analysis.

**Acceptance criteria:**
- Text input with 2000 character limit
- Voice recording up to 3 minutes (browser MediaRecorder API)
- Auto-save draft every 30 seconds
- Entry saved with timestamp, user_id, raw text, audio URL

**UI components:**
- Rich text editor (TipTap)
- Waveform audio recorder (wavesurfer.js)
- Mood tags (optional: pre-select feeling words)
- Submit button

---

### Feature 2: Multimodal Sentiment Analysis
**What it does:** After entry is submitted, the system runs text + audio through fine-tuned models to extract emotion scores across 7 dimensions.

**Emotion dimensions:** Joy, Sadness, Anger, Fear, Disgust, Surprise, Neutral

**Output stored per entry:**
```json
{
  "text_emotions": {"joy": 0.12, "sadness": 0.67, "anger": 0.04, ...},
  "voice_emotions": {"energy": 0.34, "valence": -0.22, "arousal": 0.41},
  "fused_score": -0.31,
  "dominant_emotion": "sadness",
  "confidence": 0.84
}
```

**Processing time target:** < 8 seconds for text, < 15 seconds for audio

---

### Feature 3: Mood Heatmap Dashboard
**What it does:** Visual dashboard showing emotional patterns over time using a GitHub-style heatmap, weekly trend chart, and dominant emotion breakdown.

**Charts to include:**
- Calendar heatmap (D3.js) — colour = fused_score per day
- 30-day rolling mood line chart (Recharts)
- Emotion distribution donut chart
- Streak tracker (consecutive logging days)

**Data range options:** 7 days, 30 days, 90 days, All time

---

### Feature 4: LangGraph Distress Detection Agent
**What it does:** Runs daily (via Celery Beat) for each user. Analyses the last 7 days of mood scores, identifies negative trajectories, and decides whether to send a nudge.

**Agent logic (ReAct loop):**
1. `fetch_mood_history(user_id, days=7)` — retrieve recent scores
2. `compute_trajectory(scores)` — calculate slope + volatility
3. `check_distress_threshold(trajectory)` — compare against user baseline
4. `if distress_detected: generate_nudge(user_context)` — personalised with Claude API
5. `send_notification(user_id, nudge)` — push/email

**Distress threshold rule:** 3 consecutive days with fused_score < -0.4 OR score drops > 0.5 in 48 hours

**Nudge types:**
- Breathing exercise prompt
- CBT thought-challenging prompt
- Physical activity suggestion
- Social connection prompt
- Professional help referral (if severe)

---

### Feature 5: Personalised CBT Nudge Engine
**What it does:** When the agent decides to nudge, it calls Claude API with user context (recent entries, dominant emotions, past helpful interventions) to generate a uniquely personalised message.

**Prompt structure sent to Claude:**
```
System: You are a compassionate mental wellness companion trained in CBT techniques.
        Never diagnose. Always validate. Suggest, don't prescribe.
User context: [last 3 journal summaries, dominant emotion, trajectory]
Task: Generate a warm, specific, 3-sentence nudge with one actionable suggestion.
```

---

### Feature 6: Continual Learning Feedback Loop
**What it does:** After receiving a nudge, the user rates it (helpful / not helpful). This feedback is logged and used weekly to re-rank intervention strategies per user.

**Storage:** feedback table with nudge_id, rating, timestamp
**Retraining trigger:** Weekly Celery task re-scores intervention weights per user

---

### Feature 7: Weekly Therapist Report (PDF)
**What it does:** Auto-generated PDF report every Sunday showing the week's mood trajectory, key emotion patterns, journal themes (LDA topic extraction), and intervention history. Downloadable + shareable link.

**PDF contents:**
- Week summary (mood trajectory narrative)
- Heatmap image (server-side rendered)
- Emotion breakdown table
- Journal themes (top 3 topics)
- Intervention log + ratings
- Disclaimer footer

---

### Feature 8: Authentication & Privacy
**What it does:** Secure sign up/login via Supabase Auth. All mood data encrypted at rest. Users can delete all data at any time.

**Auth methods:** Email/password, Google OAuth
**Privacy features:** Data deletion endpoint, export-my-data endpoint, no third-party analytics

---

## 6. ML Model Specifications

### Model 1: Text Emotion Classifier (RoBERTa)

**Base model:** `roberta-base` (HuggingFace)  
**Dataset:** GoEmotions (58k Reddit comments, 27 emotion labels → mapped to 7)  
**Fine-tuning approach:** Multi-label classification with BCEWithLogitsLoss  
**Training environment:** Google Colab (free T4 GPU, ~2 hours)

**Training script outline:**
```python
from transformers import RobertaForSequenceClassification, RobertaTokenizer
from datasets import load_dataset
import torch

# Load GoEmotions
dataset = load_dataset("go_emotions", "simplified")

# Map to 7 emotions, tokenize, fine-tune
model = RobertaForSequenceClassification.from_pretrained(
    "roberta-base", num_labels=7, problem_type="multi_label_classification"
)

# Use HuggingFace Trainer API with:
# - learning_rate=2e-5
# - num_train_epochs=3
# - per_device_train_batch_size=16
# - warmup_steps=500

# Save to HuggingFace Hub (free): username/moodmap-roberta
```

**Expected performance:** F1 ~0.62 on GoEmotions simplified (matches SOTA for 7-class)

---

### Model 2: Voice Affect Analyser (Wav2Vec2)

**Base model:** `facebook/wav2vec2-base` (HuggingFace)  
**Dataset:** RAVDESS (7356 audio files, 8 emotions, actors)  
**Task:** Regression on valence + arousal (Russell's circumplex model)  
**Fine-tuning approach:** Add regression head, freeze base layers for first epoch

**Training script outline:**
```python
from transformers import Wav2Vec2ForSequenceClassification, Wav2Vec2Processor

model = Wav2Vec2ForSequenceClassification.from_pretrained(
    "facebook/wav2vec2-base", num_labels=2  # valence, arousal
)

# Freeze feature extractor for first 2 epochs
for param in model.wav2vec2.feature_extractor.parameters():
    param.requires_grad = False

# Training: ~1 hour on Colab T4
# learning_rate=1e-4, epochs=5, batch_size=8
```

**Expected performance:** Valence PCC ~0.55, Arousal PCC ~0.63 (typical for RAVDESS)

---

### Model 3: Multimodal Fusion Head

**Architecture:** Late fusion with attention weighting  
**Input:** RoBERTa output (768-dim) + Wav2Vec2 output (2-dim) → concat → Linear(770, 128) → ReLU → Linear(128, 1)  
**Output:** Single fused score [-1, 1] (negative = distress, positive = wellbeing)  
**Training:** On combined features from entries that have BOTH text + audio

**Fallback:** If no audio present, use text score directly as fused score

---

### Model 4: Per-User LSTM Trajectory Model

**Architecture:** LSTM(input=8, hidden=32, layers=2) → Linear(32, 1)  
**Input:** Last 7 days of [fused_score, day_of_week, time_since_last_entry, ...] (8 features)  
**Output:** Predicted tomorrow score (used to detect incoming decline)  
**Training:** Starts after user has 14 days of data; retrained weekly via Celery task

---

### Training Pipeline Summary

| Step | Tool | Time | Cost |
|------|------|------|------|
| Preprocess GoEmotions | Python / Pandas | 30 min | Free |
| Fine-tune RoBERTa | Google Colab T4 | 2 hrs | Free |
| Fine-tune Wav2Vec2 | Google Colab T4 | 1 hr | Free |
| Push models to HuggingFace Hub | HuggingFace CLI | 15 min | Free |
| Fusion head training | Local / Colab | 30 min | Free |
| Experiment tracking | MLflow (local) | Ongoing | Free |

---

## 7. Tech Stack & APIs

### Frontend
| Technology | Version | Purpose | Install |
|------------|---------|---------|---------|
| Next.js | 14+ | React framework with App Router | `npx create-next-app@latest` |
| Tailwind CSS | 3+ | Styling | Bundled with Next.js setup |
| TipTap | 2+ | Rich text journal editor | `npm install @tiptap/react` |
| Framer Motion | 11+ | Animations and transitions | `npm install framer-motion` |
| Recharts | 2+ | Line/bar charts | `npm install recharts` |
| D3.js | 7+ | Calendar heatmap | `npm install d3` |
| wavesurfer.js | 7+ | Audio waveform recorder | `npm install wavesurfer.js` |
| SWR | 2+ | Data fetching / caching | `npm install swr` |
| Zustand | 4+ | Lightweight state management | `npm install zustand` |

### Backend
| Technology | Version | Purpose | Install |
|------------|---------|---------|---------|
| FastAPI | 0.111+ | Python web framework | `pip install fastapi uvicorn` |
| SQLAlchemy | 2+ | ORM for DB access | `pip install sqlalchemy` |
| Alembic | 1.13+ | DB migrations | `pip install alembic` |
| Celery | 5+ | Async task queue | `pip install celery` |
| Redis | 5+ | Celery broker + cache | `pip install redis` |
| python-jose | 3+ | JWT token handling | `pip install python-jose` |
| boto3 | 1.34+ | S3 audio file storage | `pip install boto3` |
| fpdf2 | 2.7+ | PDF report generation | `pip install fpdf2` |
| pydantic | 2+ | Data validation | Bundled with FastAPI |

### ML / AI
| Technology | Version | Purpose | Install |
|------------|---------|---------|---------|
| PyTorch | 2.3+ | Model training + inference | `pip install torch` |
| HuggingFace Transformers | 4.41+ | RoBERTa, Wav2Vec2 | `pip install transformers` |
| HuggingFace Datasets | 2.19+ | Load GoEmotions, RAVDESS | `pip install datasets` |
| PEFT | 0.11+ | LoRA fine-tuning (optional) | `pip install peft` |
| LangChain | 0.2+ | Agent framework | `pip install langchain` |
| LangGraph | 0.1+ | Stateful agent graphs | `pip install langgraph` |
| MLflow | 2.13+ | Experiment tracking | `pip install mlflow` |
| Optuna | 3.6+ | Hyperparameter tuning | `pip install optuna` |
| librosa | 0.10+ | Audio preprocessing | `pip install librosa` |
| soundfile | 0.12+ | Audio file I/O | `pip install soundfile` |

### External APIs & Services
| Service | Purpose | Free Tier | Sign Up |
|---------|---------|-----------|---------|
| Anthropic Claude API | LangGraph nudge generation | $5 credit | console.anthropic.com |
| Supabase | Auth + PostgreSQL hosting | 500MB DB, 50k MAU | supabase.com |
| HuggingFace Hub | Model hosting + inference | Free for public models | huggingface.co |
| Cloudflare R2 | Audio file storage (S3-compatible) | 10GB free | cloudflare.com |
| Resend | Transactional emails (nudges) | 3k emails/month | resend.com |
| Vercel | Frontend deployment | Free hobby tier | vercel.com |
| Railway | Backend + Redis deployment | $5 free credit | railway.app |
| Google Colab | GPU training | Free T4 GPU | colab.research.google.com |

### Dev Tools
| Tool | Purpose |
|------|---------|
| Claude Code | AI-assisted development (primary coding tool) |
| Docker + Docker Compose | Local development environment |
| GitHub Actions | CI/CD pipeline |
| Postman | API testing |
| pgAdmin | Database management |

---

## 8. Database Schema

### Users Table (Supabase Auth handles most of this)
```sql
-- Extended profile stored in TimescaleDB
CREATE TABLE user_profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id),
  username TEXT UNIQUE,
  timezone TEXT DEFAULT 'UTC',
  notification_enabled BOOLEAN DEFAULT TRUE,
  baseline_score FLOAT,  -- computed after 14 days
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Journal Entries Table
```sql
CREATE TABLE journal_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE,
  raw_text TEXT NOT NULL,
  audio_url TEXT,  -- Cloudflare R2 URL
  word_count INT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON journal_entries(user_id, created_at DESC);
```

### Mood Scores Table (TimescaleDB hypertable)
```sql
CREATE TABLE mood_scores (
  time TIMESTAMPTZ NOT NULL,
  user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE,
  entry_id UUID REFERENCES journal_entries(id),
  text_joy FLOAT, text_sadness FLOAT, text_anger FLOAT,
  text_fear FLOAT, text_disgust FLOAT, text_surprise FLOAT, text_neutral FLOAT,
  voice_valence FLOAT, voice_arousal FLOAT, voice_energy FLOAT,
  fused_score FLOAT,
  dominant_emotion TEXT,
  confidence FLOAT,
  analysis_version TEXT  -- model version tag
);
SELECT create_hypertable('mood_scores', 'time');
CREATE INDEX ON mood_scores(user_id, time DESC);
```

### Nudges Table
```sql
CREATE TABLE nudges (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE,
  nudge_type TEXT,  -- 'breathing', 'cbt', 'physical', 'social', 'referral'
  content TEXT,
  trigger_reason TEXT,
  sent_at TIMESTAMPTZ DEFAULT NOW(),
  opened_at TIMESTAMPTZ,
  rating INT CHECK (rating IN (1, -1, 0))  -- helpful, not helpful, no response
);
```

### Agent State Table
```sql
CREATE TABLE agent_states (
  user_id UUID PRIMARY KEY REFERENCES user_profiles(id),
  last_checked_at TIMESTAMPTZ,
  trajectory_slope FLOAT,
  volatility FLOAT,
  distress_flag BOOLEAN DEFAULT FALSE,
  days_since_nudge INT DEFAULT 0,
  intervention_weights JSONB  -- {breathing: 0.8, cbt: 0.6, ...}
);
```

---

## 9. API Endpoint Specifications

### Authentication (delegated to Supabase)
All endpoints require `Authorization: Bearer <supabase_jwt>` header.

### Journal Endpoints
```
POST   /api/v1/journal          - Submit new journal entry
GET    /api/v1/journal          - Get user's entries (paginated)
GET    /api/v1/journal/{id}     - Get single entry with mood scores
DELETE /api/v1/journal/{id}     - Delete entry
```

**POST /api/v1/journal request body:**
```json
{
  "text": "Today was rough. I couldn't focus at all...",
  "audio_key": "users/abc123/2026-04-03.webm"  // optional
}
```

**Response:**
```json
{
  "entry_id": "uuid",
  "status": "queued",
  "task_id": "celery-task-uuid"
}
```

### Mood / Insights Endpoints
```
GET /api/v1/insights/summary        - Dashboard summary stats
GET /api/v1/insights/heatmap        - Calendar heatmap data (last 90 days)
GET /api/v1/insights/trend          - Time-series mood scores
GET /api/v1/insights/emotions       - Emotion distribution breakdown
```

### Analysis Endpoints
```
GET  /api/v1/analysis/status/{task_id}   - Check analysis job status
POST /api/v1/analysis/reanalyze/{id}     - Re-run analysis on entry
```

### Nudge / Agent Endpoints
```
GET  /api/v1/nudges            - Get user's nudge history
POST /api/v1/nudges/{id}/rate  - Rate a nudge (1 = helpful, -1 = not helpful)
POST /api/v1/agent/check-in    - Manually trigger agent check (for testing)
```

### Reports
```
GET /api/v1/reports/weekly         - Generate + download weekly PDF
GET /api/v1/reports/weekly/preview - JSON preview of report data
```

### User / Settings
```
GET    /api/v1/user/profile       - Get user profile
PATCH  /api/v1/user/profile       - Update preferences
DELETE /api/v1/user/data          - GDPR delete all data
GET    /api/v1/user/export        - Export all data as JSON
```

---

## 10. CI/CD Pipeline

### GitHub Actions Workflow

**Trigger:** Push to `main` branch, or PR to `main`

**Pipeline stages:**

```yaml
# .github/workflows/main.yml

name: MoodMap CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - name: Install deps
        run: pip install -r backend/requirements.txt
      - name: Run pytest
        run: pytest backend/tests/ --cov=backend --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v4

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Node
        uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: cd frontend && npm ci && npm run lint && npm run build

  deploy-backend:
    needs: [test-backend, test-frontend]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build & push Docker image
        run: |
          docker build -t moodmap-backend ./backend
          docker tag moodmap-backend registry.railway.app/moodmap-backend:latest
          docker push registry.railway.app/moodmap-backend:latest
      - name: Deploy to Railway
        uses: bervProject/railway-deploy@v1
        with:
          railway_token: ${{ secrets.RAILWAY_TOKEN }}
          service: moodmap-backend

  deploy-frontend:
    needs: [test-backend, test-frontend]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Vercel
        uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          vercel-args: '--prod'
```

### Required GitHub Secrets
```
RAILWAY_TOKEN          - Railway deployment token
VERCEL_TOKEN           - Vercel API token
VERCEL_ORG_ID          - Vercel org ID
VERCEL_PROJECT_ID      - Vercel project ID
ANTHROPIC_API_KEY      - Claude API key (for agent)
SUPABASE_URL           - Supabase project URL
SUPABASE_ANON_KEY      - Supabase anon key
CLOUDFLARE_R2_KEY      - R2 access key
```

---

## 11. Day-by-Day Development Plan

> Each day includes: what to build, Claude Code prompts to use, exact commands to run, and what APIs/keys you need.

---

### DAY 1 — Environment Setup & Project Scaffold

**Goal:** Working dev environment with all services running locally.

**Steps:**
1. Install prerequisites: Python 3.11, Node.js 20, Docker Desktop
2. Create GitHub repo: `git init moodmap && cd moodmap`
3. Set up project structure (see Section 13)
4. Create `docker-compose.dev.yml` with: TimescaleDB, Redis, MLflow
5. Set up Supabase project (free) → get URL + anon key
6. Configure `.env` files for both frontend and backend

**Claude Code prompt to use:**
```
"Create a FastAPI project scaffold for an emotional wellness app called MoodMap.
Include: main.py, routers/, models/, services/, tests/ folders.
Add docker-compose.dev.yml with timescaledb:latest-pg16, redis:7-alpine, and
mlflow server. Add a .env.example with all required variables."
```

**Commands:**
```bash
# Start local services
docker-compose -f docker-compose.dev.yml up -d

# Install Python deps
cd backend && python -m venv venv && source venv/bin/activate
pip install fastapi uvicorn sqlalchemy alembic celery redis pydantic python-jose

# Install frontend deps
cd frontend && npx create-next-app@latest . --typescript --tailwind --app
npm install @tiptap/react framer-motion recharts d3 wavesurfer.js swr zustand
```

**APIs needed today:** None yet  
**Accounts to create:** GitHub, Supabase (free), HuggingFace (free)

---

### DAY 2 — Database Schema & Auth

**Goal:** TimescaleDB schema created, Supabase auth working end-to-end.

**Steps:**
1. Write Alembic migration for all 5 tables (see Section 8)
2. Create TimescaleDB hypertable for mood_scores
3. Implement Supabase Auth in Next.js frontend (sign up, login, logout)
4. Add JWT middleware to FastAPI to verify Supabase tokens
5. Test: create account → login → hit protected `/api/v1/user/profile` endpoint

**Claude Code prompt:**
```
"Write an Alembic migration file that creates the following PostgreSQL tables for
MoodMap: user_profiles, journal_entries, mood_scores (as a TimescaleDB hypertable),
nudges, and agent_states. Include all foreign keys, indexes, and constraints from
this schema: [paste Section 8 schema]"
```

**Commands:**
```bash
cd backend
alembic init alembic
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

**APIs needed today:** Supabase URL + Anon Key  

---

### DAY 3 — Journal Entry API + File Upload

**Goal:** User can submit a journal entry with optional audio, stored in DB + R2.

**Steps:**
1. Create Cloudflare R2 bucket (free, S3-compatible)
2. Implement `POST /api/v1/journal` endpoint
3. Implement signed URL upload for audio files (frontend gets URL, uploads directly to R2)
4. Write `GET /api/v1/journal` with pagination
5. Create journal entry form in Next.js (text input + audio recorder)
6. Test full flow: write entry → optionally record audio → submit → stored in DB

**Claude Code prompt:**
```
"Write a FastAPI router for journal entries at /api/v1/journal. Include:
POST endpoint that accepts {text, audio_key}, validates the JWT, saves to
journal_entries table, and enqueues a Celery task called 'analyze_entry'.
Also write a GET endpoint with cursor-based pagination. Use SQLAlchemy async."
```

**APIs needed today:** Cloudflare R2 (create free account → create bucket → get API key)

---

### DAY 4 — RoBERTa Training on Google Colab

**Goal:** Fine-tuned RoBERTa model saved to HuggingFace Hub, ready for inference.

**Open Google Colab (colab.research.google.com) → New notebook → Runtime → T4 GPU**

**Step-by-step Colab notebook cells:**

```python
# Cell 1: Install deps
!pip install transformers datasets torch scikit-learn

# Cell 2: Load GoEmotions
from datasets import load_dataset
dataset = load_dataset("go_emotions", "simplified")
# Maps to: admiration,amusement,anger,annoyance,approval,caring,confusion,
#          curiosity,desire,disappointment,disapproval,disgust,embarrassment,
#          excitement,fear,gratitude,grief,joy,love,nervousness,optimism,
#          pride,realization,relief,remorse,sadness,surprise,neutral

# Cell 3: Remap 28 labels → 7 labels
LABEL_MAP = {
    "joy": ["joy","amusement","excitement","gratitude","love","optimism","pride","relief","admiration","approval","caring"],
    "sadness": ["sadness","grief","disappointment","remorse","embarrassment"],
    "anger": ["anger","annoyance","disapproval","disgust"],
    "fear": ["fear","nervousness"],
    "surprise": ["surprise","realization","confusion","curiosity","desire"],
    "neutral": ["neutral"],
}

# Cell 4: Fine-tune RoBERTa
from transformers import RobertaTokenizer, RobertaForSequenceClassification, Trainer, TrainingArguments

tokenizer = RobertaTokenizer.from_pretrained("roberta-base")
model = RobertaForSequenceClassification.from_pretrained("roberta-base", num_labels=7,
  problem_type="multi_label_classification")

training_args = TrainingArguments(
  output_dir="./roberta-moodmap",
  num_train_epochs=3,
  per_device_train_batch_size=16,
  learning_rate=2e-5,
  warmup_steps=500,
  evaluation_strategy="epoch",
  save_strategy="epoch",
  load_best_model_at_end=True,
)

# Cell 5: Push to HuggingFace Hub
from huggingface_hub import notebook_login
notebook_login()  # enter your HuggingFace token
model.push_to_hub("your-username/moodmap-roberta")
tokenizer.push_to_hub("your-username/moodmap-roberta")
```

**Claude Code prompt (for inference wrapper):**
```
"Write a Python class called TextEmotionAnalyzer that loads the HuggingFace model
'username/moodmap-roberta', exposes an analyze(text: str) method returning a dict
with 7 emotion scores (joy, sadness, anger, fear, disgust, surprise, neutral) as
floats, and a dominant_emotion string. Add error handling and model caching."
```

**APIs needed today:** HuggingFace account (free) + write token (Settings → Access Tokens)

---

### DAY 5 — Wav2Vec2 Training on Google Colab

**Goal:** Fine-tuned Wav2Vec2 model saved to HuggingFace Hub.

**RAVDESS Dataset:** Download from kaggle.com/datasets/uwrfkaggler/ravdess-emotional-speech-audio (free account needed)

```python
# Colab Cell 1: Install
!pip install transformers datasets torch soundfile librosa

# Cell 2: Load + preprocess RAVDESS audio files
# File naming: 03-01-01-01-01-01-01.wav
# Position 3 = emotion (01=neutral,02=calm,03=happy,04=sad,05=angry,06=fear,07=disgust,08=surprised)
# Position 4 = intensity (01=normal, 02=strong)

import librosa
import numpy as np

def load_audio(path, target_sr=16000):
    audio, sr = librosa.load(path, sr=target_sr, mono=True)
    return audio

# Map RAVDESS emotions to valence/arousal (Russell's circumplex)
EMOTION_CIRCUMPLEX = {
    "neutral": (0.0, 0.0), "calm": (0.3, -0.3),
    "happy": (0.7, 0.6), "sad": (-0.7, -0.5),
    "angry": (-0.3, 0.8), "fear": (-0.6, 0.7),
    "disgust": (-0.5, 0.3), "surprised": (0.1, 0.7)
}

# Cell 3: Fine-tune Wav2Vec2
from transformers import Wav2Vec2ForSequenceClassification, Wav2Vec2Processor

processor = Wav2Vec2Processor.from_pretrained("facebook/wav2vec2-base")
model = Wav2Vec2ForSequenceClassification.from_pretrained(
    "facebook/wav2vec2-base", num_labels=2  # valence, arousal
)

# Cell 4: Push to Hub
model.push_to_hub("your-username/moodmap-wav2vec2")
```

**APIs needed today:** Kaggle account (free), HuggingFace account

---

### DAY 6 — ML Service + Celery Analysis Pipeline

**Goal:** Celery worker picks up journal entry tasks, runs both models, saves results to DB.

**Steps:**
1. Create `ml_service/` FastAPI microservice (or integrate into main backend)
2. Implement `TextEmotionAnalyzer` and `VoiceEmotionAnalyzer` classes
3. Implement `FusionModel` class (simple weighted average for MVP)
4. Create Celery task `analyze_entry(entry_id: str)`
5. Task: fetch entry → run text model → if audio_url: run voice model → fuse → save to mood_scores

**Claude Code prompt:**
```
"Write a Celery task called analyze_entry in tasks/analysis.py. It should:
1. Fetch the journal entry by ID from PostgreSQL using SQLAlchemy async
2. Run TextEmotionAnalyzer on the entry's raw_text field
3. If entry has audio_url: download from Cloudflare R2, run VoiceEmotionAnalyzer
4. Compute fused_score as: (0.6 * text_valence) + (0.4 * voice_valence) if audio present, else text_valence
5. Save results to mood_scores table with all emotion columns
6. Update entry status to 'analyzed'
Use Redis as the Celery broker."
```

**Test:**
```bash
# Terminal 1: Start Celery worker
celery -A backend.celery_app worker --loglevel=info

# Terminal 2: Test task
python -c "from tasks.analysis import analyze_entry; analyze_entry.delay('test-uuid')"
```

---

### DAY 7 — Dashboard Frontend (Charts + Heatmap)

**Goal:** Fully functional mood dashboard with calendar heatmap, trend chart, emotion breakdown.

**Steps:**
1. Create `/dashboard` page in Next.js
2. Fetch `/api/v1/insights/heatmap` and render D3 calendar heatmap
3. Fetch `/api/v1/insights/trend` and render Recharts line chart
4. Fetch `/api/v1/insights/emotions` and render donut chart (Recharts)
5. Add date range selector (7/30/90 days)
6. Add streak tracker component

**Claude Code prompt:**
```
"Create a Next.js dashboard page at app/dashboard/page.tsx for MoodMap.
Include three components:
1. MoodHeatmap: D3.js calendar heatmap where cell colour maps from red (#E24B4A)
   at -1 to green (#639922) at +1, with neutral grey (#888780) at 0
2. MoodTrendChart: Recharts AreaChart showing 30-day rolling mood score with
   a reference line at y=0
3. EmotionBreakdown: Recharts PieChart showing dominant emotion distribution
Use SWR for data fetching. Use Tailwind for styling. All charts must be dark-mode compatible."
```

---

### DAY 8 — LangGraph Distress Detection Agent

**Goal:** Working LangGraph agent that analyses mood history and generates personalised nudges.

**Agent graph definition:**
```python
# backend/agents/distress_agent.py
from langgraph.graph import StateGraph, END
from anthropic import Anthropic

# State
class AgentState(TypedDict):
    user_id: str
    mood_history: List[float]
    trajectory: dict
    distress_detected: bool
    nudge_content: str
    nudge_type: str

# Define nodes
def fetch_history(state): ...       # Query TimescaleDB last 7 days
def compute_trajectory(state): ...  # Calculate slope, volatility, Z-score vs baseline
def check_threshold(state): ...     # Compare to threshold rules
def generate_nudge(state): ...      # Call Claude API with user context
def send_nudge(state): ...          # Save to nudges table + send email via Resend

# Define conditional routing
def should_send_nudge(state):
    return "generate_nudge" if state["distress_detected"] else END

# Build graph
workflow = StateGraph(AgentState)
workflow.add_node("fetch_history", fetch_history)
workflow.add_node("compute_trajectory", compute_trajectory)
workflow.add_node("check_threshold", check_threshold)
workflow.add_node("generate_nudge", generate_nudge)
workflow.add_node("send_nudge", send_nudge)
workflow.set_entry_point("fetch_history")
workflow.add_edge("fetch_history", "compute_trajectory")
workflow.add_edge("compute_trajectory", "check_threshold")
workflow.add_conditional_edges("check_threshold", should_send_nudge)
workflow.add_edge("generate_nudge", "send_nudge")
workflow.add_edge("send_nudge", END)

app = workflow.compile()
```

**Claude Code prompt:**
```
"Write the compute_trajectory node for a LangGraph distress detection agent.
Input: mood_history (list of 7 daily fused_scores, most recent last).
Output: {slope: float, volatility: float, three_day_avg: float, z_score: float}
Use numpy for calculations. Slope = linear regression coefficient over the 7 points.
Volatility = standard deviation. Z-score = (mean - baseline) / baseline_std."
```

**APIs needed today:** Anthropic Claude API key (console.anthropic.com → API keys)

---

### DAY 9 — Celery Beat Scheduler + Nudge Delivery

**Goal:** Agent runs automatically every night at 8pm for each user. Emails delivered via Resend.

**Steps:**
1. Configure Celery Beat schedule
2. Create `run_agent_for_all_users` periodic task
3. Set up Resend account (free 3k emails/month) + email template
4. Implement nudge email template (HTML)
5. Implement in-app nudge notification (Next.js toast/banner)

**Claude Code prompt:**
```
"Write a Celery Beat periodic task called run_nightly_agent_check that:
1. Runs daily at 20:00 UTC
2. Queries all user_ids from user_profiles where notification_enabled = TRUE
3. For each user: runs the LangGraph distress agent with that user's data
4. Sends nudge email via Resend API if distress detected
5. Uses a semaphore to limit concurrent agent runs to 5 at a time
Include error handling and logging for each user's processing."
```

**APIs needed today:** Resend API key (resend.com → free plan → API key)

---

### DAY 10 — Feedback Loop + Continual Learning

**Goal:** Users can rate nudges. Ratings update per-user intervention weights in agent_states.

**Steps:**
1. Add thumbs up/down UI to nudge notifications
2. Implement `POST /api/v1/nudges/{id}/rate` endpoint
3. Write `update_intervention_weights` function
4. Create weekly Celery task to recompute weights per user
5. Update `generate_nudge` agent node to use weights when selecting intervention type

**Claude Code prompt:**
```
"Write a function update_intervention_weights(user_id: str, nudge_type: str, rating: int)
that updates the intervention_weights JSONB column in agent_states for a given user.
Use exponential moving average: new_weight = 0.8 * old_weight + 0.2 * rating_value
where rating_value is 1.0 for helpful, 0.0 for not helpful, 0.5 for no response.
Ensure weights are normalised to sum to 1.0 after update."
```

---

### DAY 11 — Weekly PDF Report Generator

**Goal:** Auto-generated weekly PDF report downloadable from the dashboard.

**Steps:**
1. Implement `GET /api/v1/reports/weekly` endpoint
2. Collect report data: mood summary, top 3 journal themes (using gensim LDA), nudge log
3. Use fpdf2 to generate PDF with: header, mood trend summary, emotion table, themes, nudge log
4. Store in R2 with 7-day expiry URL
5. Add "Download Weekly Report" button to dashboard

**Claude Code prompt:**
```
"Write a FastAPI endpoint GET /api/v1/reports/weekly that generates a PDF using fpdf2.
The PDF should have: 1) Header with MoodMap logo text and date range, 2) Week summary
paragraph describing the mood trend in plain language, 3) Table of daily mood scores
with colour coding (red < -0.3, yellow -0.3 to 0.3, green > 0.3), 4) Top 3 journal
themes extracted by LDA using gensim, 5) Nudge history table with ratings,
6) Footer disclaimer. Return as FileResponse."
```

---

### DAY 12 — Testing, Error Handling & Polish

**Goal:** All critical paths tested. UI polished. Edge cases handled.

**Steps:**
1. Write pytest tests for all API endpoints (minimum 80% coverage)
2. Write React component tests with Vitest
3. Add proper loading states and error boundaries in Next.js
4. Add form validation with react-hook-form + zod
5. Handle offline state gracefully (entry drafts saved to localStorage)
6. Accessibility audit (axe-core browser extension)

**Claude Code prompt:**
```
"Write pytest tests for the POST /api/v1/journal endpoint covering: happy path with
text only, happy path with text + audio_key, missing text field returns 422, invalid
JWT returns 401, empty text returns 422, text over 2000 characters returns 422.
Use pytest-asyncio and httpx AsyncClient for testing. Use a test database fixture
that rolls back after each test."
```

---

### DAY 13 — CI/CD Setup & Docker Production Build

**Goal:** GitHub Actions pipeline passing. Production Docker images built.

**Steps:**
1. Create `.github/workflows/main.yml` (see Section 10)
2. Write `Dockerfile` for backend (multi-stage: build + slim runtime)
3. Write `docker-compose.prod.yml` for production
4. Add all required secrets to GitHub repository
5. Push to main → verify pipeline passes
6. Test that Railway deployment works with Docker image

**Backend Dockerfile:**
```dockerfile
# Stage 1: Build
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### DAY 14 — Deploy, Demo & Documentation

**Goal:** Live at public URLs. README and demo video complete.

**Steps:**
1. Deploy frontend to Vercel: `vercel --prod` (or via GitHub Actions)
2. Deploy backend + Redis to Railway (connect GitHub repo → Railway auto-deploys)
3. Set all production environment variables in Railway dashboard
4. Test full end-to-end flow on production
5. Record 3-minute demo video (screen record: sign up → write entry → wait for analysis → view dashboard → receive nudge)
6. Write README.md with: project description, architecture diagram, setup guide, API docs link

**Claude Code prompt:**
```
"Write a comprehensive README.md for MoodMap that includes: project description with
problem statement, architecture overview diagram in ASCII, tech stack badges, local
development setup steps (prerequisites, env setup, docker compose up), HuggingFace
model training instructions, deployment instructions for Vercel + Railway, API
documentation link, and a features section with screenshots placeholder."
```

---

## 12. Deployment Guide

### Frontend (Vercel)
```bash
# One-time setup
npm install -g vercel
vercel login
cd frontend && vercel link  # link to your Vercel project

# Add env vars in Vercel dashboard:
# NEXT_PUBLIC_SUPABASE_URL
# NEXT_PUBLIC_SUPABASE_ANON_KEY
# NEXT_PUBLIC_API_URL=https://your-railway-backend.up.railway.app

# Deploy
vercel --prod
```

### Backend (Railway)
1. Go to railway.app → New Project → Deploy from GitHub repo
2. Select your repo → set root directory to `/backend`
3. Add environment variables in Railway dashboard (all vars from .env)
4. Railway auto-detects Python/Dockerfile → deploys automatically
5. Add Redis service: Railway dashboard → New Service → Redis (one click)
6. Copy Redis URL → set as `REDIS_URL` env var in backend service

### Database (TimescaleDB on Railway)
1. Railway → New Service → PostgreSQL
2. Enable TimescaleDB extension: Railway dashboard → PostgreSQL → Query → `CREATE EXTENSION IF NOT EXISTS timescaledb;`
3. Copy connection string → set as `DATABASE_URL` in backend service
4. Run migrations: `railway run alembic upgrade head`

### ML Models (HuggingFace Hub)
- Models are loaded directly from HuggingFace Hub at startup
- No GPU needed for inference (CPU is fast enough for text, ~2s per entry)
- Voice model only loads if audio entries exist (lazy loading)

---

## 13. Folder Structure

```
moodmap/
├── .github/
│   └── workflows/
│       └── main.yml                  # CI/CD pipeline
│
├── frontend/                          # Next.js 14 App
│   ├── app/
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── signup/page.tsx
│   │   ├── dashboard/
│   │   │   ├── page.tsx              # Main dashboard
│   │   │   └── components/
│   │   │       ├── MoodHeatmap.tsx
│   │   │       ├── MoodTrendChart.tsx
│   │   │       └── EmotionBreakdown.tsx
│   │   ├── journal/
│   │   │   ├── page.tsx              # Journal entry page
│   │   │   └── [id]/page.tsx         # Single entry view
│   │   ├── nudges/page.tsx           # Nudge history + ratings
│   │   └── layout.tsx
│   ├── components/
│   │   ├── ui/                       # Reusable UI components
│   │   ├── JournalEditor.tsx         # TipTap rich text editor
│   │   ├── VoiceRecorder.tsx         # wavesurfer.js recorder
│   │   └── NudgeNotification.tsx     # Proactive nudge banner
│   ├── lib/
│   │   ├── supabase.ts               # Supabase client
│   │   └── api.ts                    # API fetch helpers
│   └── stores/
│       └── userStore.ts              # Zustand user state
│
├── backend/                           # FastAPI Python App
│   ├── main.py                        # App entry point
│   ├── config.py                      # Settings (pydantic-settings)
│   ├── database.py                    # SQLAlchemy async engine
│   ├── celery_app.py                  # Celery + Beat configuration
│   ├── routers/
│   │   ├── journal.py
│   │   ├── insights.py
│   │   ├── nudges.py
│   │   ├── reports.py
│   │   └── user.py
│   ├── models/
│   │   ├── db_models.py              # SQLAlchemy ORM models
│   │   └── schemas.py                # Pydantic request/response schemas
│   ├── services/
│   │   ├── storage.py                # Cloudflare R2 operations
│   │   ├── email.py                  # Resend email service
│   │   └── pdf_generator.py          # fpdf2 report generation
│   ├── ml/
│   │   ├── text_analyzer.py          # RoBERTa inference wrapper
│   │   ├── voice_analyzer.py         # Wav2Vec2 inference wrapper
│   │   └── fusion.py                 # Multimodal fusion
│   ├── agents/
│   │   └── distress_agent.py         # LangGraph agent graph
│   ├── tasks/
│   │   ├── analysis.py               # analyze_entry Celery task
│   │   └── scheduler.py              # Nightly agent Celery Beat task
│   ├── tests/
│   │   ├── conftest.py               # Fixtures
│   │   ├── test_journal.py
│   │   ├── test_insights.py
│   │   └── test_agent.py
│   ├── alembic/                       # DB migrations
│   ├── requirements.txt
│   └── Dockerfile
│
├── ml_training/                       # Colab notebooks (not deployed)
│   ├── 01_train_roberta.ipynb
│   └── 02_train_wav2vec2.ipynb
│
├── docker-compose.dev.yml
├── docker-compose.prod.yml
└── README.md
```

---

## Appendix A: Free Resource Limits

| Service | Free Limit | Notes |
|---------|------------|-------|
| Supabase | 500MB DB, 50k MAU | More than enough for a demo |
| Vercel | 100GB bandwidth, unlimited deploys | Frontend only |
| Railway | $5 free credit (~30 hrs runtime) | Apply for student credits |
| HuggingFace Hub | Unlimited public models | Keep models public |
| Cloudflare R2 | 10GB storage, 1M requests | Audio files only |
| Resend | 3,000 emails/month | Nudge emails only |
| Anthropic API | ~$5 with new account credit | ~5,000 nudge generations |
| Google Colab | 12hr/session T4 GPU | Enough for both models |

## Appendix B: Estimated Costs After Free Tier

If building beyond MVP, estimated monthly costs:
- Railway (backend + Redis): ~$10/month
- Supabase Pro: $25/month
- Anthropic API (1000 users, 1 nudge/week): ~$5/month
- Cloudflare R2 (10GB audio): ~$0.15/month

**Total MVP cost: ~$0 for first demo. ~$40/month at small scale.**

---

*This document was generated for a student developer building MoodMap in 2 weeks using Claude Code. All technology choices prioritise free tiers, developer experience, and the 2-week timeline constraint.*
