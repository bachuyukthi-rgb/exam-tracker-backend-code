# ============================================================
#  EXAM TRACKER — main.py  (single-file version for Render)
#  All routes, middleware, and config in one file.
#  No subfolder imports = no ModuleNotFoundError on Render.
#
#  Setup:
#    pip install -r requirements.txt
#    cp .env.example .env  →  fill in your Supabase values
#    python main.py
#
#  Render start command: uvicorn main:app --host 0.0.0.0 --port 10000
# ============================================================
 
import os
import sys
from datetime import datetime, date, timedelta
from typing import Optional, Literal
 
from dotenv import load_dotenv
load_dotenv()
 
from fastapi import FastAPI, HTTPException, Depends, Request, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from jose import jwt, JWTError, ExpiredSignatureError
from supabase import create_client, Client
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
 
# ── ENV VARS ─────────────────────────────────────────────────
SUPABASE_URL      = os.getenv("SUPABASE_URL", "")
SUPABASE_SVC_KEY  = os.getenv("SUPABASE_SERVICE_KEY", "")
JWT_SECRET        = os.getenv("SUPABASE_JWT_SECRET", "")
FRONTEND_URL      = os.getenv("FRONTEND_URL", "http://127.0.0.1:5500")
PORT              = int(os.getenv("PORT", 8000))
ENV               = os.getenv("ENV", "development")
 
# Validate required env vars on startup
missing = [k for k, v in {
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_SERVICE_KEY": SUPABASE_SVC_KEY,
    "SUPABASE_JWT_SECRET": JWT_SECRET,
}.items() if not v]
 
if missing:
    print(f"❌ Missing env vars: {', '.join(missing)}")
    print("   Add them in your .env file or Render environment settings.")
    sys.exit(1)
 
# ── SUPABASE CLIENT ──────────────────────────────────────────
# Uses Service Role key — bypasses RLS, safe for backend only
db: Client = create_client(SUPABASE_URL, SUPABASE_SVC_KEY)
 
# ── RATE LIMITER ─────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)
 
# ── FASTAPI APP ──────────────────────────────────────────────
app = FastAPI(
    title="Exam Tracker API",
    description="REST API backend for the Exam Tracker website",
    version="1.0.0",
)
 
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
 
# ── CORS ─────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_URL,
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
 
# ── GLOBAL ERROR HANDLER ─────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error.", "detail": str(exc)},
    )
 
# ============================================================
#  AUTH MIDDLEWARE
# ============================================================
bearer_scheme = HTTPBearer()
 
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """Verifies Supabase JWT and returns decoded user dict."""
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing user ID.")
        return {
            "id":    user_id,
            "email": payload.get("email", ""),
            "role":  payload.get("role", "authenticated"),
        }
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired. Please sign in again.")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token.")
 
 
# ============================================================
#  SCHEMAS (Pydantic models)
# ============================================================
 
# Auth
class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = ""
 
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
 
class ResetPasswordRequest(BaseModel):
    email: EmailStr
 
class RefreshRequest(BaseModel):
    refresh_token: str
 
# Subjects
class SubjectCreate(BaseModel):
    name: str
    code: Optional[str] = None
    exam_date: Optional[str] = None
    color: Optional[str] = "#c8f562"
 
class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    exam_date: Optional[str] = None
    color: Optional[str] = None
 
# Syllabus
class SyllabusCreate(BaseModel):
    subject_id: str
    topic: str
    unit: Optional[str] = "General"
    status: Optional[Literal["pending", "in-progress", "completed"]] = "pending"
 
class SyllabusUpdate(BaseModel):
    topic:  Optional[str] = None
    unit:   Optional[str] = None
    status: Optional[Literal["pending", "in-progress", "completed"]] = None
 
# Todos
class TodoCreate(BaseModel):
    task: str
    subject_id: Optional[str] = None
    due_date:   Optional[str] = None
    priority:   Optional[Literal["low", "medium", "high"]] = "medium"
 
class TodoUpdate(BaseModel):
    task:       Optional[str] = None
    subject_id: Optional[str] = None
    due_date:   Optional[str] = None
    priority:   Optional[Literal["low", "medium", "high"]] = None
    completed:  Optional[bool] = None
 
