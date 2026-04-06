# routes/subjects.py
# Full CRUD for subjects — all scoped to the authenticated user

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional
from config.supabase import supabase
from middleware.auth import get_current_user

router = APIRouter(prefix="/api/subjects", tags=["Subjects"])


# ── SCHEMAS ──────────────────────────────────────────────────
class SubjectCreate(BaseModel):
    name: str
    code: Optional[str] = None
    exam_date: Optional[str] = None   # format: YYYY-MM-DD
    color: Optional[str] = "#c8f562"

class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    exam_date: Optional[str] = None
    color: Optional[str] = None


# ── GET /api/subjects ─────────────────────────────────────────
@router.get("/")
async def get_subjects(current_user: dict = Depends(get_current_user)):
    try:
        result = (
            supabase.table("subjects")
            .select("*")
            .eq("user_id", current_user["id"])
            .order("created_at")
            .execute()
        )
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /api/subjects/{subject_id} ───────────────────────────
@router.get("/{subject_id}")
async def get_subject(subject_id: str, current_user: dict = Depends(get_current_user)):
    try:
        result = (
            supabase.table("subjects")
            .select("*")
            .eq("id", subject_id)
            .eq("user_id", current_user["id"])
            .maybe_single()
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Subject not found.")
        return {"success": True, "data": result.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /api/subjects/{subject_id}/stats ─────────────────────
@router.get("/{subject_id}/stats")
async def get_subject_stats(subject_id: str, current_user: dict = Depends(get_current_user)):
    try:
        user_id = current_user["id"]

        # Fetch subject
        subject_res = (
            supabase.table("subjects")
            .select("*")
            .eq("id", subject_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if not subject_res.data:
            raise HTTPException(status_code=404, detail="Subject not found.")

        # Syllabus stats
        syllabus_res = (
            supabase.table("syllabus")
            .select("status")
            .eq("subject_id", subject_id)
            .eq("user_id", user_id)
            .execute()
        )

        # Session stats
        sessions_res = (
            supabase.table("sessions")
            .select("duration_seconds")
            .eq("subject_id", subject_id)
            .eq("user_id", user_id)
            .execute()
        )

        topics   = syllabus_res.data or []
        sessions = sessions_res.data or []

        total_topics     = len(topics)
        completed_topics = len([t for t in topics if t["status"] == "completed"])
        in_progress      = len([t for t in topics if t["status"] == "in-progress"])
        total_seconds    = sum(s["duration_seconds"] for s in sessions)

        return {
            "success": True,
            "data": {
                **subject_res.data,
                "stats": {
                    "total_topics":       total_topics,
                    "completed_topics":   completed_topics,
                    "in_progress_topics": in_progress,
                    "completion_pct":     round((completed_topics / total_topics) * 100) if total_topics else 0,
                    "total_study_seconds": total_seconds,
                    "total_study_hours":  round(total_seconds / 3600, 2),
                    "session_count":      len(sessions),
                },
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── POST /api/subjects ────────────────────────────────────────
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_subject(body: SubjectCreate, current_user: dict = Depends(get_current_user)):
    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="Subject name is required.")
    try:
        result = (
            supabase.table("subjects")
            .insert({
                "user_id":   current_user["id"],
                "name":      body.name.strip(),
                "code":      body.code.strip() if body.code else None,
                "exam_date": body.exam_date or None,
                "color":     body.color or "#c8f562",
            })
            .select()
            .single()
            .execute()
        )
        return {"success": True, "message": "Subject created.", "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── PATCH /api/subjects/{subject_id} ─────────────────────────
@router.patch("/{subject_id}")
async def update_subject(subject_id: str, body: SubjectUpdate, current_user: dict = Depends(get_current_user)):
    updates = {}
    if body.name      is not None: updates["name"]      = body.name.strip()
    if body.code      is not None: updates["code"]      = body.code.strip() or None
    if body.exam_date is not None: updates["exam_date"] = body.exam_date or None
    if body.color     is not None: updates["color"]     = body.color

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")

    try:
        result = (
            supabase.table("subjects")
            .update(updates)
            .eq("id", subject_id)
            .eq("user_id", current_user["id"])
            .select()
            .single()
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Subject not found.")
        return {"success": True, "message": "Subject updated.", "data": result.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── DELETE /api/subjects/{subject_id} ────────────────────────
@router.delete("/{subject_id}")
async def delete_subject(subject_id: str, current_user: dict = Depends(get_current_user)):
    try:
        supabase.table("subjects").delete().eq("id", subject_id).eq("user_id", current_user["id"]).execute()
        return {"success": True, "message": "Subject and all related data deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
