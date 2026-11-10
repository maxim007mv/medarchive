from fastapi import FastAPI

# Swagger UI and ReDoc load scripts from external CDNs, which AGENTS.md forbids.
app = FastAPI(title="Медархив API", docs_url=None, redoc_url=None)


@app.get("/healthz", operation_id="health.live", tags=["health"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