# Sessions
class SessionCreate(BaseModel):
    subject_id:       Optional[str] = None
    note:             Optional[str] = None
    started_at:       str
    ended_at:         Optional[str] = None
    duration_seconds: int
 
class SessionUpdate(BaseModel):
    note:             Optional[str] = None
    duration_seconds: Optional[int] = None
 
 
# ============================================================
#  HEALTH & INFO
# ============================================================
 
@app.get("/health", tags=["Health"])
async def health():
    return {"success": True, "status": "ok", "service": "Exam Tracker API", "version": "1.0.0"}
 
@app.get("/api", tags=["Info"])
async def api_info():
    return {
        "success": True,
        "service": "Exam Tracker API v1.0",
        "docs":    "/docs",
        "endpoints": {
            "auth":      ["POST /api/auth/signup", "POST /api/auth/login", "POST /api/auth/logout", "GET /api/auth/me", "POST /api/auth/reset-password", "POST /api/auth/refresh"],
            "subjects":  ["GET/POST /api/subjects", "GET/PATCH/DELETE /api/subjects/{id}", "GET /api/subjects/{id}/stats"],
            "syllabus":  ["GET/POST /api/syllabus", "GET/PATCH/DELETE /api/syllabus/{id}", "PATCH /api/syllabus/{id}/cycle-status"],
            "todos":     ["GET/POST /api/todos", "GET/PATCH/DELETE /api/todos/{id}", "PATCH /api/todos/{id}/toggle", "GET /api/todos/stats", "DELETE /api/todos/completed/all"],
            "sessions":  ["GET/POST /api/sessions", "GET/PATCH/DELETE /api/sessions/{id}", "GET /api/sessions/today", "GET /api/sessions/analytics"],
            "dashboard": ["GET /api/dashboard"],
        },
    }
 
 
# ============================================================
#  AUTH ROUTES
# ============================================================
 
@app.post("/api/auth/signup", tags=["Auth"], status_code=201)
async def signup(body: SignupRequest):
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    try:
        result = db.auth.admin.create_user({
            "email":         body.email,
            "password":      body.password,
            "user_metadata": {"full_name": body.full_name or ""},
            "email_confirm": False,
        })
        u = result.user
        return {
            "success": True,
            "message": "Account created successfully.",
            "user": {"id": u.id, "email": u.email, "name": (u.user_metadata or {}).get("full_name", "")},
        }
    except Exception as e:
        msg = str(e)
        if "already registered" in msg.lower():
            raise HTTPException(status_code=400, detail="This email is already registered.")
        raise HTTPException(status_code=400, detail=msg)
 
 
