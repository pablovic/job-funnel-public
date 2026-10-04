from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import analytics, applications, opportunities

app = FastAPI(title="Job Funnel", version="0.1.0",
              description="Personal opportunity funnel: ingest, filter, score, decide, apply, measure.")

app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"],
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(opportunities.router)
app.include_router(applications.router)
app.include_router(analytics.router)


@app.get("/health")
def health():
    return {"ok": True}
