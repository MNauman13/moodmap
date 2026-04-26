import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import validate_env, CORS_ORIGINS
from backend.routers import user, journal, insights, nudges, reports, dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

validate_env()

app = FastAPI(title="MoodMap API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user.router)
app.include_router(journal.router)
app.include_router(insights.router)
app.include_router(nudges.router)
app.include_router(reports.router)
app.include_router(dashboard.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def read_root():
    return {"message": "MoodMap API is running"}