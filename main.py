# ============================================================
#  EXAM TRACKER — main.py
#  FastAPI application entry point
#
#  Setup:
#    1. pip install -r requirements.txt
#    2. cp .env.example .env  →  fill in your Supabase values
#    3. python main.py        →  starts on http://localhost:8000
#
#  API docs auto-generated at: http://localhost:8000/docs
# ============================================================

import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

# Route modules
from routes.auth      import router as auth_router
from routes.subjects  import router as subjects_router
from routes.syllabus  import router as syllabus_router
from routes.todos     import router as todos_router
from routes.sessions  import router as sessions_router
from routes.dashboard import router as dashboard_router

load_dotenv()

# ── RATE LIMITER ─────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── APP SETUP ────────────────────────────────────────────────
app = FastAPI(
    title="Exam Tracker API",
    description="Backend REST API for the Exam Tracker website",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ─────────────────────────────────────────────────────
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:5500")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:5500", "http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ── GLOBAL EXCEPTION HANDLER ─────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error.", "detail": str(exc)},
    )

# ── ROUTES ───────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(subjects_router)
app.include_router(syllabus_router)
app.include_router(todos_router)
app.include_router(sessions_router)
app.include_router(dashboard_router)

# ── HEALTH CHECK ─────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health():
    return {
        "success": True,
        "status":  "ok",
        "service": "Exam Tracker API",
        "version": "1.0.0",
    }

# ── ROOT ─────────────────────────────────────────────────────
@app.get("/api", tags=["Info"])
async def api_info():
    return {
        "success": True,
        "service": "Exam Tracker API v1.0",
        "docs":    "/docs",
        "redoc":   "/redoc",
        "health":  "/health",
        "endpoints": {
            "auth": {
                "POST /api/auth/signup":         "Create account",
                "POST /api/auth/login":          "Sign in → returns tokens",
                "POST /api/auth/logout":         "Sign out (auth required)",
                "GET  /api/auth/me":             "Current user (auth required)",
                "POST /api/auth/reset-password": "Send password reset email",
                "POST /api/auth/refresh":        "Refresh access token",
            },
            "subjects": {
                "GET    /api/subjects":           "List all subjects",
                "GET    /api/subjects/{id}":      "Get subject",
                "GET    /api/subjects/{id}/stats":"Subject + completion stats",
                "POST   /api/subjects":           "Create subject",
                "PATCH  /api/subjects/{id}":      "Update subject",
                "DELETE /api/subjects/{id}":      "Delete subject (cascades)",
            },
            "syllabus": {
                "GET    /api/syllabus":                     "List topics (?subject_id, ?status)",
                "GET    /api/syllabus/{id}":                "Get topic",
                "POST   /api/syllabus":                     "Add topic",
                "PATCH  /api/syllabus/{id}":                "Update topic",
                "PATCH  /api/syllabus/{id}/cycle-status":   "pending→in-progress→completed",
                "DELETE /api/syllabus/{id}":                "Delete topic",
                "DELETE /api/syllabus/subject/{subject_id}":"Delete all topics for subject",
            },
            "todos": {
                "GET    /api/todos":               "List tasks (?completed, ?priority)",
                "GET    /api/todos/stats":         "Completion statistics",
                "POST   /api/todos":               "Create task",
                "PATCH  /api/todos/{id}":          "Update task",
                "PATCH  /api/todos/{id}/toggle":   "Toggle completed",
                "DELETE /api/todos/{id}":          "Delete task",
                "DELETE /api/todos/completed/all": "Clear all completed",
            },
            "sessions": {
                "GET    /api/sessions":            "List sessions (?subject_id, ?from, ?to)",
                "GET    /api/sessions/today":      "Today's sessions + total time",
                "GET    /api/sessions/analytics":  "Study analytics (?days=14)",
                "POST   /api/sessions":            "Save session",
                "PATCH  /api/sessions/{id}":       "Update session",
                "DELETE /api/sessions/{id}":       "Delete session",
            },
            "dashboard": {
                "GET /api/dashboard": "All stats in one call",
            },
        },
        "auth_note": "All endpoints except signup, login, reset-password require: Authorization: Bearer <token>",
    }

# ── RUN ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    env  = os.getenv("ENV", "development")

    print("")
    print("  ⬡  Exam Tracker Python API")
    print(f"  ✅  Running on   http://localhost:{port}")
    print(f"  📋  Swagger docs http://localhost:{port}/docs")
    print(f"  📋  ReDoc        http://localhost:{port}/redoc")
    print(f"  💚  Health       http://localhost:{port}/health")
    print(f"  🌍  Environment  {env}")
    print("")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=(env == "development"),
        log_level="info",
    )
