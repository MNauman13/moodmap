from fastapi import FastAPI
from backend.routers import user, journal, insights

app = FastAPI(title="MoodMap API")

# Register the user router
app.include_router(user.router)
app.include_router(journal.router)
app.include_router(insights.router)

@app.get("/")
def read_root():
    return {"message": "MoodMap API is running"}