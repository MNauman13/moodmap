from fastapi import FastAPI
from routers import user

app = FastAPI(title="MoodMap API")

# Register the user router
app.include_router(user.router)

@app.get("/")
def read_root():
    return {"message": "MoodMap API is running"}