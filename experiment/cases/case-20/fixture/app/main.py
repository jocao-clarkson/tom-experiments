from fastapi import FastAPI

from app.api import workouts

app = FastAPI(title="pacer-api")
app.include_router(workouts.router)


@app.get("/healthz")
async def healthz():
    return {"ok": True}
