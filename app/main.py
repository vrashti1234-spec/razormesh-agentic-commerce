from fastapi import FastAPI

app = FastAPI(
    title="RazorMesh",
    description="Agentic Commerce Trust & Payment Layer",
    version="0.1.0",
)


@app.get("/")
async def root():
    return {
        "name": "RazorMesh",
        "description": "Agentic Commerce Trust & Payment Layer — Razorpay AI Buildathon 2026",
        "version": "0.1.0",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
