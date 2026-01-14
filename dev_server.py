import uvicorn
# import os
# from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles

from api import app

# Enhanced CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "http://localhost:5500",  # Live Server default
        "http://127.0.0.1:5500",
        "*"  # Remove in production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optional: Serve static files during development
# app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    print("🚀 Starting FastAPI development server...")
    print("📡 API will be available at: http://localhost:8000")
    print("📖 Docs available at: http://localhost:8000/docs")
    print("🌐 CORS enabled for local frontend development")

    uvicorn.run(
        "dev_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes
        log_level="info"
    )
