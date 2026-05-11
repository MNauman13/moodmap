# MoodMap

MoodMap is a journaling app that tracks your emotional state over time. Each entry is analysed by a fine-tuned [RoBERTa](https://huggingface.co/FacebookAI/roberta-base) text classifier and an optional voice model ([HuBERT](https://huggingface.co/facebook/hubert-base-ls960)), fused into a single valence score between −1 and +1. A [LangGraph](https://github.com/langchain-ai/langgraph) agent monitors mood trajectory and generates personalised nudges when it detects a sustained or acute downward trend.

The stack is [Next.js](https://nextjs.org/) / [React 19](https://react.dev/) on the frontend, [FastAPI](https://fastapi.tiangolo.com/) on the backend, [Celery](https://docs.celeryq.dev/) + [Redis](https://redis.io/) for background work, [PostgreSQL](https://www.postgresql.org/) via [SQLAlchemy](https://www.sqlalchemy.org/), and [Supabase](https://supabase.com/) for auth.

---

## Interesting Techniques

### Masked multi-label BCE loss for partial-label datasets

The text classifier is trained across three datasets — GoEmotions, dair-ai/emotion, and TweetEval — that cover different subsets of the 9 emotion categories. GoEmotions annotates all 9 per sample. The others cover 6/9 and 4/9 respectively.

Zero-filling the unannotated positions is a mistake: a dair-ai sample labelled "joy" doesn't confirm that the writer felt no optimism, disgust, or neutrality. Those positions simply weren't annotated. Zero-filling injects false negative training signal into every sample from those datasets.

The fix is to use `-1` as a sentinel for unknown positions and mask them out of the loss in [`backend/ml/`](backend/ml/):

```python
mask = (labels != -1).float()
safe_labels = labels.clamp(min=0.0)
per_element_loss = loss_fn(logits, safe_labels)  # reduction="none"
loss = (per_element_loss * mask).sum() / mask.sum().clamp(min=1.0)
```

`BCEWithLogitsLoss` runs with `reduction="none"` to produce per-position losses before masking. The denominator is `mask.sum()` — only the known positions count.

### Symmetrical averaging in the valence formula

A naive valence formula (sum positives − sum negatives) breaks when the two sides have different cardinality. MoodMap has 3 positive categories and 4 negative ones. Summing before subtracting biases every entry toward negative valence even when per-category scores are identical.

The fusion logic in [`backend/ml/fusion.py`](backend/ml/fusion.py) averages each side before subtracting:

```
positive_avg = (joy + love + optimism) / 3
negative_avg = (sadness + anger + fear + disgust) / 4
valence = (positive_avg − negative_avg) × (1 − 0.6 × neutral)
```

The neutral dampening term reduces magnitude when the dominant signal is ambiguous rather than directional.

### Direct-to-R2 audio upload via presigned POST

Voice recordings are uploaded directly from the browser to Cloudflare R2. The FastAPI server generates a presigned POST URL but never touches the audio bytes. This avoids proxying large audio blobs through the API container entirely.

### Dual database drivers for async API and sync Celery

FastAPI is fully async; Celery workers run synchronous tasks. Running asyncpg inside a Celery task would require a separate event loop per task, which is fragile. The project solves this by maintaining two session factories pointed at the same database: asyncpg for the FastAPI async path, psycopg2-binary for the Celery sync path. [`backend/config.py`](backend/config.py) exposes a `sync_database_url` computed property that substitutes the driver prefix.

### Field-level encryption via a custom SQLAlchemy type

Sensitive text fields (journal content, nudge content) use a custom `EncryptedString` SQLAlchemy type defined in [`backend/models/db_models.py`](backend/models/db_models.py). Encryption and decryption are transparent to the ORM — the application reads and writes plain strings; the type descriptor handles Fernet symmetric encryption before the value reaches the database.

### `max_tasks_per_child` to flush PyTorch memory

PyTorch accumulates fragmented memory across inference calls. Rather than patching this in Python, the Celery worker in [`docker-compose.prod.yml`](docker-compose.prod.yml) is configured with `--max-tasks-per-child=50`. After 50 tasks the worker process is recycled and all allocations are flushed. The ML models are lazy-loaded on first use, so the recycled worker pays the load cost once on its first task.

### Next.js font loading with `next/font/google`

Fonts are loaded in [`frontend/app/layout.tsx`](frontend/app/layout.tsx) via `next/font/google` rather than a CSS `@import` or a `<link>` tag. Next.js downloads the font files at build time, self-hosts them alongside the app, and exposes each family as a CSS custom property (`--font-lora`, `--font-dm-sans`). The [`font-display: swap`](https://developer.mozilla.org/en-US/docs/Web/CSS/@font-face/font-display) descriptor keeps text visible during the load.

### Security headers declared in `next.config.ts`

The full [Content Security Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy) is declared in [`frontend/next.config.ts`](frontend/next.config.ts) via the `headers()` API, with precise allowlists for Supabase, Google Fonts, Cloudflare R2, and WebSocket origins. [HSTS](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Strict-Transport-Security) is set to one year with `preload`. The [Permissions-Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Permissions-Policy) header enables `microphone` (required for voice journaling) and explicitly blocks camera, geolocation, and payment APIs.

### MediaRecorder for in-browser audio capture

Voice entries use the [MediaRecorder API](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder) for recording. The captured blob is previewed in wavesurfer.js before submission, then uploaded directly to R2 via a presigned URL — the API server is never in the media path.

---

## Libraries Worth Knowing

**[LangGraph](https://github.com/langchain-ai/langgraph)** — Graph-based agent orchestration from LangChain. The distress agent in [`backend/agents/`](backend/agents/) is a LangGraph state machine. Each node reads `trajectory_slope`, `volatility`, and `days_since_nudge` from a persistent `AgentState` row, then decides whether to queue a nudge or pass. The graph structure makes the branching logic explicit and testable.

**[wavesurfer.js](https://wavesurfer.xyz/)** — Waveform rendering and audio playback. Renders a live waveform during recording in [`frontend/app/journal/`](frontend/app/journal/) and a playback waveform on the journal detail view. The integration surface is a canvas renderer backed by a decoded PCM buffer.

**[Resend](https://resend.com/)** — Transactional email API. Nudge emails and weekly report emails are sent through Resend from [`backend/services/email.py`](backend/services/email.py). Emails are plain HTML with inline styles for Gmail compatibility.

**[librosa](https://librosa.org/)** — Audio analysis library for Python. Loads audio files, resamples them to 16 kHz, and produces the array fed to the HuBERT model in [`backend/ml/voice_analyser.py`](backend/ml/voice_analyser.py).

**[orjson](https://github.com/ijl/orjson)** — A fast JSON serialiser written in Rust. Drop-in compatible with the stdlib `json` module, with native support for numpy arrays and dataclasses. FastAPI uses it automatically when it's present in the environment.

**[SWR](https://swr.vercel.app/)** — React data fetching library that implements the [stale-while-revalidate](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cache-Control) caching strategy. Dashboard and insights panels render immediately with cached data and refresh in the background — no loading spinner on every navigation.

**[Tiptap](https://tiptap.dev/)** — Headless rich text editor built on ProseMirror. The journal editor in [`frontend/app/journal/`](frontend/app/journal/) uses Tiptap with no default UI — the toolbar and input surface are styled entirely in Tailwind.

**[Zustand](https://zustand-demo.pmnd.rs/)** — Minimal React state management. No provider wrappers, no reducers — just a hook that returns a typed store slice from [`frontend/stores/`](frontend/stores/).

**[Framer Motion](https://www.framer.com/motion/)** — React animation library. Used for page transitions, skeleton shimmer loaders, and emotion chart entry animations.

**[Alembic](https://alembic.sqlalchemy.org/)** — SQLAlchemy's migration tool. Each schema change is a versioned upgrade/downgrade Python file in [`backend/alembic/versions/`](backend/alembic/versions/). The migration chain is the source of truth for database structure.

**Fonts: [Lora](https://fonts.google.com/specimen/Lora) and [DM Sans](https://fonts.google.com/specimen/DM+Sans)** — Both loaded via `next/font/google`. Lora (a contemporary serif) is used for editorial headings and journal content. DM Sans (a geometric low-contrast sans) is the UI typeface.

---

## Project Structure

```
MoodMap/
├── backend/
│   ├── agents/
│   ├── alembic/
│   │   └── versions/
│   ├── ml/
│   ├── models/
│   ├── routers/
│   ├── services/
│   ├── tasks/
│   ├── tests/
│   ├── celery_app.py
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── (auth)/
│   │   ├── api/
│   │   │   └── v1/
│   │   ├── dashboard/
│   │   ├── journal/
│   │   └── nudges/
│   ├── components/
│   ├── hooks/
│   ├── lib/
│   ├── public/
│   ├── stores/
│   └── next.config.ts
├── notebooks/
├── scripts/
├── docker-compose.dev.yml
├── docker-compose.prod.yml
└── railway.toml
```

**`backend/agents/`** — LangGraph distress agent. Reads persistent `AgentState` from the database, evaluates mood trajectory metrics, and decides whether to queue a nudge.

**`backend/ml/`** — Inference wrappers for the text (RoBERTa) and voice (HuBERT) emotion models, plus the fusion function that combines their outputs into a single valence score.

**`backend/tasks/`** — Celery task definitions: the entry analysis pipeline, immediate crisis check, nightly agent sweep, and weekly report generation.

**`backend/services/`** — Stateless modules for S3/R2 storage, Resend email, Redis cache, rate limiting, and field encryption.

**`backend/alembic/versions/`** — Versioned database migration history. Each file is an upgrade/downgrade pair.

**`frontend/app/(auth)/`** — Next.js [route group](https://nextjs.org/docs/app/building-your-application/routing/route-groups) for login and signup. The parentheses exclude this segment from the URL path.

**`frontend/app/api/v1/`** — Next.js route handlers that proxy requests to the FastAPI backend, attaching the Supabase JWT from the server-side session.

**`frontend/lib/`** — Typed API client (`api.ts`), Supabase client factory, and server-side session helpers.

**`frontend/stores/`** — Zustand store definitions.

**`notebooks/`** — Jupyter notebooks for model training: the text sentiment analyser (`moodmap_text_sentiment_analyzer.ipynb`) and voice processor (`moodmap_audio_processing.ipynb`).
