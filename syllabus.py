# routes/syllabus.py
# Full CRUD for syllabus topics — all scoped to the authenticated user

from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel
from typing import Optional, Literal
from config.supabase import supabase
from middleware.auth import get_current_user

router = APIRouter(prefix="/api/syllabus", tags=["Syllabus"])

VALID_STATUSES = ["pending", "in-progress", "completed"]
CYCLE_STATUS   = {"pending": "in-progress", "in-progress": "completed", "completed": "pending"}


# ── SCHEMAS ──────────────────────────────────────────────────
class SyllabusCreate(BaseModel):
    subject_id: str
    topic: str
    unit: Optional[str] = "General"
    status: Optional[Literal["pending", "in-progress", "completed"]] = "pending"

class SyllabusUpdate(BaseModel):
    topic:  Optional[str] = None
    unit:   Optional[str] = None
    status: Optional[Literal["pending", "in-progress", "completed"]] = None


# ── GET /api/syllabus ─────────────────────────────────────────
@router.get("/")
async def get_syllabus(
    subject_id: Optional[str] = Query(None),
    status:     Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    try:
        query = (
            supabase.table("syllabus")
            .select("*, subjects(name, color)")
            .eq("user_id", current_user["id"])
            .order("created_at")
        )
        if subject_id: query = query.eq("subject_id", subject_id)
        if status and status in VALID_STATUSES: query = query.eq("status", status)

        result = query.execute()
        return {"success": True, "count": len(result.data), "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /api/syllabus/{topic_id} ──────────────────────────────
@router.get("/{topic_id}")
async def get_topic(topic_id: str, current_user: dict = Depends(get_current_user)):
    try:
        result = (
            supabase.table("syllabus")
            .select("*, subjects(name, color)")
            .eq("id", topic_id)
            .eq("user_id", current_user["id"])
            .maybe_single()
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Topic not found.")
        return {"success": True, "data": result.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── POST /api/syllabus ────────────────────────────────────────
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_topic(body: SyllabusCreate, current_user: dict = Depends(get_current_user)):
    if not body.topic or not body.topic.strip():
        raise HTTPException(status_code=400, detail="Topic name is required.")

    # Verify subject belongs to this user
    subject_res = (
        supabase.table("subjects")
        .select("id")
        .eq("id", body.subject_id)
        .eq("user_id", current_user["id"])
        .maybe_single()
        .execute()
    )
    if not subject_res.data:
        raise HTTPException(status_code=404, detail="Subject not found.")

    try:
        result = (
            supabase.table("syllabus")
            .insert({
                "user_id":    current_user["id"],
                "subject_id": body.subject_id,
                "topic":      body.topic.strip(),
                "unit":       body.unit.strip() if body.unit else "General",
                "status":     body.status or "pending",
            })
            .select()
            .single()
            .execute()
        )
        return {"success": True, "message": "Topic added.", "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── PATCH /api/syllabus/{topic_id} ───────────────────────────
@router.patch("/{topic_id}")
async def update_topic(topic_id: str, body: SyllabusUpdate, current_user: dict = Depends(get_current_user)):
    updates = {}
    if body.topic  is not None: updates["topic"]  = body.topic.strip()
    if body.unit   is not None: updates["unit"]   = body.unit.strip() or "General"
    if body.status is not None: updates["status"] = body.status

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")

    try:
        result = (
            supabase.table("syllabus")
            .update(updates)
            .eq("id", topic_id)
            .eq("user_id", current_user["id"])
            .select()
            .single()
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Topic not found.")
        return {"success": True, "message": "Topic updated.", "data": result.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── PATCH /api/syllabus/{topic_id}/cycle-status ──────────────
@router.patch("/{topic_id}/cycle-status")
async def cycle_status(topic_id: str, current_user: dict = Depends(get_current_user)):
    try:
        existing = (
            supabase.table("syllabus")
            .select("status")
            .eq("id", topic_id)
            .eq("user_id", current_user["id"])
            .maybe_single()
            .execute()
        )
        if not existing.data:
            raise HTTPException(status_code=404, detail="Topic not found.")

        next_status = CYCLE_STATUS[existing.data["status"]]

        result = (
            supabase.table("syllabus")
            .update({"status": next_status})
            .eq("id", topic_id)
            .eq("user_id", current_user["id"])
            .select()
            .single()
            .execute()
        )
        return {"success": True, "message": f'Status updated to "{next_status}".', "data": result.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── DELETE /api/syllabus/{topic_id} ──────────────────────────
@router.delete("/{topic_id}")
async def delete_topic(topic_id: str, current_user: dict = Depends(get_current_user)):
    try:
        supabase.table("syllabus").delete().eq("id", topic_id).eq("user_id", current_user["id"]).execute()
        return {"success": True, "message": "Topic deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── DELETE /api/syllabus/subject/{subject_id} ────────────────
@router.delete("/subject/{subject_id}")
async def delete_by_subject(subject_id: str, current_user: dict = Depends(get_current_user)):
    try:
        result = (
            supabase.table("syllabus")
            .delete()
            .eq("subject_id", subject_id)
            .eq("user_id", current_user["id"])
            .execute()
        )
        count = len(result.data) if result.data else 0
        return {"success": True, "message": f"{count} topics deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
