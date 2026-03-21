from fastapi import FastAPI
from .routes import router

app = FastAPI(title="GoldenEye Analytics", version="0.1.0")

app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "analytics"}