@app.post("/api/auth/login", tags=["Auth"])
async def login(body: LoginRequest):
    try:
        result  = db.auth.sign_in_with_password({"email": body.email, "password": body.password})
        session = result.session
        user    = result.user
        if not session:
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        return {
            "success":       True,
            "message":       "Login successful.",
            "access_token":  session.access_token,
            "refresh_token": session.refresh_token,
            "expires_at":    session.expires_at,
            "user": {"id": user.id, "email": user.email, "name": (user.user_metadata or {}).get("full_name", "")},
        }
    except HTTPException:
        raise
    except Exception as e:
        msg = str(e)
        if "invalid" in msg.lower():
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        raise HTTPException(status_code=400, detail=msg)
 
 
@app.post("/api/auth/logout", tags=["Auth"])
async def logout(current_user: dict = Depends(get_current_user)):
    try:
        db.auth.admin.sign_out(current_user["id"])
        return {"success": True, "message": "Logged out successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
 
 
@app.get("/api/auth/me", tags=["Auth"])
async def get_me(current_user: dict = Depends(get_current_user)):
    try:
        result = db.auth.admin.get_user_by_id(current_user["id"])
        u = result.user
        if not u:
            raise HTTPException(status_code=404, detail="User not found.")
        return {
            "success": True,
            "user": {
                "id":           u.id,
                "email":        u.email,
                "name":         (u.user_metadata or {}).get("full_name", ""),
                "created_at":   str(u.created_at),
                "last_sign_in": str(u.last_sign_in_at),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
 
 
@app.post("/api/auth/reset-password", tags=["Auth"])
async def reset_password(body: ResetPasswordRequest):
    try:
        db.auth.reset_password_email(body.email, options={"redirect_to": f"{FRONTEND_URL}/reset"})
    except Exception:
        pass
    return {"success": True, "message": "If that email exists, a reset link has been sent."}
 
 
@app.post("/api/auth/refresh", tags=["Auth"])
async def refresh_token(body: RefreshRequest):
    try:
        result  = db.auth.refresh_session(body.refresh_token)
        session = result.session
        if not session:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")
        return {"success": True, "access_token": session.access_token, "refresh_token": session.refresh_token, "expires_at": session.expires_at}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
 
 
# ============================================================
#  SUBJECTS ROUTES
# ============================================================
 
@app.get("/api/subjects", tags=["Subjects"])
async def get_subjects(current_user: dict = Depends(get_current_user)):
    try:
        result = db.table("subjects").select("*").eq("user_id", current_user["id"]).order("created_at").execute()
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.get("/api/subjects/{subject_id}/stats", tags=["Subjects"])
async def get_subject_stats(subject_id: str, current_user: dict = Depends(get_current_user)):
    try:
        uid = current_user["id"]
        sub = db.table("subjects").select("*").eq("id", subject_id).eq("user_id", uid).maybe_single().execute()
        if not sub.data:
            raise HTTPException(status_code=404, detail="Subject not found.")
        topics   = db.table("syllabus").select("status").eq("subject_id", subject_id).eq("user_id", uid).execute().data or []
        sessions = db.table("sessions").select("duration_seconds").eq("subject_id", subject_id).eq("user_id", uid).execute().data or []
        total    = len(topics)
        done     = len([t for t in topics if t["status"] == "completed"])
        secs     = sum(s["duration_seconds"] for s in sessions)
        return {
            "success": True,
            "data": {
                **sub.data,
                "stats": {
                    "total_topics": total, "completed_topics": done,
                    "in_progress_topics": len([t for t in topics if t["status"] == "in-progress"]),
                    "completion_pct": round((done / total) * 100) if total else 0,
                    "total_study_seconds": secs, "total_study_hours": round(secs / 3600, 2),
                    "session_count": len(sessions),
                },
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.get("/api/subjects/{subject_id}", tags=["Subjects"])
async def get_subject(subject_id: str, current_user: dict = Depends(get_current_user)):
    try:
        result = db.table("subjects").select("*").eq("id", subject_id).eq("user_id", current_user["id"]).maybe_single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Subject not found.")
        return {"success": True, "data": result.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.post("/api/subjects", tags=["Subjects"], status_code=201)
async def create_subject(body: SubjectCreate, current_user: dict = Depends(get_current_user)):
    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="Subject name is required.")
    try:
        result = db.table("subjects").insert({
            "user_id": current_user["id"], "name": body.name.strip(),
            "code": body.code.strip() if body.code else None,
            "exam_date": body.exam_date or None, "color": body.color or "#c8f562",
        }).select().single().execute()
        return {"success": True, "message": "Subject created.", "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.patch("/api/subjects/{subject_id}", tags=["Subjects"])
async def update_subject(subject_id: str, body: SubjectUpdate, current_user: dict = Depends(get_current_user)):
    updates = {}
    if body.name      is not None: updates["name"]      = body.name.strip()
    if body.code      is not None: updates["code"]      = body.code.strip() or None
    if body.exam_date is not None: updates["exam_date"] = body.exam_date or None
    if body.color     is not None: updates["color"]     = body.color
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")
    try:
        result = db.table("subjects").update(updates).eq("id", subject_id).eq("user_id", current_user["id"]).select().single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Subject not found.")
        return {"success": True, "message": "Subject updated.", "data": result.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.delete("/api/subjects/{subject_id}", tags=["Subjects"])
async def delete_subject(subject_id: str, current_user: dict = Depends(get_current_user)):
    try:
        db.table("subjects").delete().eq("id", subject_id).eq("user_id", current_user["id"]).execute()
        return {"success": True, "message": "Subject and all related data deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
# ============================================================
#  SYLLABUS ROUTES
# ============================================================
CYCLE = {"pending": "in-progress", "in-progress": "completed", "completed": "pending"}
 
@app.get("/api/syllabus", tags=["Syllabus"])
async def get_syllabus(
    subject_id: Optional[str] = Query(None),
    status:     Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    try:
        q = db.table("syllabus").select("*, subjects(name, color)").eq("user_id", current_user["id"]).order("created_at")
        if subject_id: q = q.eq("subject_id", subject_id)
        if status and status in ["pending", "in-progress", "completed"]: q = q.eq("status", status)
        result = q.execute()
        return {"success": True, "count": len(result.data), "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.get("/api/syllabus/{topic_id}", tags=["Syllabus"])
async def get_topic(topic_id: str, current_user: dict = Depends(get_current_user)):
    try:
        result = db.table("syllabus").select("*, subjects(name, color)").eq("id", topic_id).eq("user_id", current_user["id"]).maybe_single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Topic not found.")
        return {"success": True, "data": result.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.post("/api/syllabus", tags=["Syllabus"], status_code=201)
async def create_topic(body: SyllabusCreate, current_user: dict = Depends(get_current_user)):
    if not body.topic or not body.topic.strip():
        raise HTTPException(status_code=400, detail="Topic name is required.")
    sub = db.table("subjects").select("id").eq("id", body.subject_id).eq("user_id", current_user["id"]).maybe_single().execute()
    if not sub.data:
        raise HTTPException(status_code=404, detail="Subject not found.")
    try:
        result = db.table("syllabus").insert({
            "user_id": current_user["id"], "subject_id": body.subject_id,
            "topic": body.topic.strip(), "unit": body.unit or "General", "status": body.status or "pending",
        }).select().single().execute()
        return {"success": True, "message": "Topic added.", "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.patch("/api/syllabus/{topic_id}/cycle-status", tags=["Syllabus"])
async def cycle_status(topic_id: str, current_user: dict = Depends(get_current_user)):
    try:
        existing = db.table("syllabus").select("status").eq("id", topic_id).eq("user_id", current_user["id"]).maybe_single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Topic not found.")
        next_s = CYCLE[existing.data["status"]]
        result = db.table("syllabus").update({"status": next_s}).eq("id", topic_id).eq("user_id", current_user["id"]).select().single().execute()
        return {"success": True, "message": f'Status → "{next_s}".', "data": result.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.patch("/api/syllabus/{topic_id}", tags=["Syllabus"])
async def update_topic(topic_id: str, body: SyllabusUpdate, current_user: dict = Depends(get_current_user)):
    updates = {}
    if body.topic  is not None: updates["topic"]  = body.topic.strip()
    if body.unit   is not None: updates["unit"]   = body.unit.strip() or "General"
    if body.status is not None: updates["status"] = body.status
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")
    try:
        result = db.table("syllabus").update(updates).eq("id", topic_id).eq("user_id", current_user["id"]).select().single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Topic not found.")
        return {"success": True, "message": "Topic updated.", "data": result.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.delete("/api/syllabus/{topic_id}", tags=["Syllabus"])
async def delete_topic(topic_id: str, current_user: dict = Depends(get_current_user)):
    try:
        db.table("syllabus").delete().eq("id", topic_id).eq("user_id", current_user["id"]).execute()
        return {"success": True, "message": "Topic deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
# ============================================================
#  TODOS ROUTES
# ============================================================
 
@app.get("/api/todos/stats", tags=["Todos"])
async def get_todo_stats(current_user: dict = Depends(get_current_user)):
    try:
        todos = db.table("todos").select("priority, completed").eq("user_id", current_user["id"]).execute().data or []
        total = len(todos)
        done  = len([t for t in todos if t["completed"]])
        by_p  = {p: {"total": 0, "done": 0} for p in ["low", "medium", "high"]}
        for t in todos:
            by_p[t["priority"]]["total"] += 1
            if t["completed"]: by_p[t["priority"]]["done"] += 1
        return {"success": True, "data": {"total": total, "completed": done, "pending": total - done, "completion_pct": round((done / total) * 100) if total else 0, "by_priority": by_p}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.get("/api/todos/completed/all", tags=["Todos"])
async def placeholder(): pass  # keeps route ordering for DELETE below
 
 
@app.get("/api/todos", tags=["Todos"])
async def get_todos(
    subject_id: Optional[str]  = Query(None),
    completed:  Optional[bool] = Query(None),
    priority:   Optional[str]  = Query(None),
    current_user: dict = Depends(get_current_user),
):
    try:
        q = db.table("todos").select("*, subjects(name, color)").eq("user_id", current_user["id"]).order("created_at")
        if subject_id is not None: q = q.eq("subject_id", subject_id)
        if completed  is not None: q = q.eq("completed",  completed)
        if priority and priority in ["low","medium","high"]: q = q.eq("priority", priority)
        result = q.execute()
        return {"success": True, "count": len(result.data), "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.get("/api/todos/{todo_id}", tags=["Todos"])
async def get_todo(todo_id: str, current_user: dict = Depends(get_current_user)):
    try:
        result = db.table("todos").select("*, subjects(name, color)").eq("id", todo_id).eq("user_id", current_user["id"]).maybe_single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Task not found.")
        return {"success": True, "data": result.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.post("/api/todos", tags=["Todos"], status_code=201)
async def create_todo(body: TodoCreate, current_user: dict = Depends(get_current_user)):
    if not body.task or not body.task.strip():
        raise HTTPException(status_code=400, detail="Task description is required.")
    try:
        result = db.table("todos").insert({
            "user_id": current_user["id"], "task": body.task.strip(),
            "subject_id": body.subject_id or None, "due_date": body.due_date or None,
            "priority": body.priority or "medium", "completed": False,
        }).select().single().execute()
        return {"success": True, "message": "Task created.", "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.patch("/api/todos/{todo_id}/toggle", tags=["Todos"])
async def toggle_todo(todo_id: str, current_user: dict = Depends(get_current_user)):
    try:
        existing = db.table("todos").select("completed").eq("id", todo_id).eq("user_id", current_user["id"]).maybe_single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Task not found.")
        new_val = not existing.data["completed"]
        result  = db.table("todos").update({"completed": new_val}).eq("id", todo_id).eq("user_id", current_user["id"]).select().single().execute()
        return {"success": True, "message": f"Task marked as {'completed' if new_val else 'pending'}.", "data": result.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.patch("/api/todos/{todo_id}", tags=["Todos"])
async def update_todo(todo_id: str, body: TodoUpdate, current_user: dict = Depends(get_current_user)):
    updates = {}
    if body.task       is not None: updates["task"]       = body.task.strip()
    if body.subject_id is not None: updates["subject_id"] = body.subject_id or None
    if body.due_date   is not None: updates["due_date"]   = body.due_date   or None
    if body.priority   is not None: updates["priority"]   = body.priority
    if body.completed  is not None: updates["completed"]  = body.completed
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")
    try:
        result = db.table("todos").update(updates).eq("id", todo_id).eq("user_id", current_user["id"]).select().single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Task not found.")
        return {"success": True, "message": "Task updated.", "data": result.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.delete("/api/todos/completed/all", tags=["Todos"])
async def clear_completed(current_user: dict = Depends(get_current_user)):
    try:
        result = db.table("todos").delete().eq("user_id", current_user["id"]).eq("completed", True).execute()
        count  = len(result.data) if result.data else 0
        return {"success": True, "message": f"{count} completed tasks deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.delete("/api/todos/{todo_id}", tags=["Todos"])
async def delete_todo(todo_id: str, current_user: dict = Depends(get_current_user)):
    try:
        db.table("todos").delete().eq("id", todo_id).eq("user_id", current_user["id"]).execute()
        return {"success": True, "message": "Task deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
# ============================================================
#  SESSIONS ROUTES
# ============================================================
 
@app.get("/api/sessions/today", tags=["Sessions"])
async def get_today_sessions(current_user: dict = Depends(get_current_user)):
    try:
        today   = date.today().isoformat()
        result  = db.table("sessions").select("*, subjects(name, color)").eq("user_id", current_user["id"]).gte("started_at", today + "T00:00:00").lte("started_at", today + "T23:59:59").order("started_at", desc=True).execute()
        sessions = result.data or []
        total    = sum(s["duration_seconds"] for s in sessions)
        return {"success": True, "count": len(sessions), "total_seconds": total, "total_hours": round(total / 3600, 2), "data": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.get("/api/sessions/analytics", tags=["Sessions"])
async def get_analytics(days: int = Query(14, le=90), current_user: dict = Depends(get_current_user)):
    try:
        from_date = (date.today() - timedelta(days=days - 1)).isoformat()
        sessions  = db.table("sessions").select("*, subjects(name, color)").eq("user_id", current_user["id"]).gte("started_at", from_date).order("started_at").execute().data or []
 
        daily_map: dict = {}
        for i in range(days):
            d = (date.today() - timedelta(days=days - 1 - i)).isoformat()
            daily_map[d] = {"date": d, "sessions": 0, "seconds": 0}
 
        subject_map: dict = {}
        for s in sessions:
            day = s["started_at"][:10]
            if day in daily_map:
                daily_map[day]["sessions"] += 1
                daily_map[day]["seconds"]  += s["duration_seconds"]
            sid = s["subject_id"] or "no_subject"
            if sid not in subject_map:
                sub_info = s.get("subjects") or {}
                subject_map[sid] = {"subject_id": s["subject_id"], "subject_name": sub_info.get("name", "No Subject"), "color": sub_info.get("color", "#555"), "sessions": 0, "seconds": 0}
            subject_map[sid]["sessions"] += 1
            subject_map[sid]["seconds"]  += s["duration_seconds"]
 
        total = sum(s["duration_seconds"] for s in sessions)
        return {
            "success": True,
            "data": {
                "period_days": days, "total_sessions": len(sessions),
                "total_seconds": total, "total_hours": round(total / 3600, 2),
                "unique_study_days": sum(1 for d in daily_map.values() if d["seconds"] > 0),
                "avg_session_seconds": round(total / len(sessions)) if sessions else 0,
                "daily_breakdown": list(daily_map.values()),
                "by_subject": sorted(subject_map.values(), key=lambda x: x["seconds"], reverse=True),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.get("/api/sessions", tags=["Sessions"])
async def get_sessions(
    subject_id: Optional[str] = Query(None),
    from_date:  Optional[str] = Query(None, alias="from"),
    to_date:    Optional[str] = Query(None, alias="to"),
    limit:      int           = Query(100, le=500),
    current_user: dict = Depends(get_current_user),
):
    try:
        q = db.table("sessions").select("*, subjects(name, color)").eq("user_id", current_user["id"]).order("started_at", desc=True).limit(limit)
        if subject_id: q = q.eq("subject_id", subject_id)
        if from_date:  q = q.gte("started_at", from_date)
        if to_date:    q = q.lte("started_at", to_date + "T23:59:59")
        result = q.execute()
        return {"success": True, "count": len(result.data), "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.get("/api/sessions/{session_id}", tags=["Sessions"])
async def get_session(session_id: str, current_user: dict = Depends(get_current_user)):
    try:
        result = db.table("sessions").select("*, subjects(name, color)").eq("id", session_id).eq("user_id", current_user["id"]).maybe_single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Session not found.")
        return {"success": True, "data": result.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.post("/api/sessions", tags=["Sessions"], status_code=201)
async def create_session(body: SessionCreate, current_user: dict = Depends(get_current_user)):
    if body.duration_seconds < 1:
        raise HTTPException(status_code=400, detail="duration_seconds must be at least 1.")
    try:
        result = db.table("sessions").insert({
            "user_id": current_user["id"], "subject_id": body.subject_id or None,
            "note": body.note.strip() if body.note else None,
            "started_at": body.started_at, "ended_at": body.ended_at or datetime.utcnow().isoformat(),
            "duration_seconds": body.duration_seconds,
        }).select().single().execute()
        return {"success": True, "message": "Session saved.", "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.patch("/api/sessions/{session_id}", tags=["Sessions"])
async def update_session(session_id: str, body: SessionUpdate, current_user: dict = Depends(get_current_user)):
    updates = {}
    if body.note             is not None: updates["note"]             = body.note.strip() or None
    if body.duration_seconds is not None: updates["duration_seconds"] = body.duration_seconds
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")
    try:
        result = db.table("sessions").update(updates).eq("id", session_id).eq("user_id", current_user["id"]).select().single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Session not found.")
        return {"success": True, "message": "Session updated.", "data": result.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.delete("/api/sessions/{session_id}", tags=["Sessions"])
async def delete_session(session_id: str, current_user: dict = Depends(get_current_user)):
    try:
        db.table("sessions").delete().eq("id", session_id).eq("user_id", current_user["id"]).execute()
        return {"success": True, "message": "Session deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
# ============================================================
#  DASHBOARD ROUTE
# ============================================================
 
@app.get("/api/dashboard", tags=["Dashboard"])
async def get_dashboard(current_user: dict = Depends(get_current_user)):
    try:
        uid   = current_user["id"]
        today = date.today().isoformat()
 
        subjects = db.table("subjects").select("*").eq("user_id", uid).execute().data or []
        syllabus = db.table("syllabus").select("status").eq("user_id", uid).execute().data or []
        todos    = db.table("todos").select("completed, priority").eq("user_id", uid).execute().data or []
        sessions = db.table("sessions").select("duration_seconds, subject_id").eq("user_id", uid).execute().data or []
        today_s  = db.table("sessions").select("duration_seconds, subject_id, note, started_at, subjects(name, color)").eq("user_id", uid).gte("started_at", today + "T00:00:00").lte("started_at", today + "T23:59:59").order("started_at", desc=True).execute().data or []
 
        total_secs  = sum(s["duration_seconds"] for s in sessions)
        today_secs  = sum(s["duration_seconds"] for s in today_s)
        syl_done    = len([t for t in syllabus if t["status"] == "completed"])
        syl_prog    = len([t for t in syllabus if t["status"] == "in-progress"])
        td_done     = len([t for t in todos if t["completed"]])
        td_high_pen = len([t for t in todos if not t["completed"] and t["priority"] == "high"])
 
        sub_hours: dict = {}
        for s in sessions:
            if s["subject_id"]:
                sub_hours[s["subject_id"]] = sub_hours.get(s["subject_id"], 0) + s["duration_seconds"]
 
        return {
            "success": True,
            "data": {
                "summary": {
                    "total_subjects":        len(subjects),
                    "total_sessions":        len(sessions),
                    "total_study_seconds":   total_secs,
                    "total_study_hours":     round(total_secs / 3600, 2),
                    "today_study_seconds":   today_secs,
                    "today_study_hours":     round(today_secs / 3600, 2),
                    "syllabus_total":        len(syllabus),
                    "syllabus_completed":    syl_done,
                    "syllabus_in_progress":  syl_prog,
                    "syllabus_pct":          round((syl_done / len(syllabus)) * 100) if syllabus else 0,
                    "todos_total":           len(todos),
                    "todos_done":            td_done,
                    "todos_pending_high":    td_high_pen,
                },
                "today_sessions": today_s,
                "subject_hours": [
                    {"id": s["id"], "name": s["name"], "color": s["color"], "exam_date": s.get("exam_date"),
                     "study_seconds": sub_hours.get(s["id"], 0),
                     "study_hours":   round(sub_hours.get(s["id"], 0) / 3600, 2)}
                    for s in subjects
                ],
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
# ============================================================
#  ENTRY POINT
# ============================================================
if __name__ == "__main__":
    import uvicorn
    print(f"\n  ⬡  Exam Tracker Python API")
    print(f"  ✅  http://localhost:{PORT}")
    print(f"  📋  Docs: http://localhost:{PORT}/docs\n")
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=(ENV == "development"))
