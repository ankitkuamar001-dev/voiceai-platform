import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

def setup_cors(app: FastAPI) -> None:
    cors_origins_env = os.getenv("CORS_ORIGINS", "")
    if cors_origins_env:
        origins = [origin.strip() for origin in cors_origins_env.split(",")]
    else:
        # Default to nothing or local development origins if not set
        origins = [
            "http://localhost:3000",
            "http://localhost:8000"
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
