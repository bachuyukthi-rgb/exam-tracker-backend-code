# routes/sessions.py
# Full CRUD + analytics for study sessions — all scoped to the authenticated user

from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date, timedelta
from config.supabase import supabase
from middleware.auth import get_current_user

router = APIRouter(prefix="/api/sessions", tags=["Sessions"])


# ── SCHEMAS ──────────────────────────────────────────────────
class SessionCreate(BaseModel):
    subject_id:       Optional[str] = None
    note:             Optional[str] = None
    started_at:       str            # ISO datetime string
    ended_at:         Optional[str] = None
    duration_seconds: int

class SessionUpdate(BaseModel):
    note:             Optional[str] = None
    duration_seconds: Optional[int] = None


# ── GET /api/sessions ─────────────────────────────────────────
@router.get("/")
async def get_sessions(
    subject_id: Optional[str] = Query(None),
    from_date:  Optional[str] = Query(None, alias="from"),
    to_date:    Optional[str] = Query(None, alias="to"),
    limit:      int           = Query(100, le=500),
    current_user: dict = Depends(get_current_user),
):
    try:
        query = (
            supabase.table("sessions")
            .select("*, subjects(name, color)")
            .eq("user_id", current_user["id"])
            .order("started_at", desc=True)
            .limit(limit)
        )
        if subject_id: query = query.eq("subject_id", subject_id)
        if from_date:  query = query.gte("started_at", from_date)
        if to_date:    query = query.lte("started_at", to_date + "T23:59:59")

        result = query.execute()
        return {"success": True, "count": len(result.data), "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /api/sessions/today ───────────────────────────────────
@router.get("/today")
async def get_today_sessions(current_user: dict = Depends(get_current_user)):
    try:
        today = date.today().isoformat()
        result = (
            supabase.table("sessions")
            .select("*, subjects(name, color)")
            .eq("user_id", current_user["id"])
            .gte("started_at", today + "T00:00:00")
            .lte("started_at", today + "T23:59:59")
            .order("started_at", desc=True)
            .execute()
        )
        sessions      = result.data or []
        total_seconds = sum(s["duration_seconds"] for s in sessions)

        return {
            "success":       True,
            "count":         len(sessions),
            "total_seconds": total_seconds,
            "total_hours":   round(total_seconds / 3600, 2),
            "data":          sessions,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /api/sessions/analytics ──────────────────────────────
@router.get("/analytics")
async def get_analytics(
    days: int = Query(14, le=90),
    current_user: dict = Depends(get_current_user),
):
    try:
        from_date = (date.today() - timedelta(days=days - 1)).isoformat()

        result = (
            supabase.table("sessions")
            .select("*, subjects(name, color)")
            .eq("user_id", current_user["id"])
            .gte("started_at", from_date)
            .order("started_at")
            .execute()
        )
        sessions = result.data or []

        # Build daily breakdown (last N days)
        daily_map = {}
        for i in range(days):
            d = (date.today() - timedelta(days=days - 1 - i)).isoformat()
            daily_map[d] = {"date": d, "sessions": 0, "seconds": 0}

        # Per-subject breakdown
        subject_map: dict = {}

        for s in sessions:
            day = s["started_at"][:10]
            if day in daily_map:
                daily_map[day]["sessions"] += 1
                daily_map[day]["seconds"]  += s["duration_seconds"]

            sid = s["subject_id"] or "no_subject"
            if sid not in subject_map:
                subject_map[sid] = {
                    "subject_id":   s["subject_id"],
                    "subject_name": s.get("subjects", {}).get("name", "No Subject") if s.get("subjects") else "No Subject",
                    "color":        s.get("subjects", {}).get("color", "#555")       if s.get("subjects") else "#555",
                    "sessions":     0,
                    "seconds":      0,
                }
            subject_map[sid]["sessions"] += 1
            subject_map[sid]["seconds"]  += s["duration_seconds"]

        total_seconds    = sum(s["duration_seconds"] for s in sessions)
        unique_days      = sum(1 for d in daily_map.values() if d["seconds"] > 0)
        avg_session_secs = round(total_seconds / len(sessions)) if sessions else 0

        return {
            "success": True,
            "data": {
                "period_days":         days,
                "total_sessions":      len(sessions),
                "total_seconds":       total_seconds,
                "total_hours":         round(total_seconds / 3600, 2),
                "unique_study_days":   unique_days,
                "avg_session_seconds": avg_session_secs,
                "daily_breakdown":     list(daily_map.values()),
                "by_subject":          sorted(subject_map.values(), key=lambda x: x["seconds"], reverse=True),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /api/sessions/{session_id} ───────────────────────────
@router.get("/{session_id}")
async def get_session(session_id: str, current_user: dict = Depends(get_current_user)):
    try:
        result = (
            supabase.table("sessions")
            .select("*, subjects(name, color)")
            .eq("id", session_id)
            .eq("user_id", current_user["id"])
            .maybe_single()
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Session not found.")
        return {"success": True, "data": result.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── POST /api/sessions ────────────────────────────────────────
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_session(body: SessionCreate, current_user: dict = Depends(get_current_user)):
    if body.duration_seconds < 1:
        raise HTTPException(status_code=400, detail="duration_seconds must be at least 1.")
    if not body.started_at:
        raise HTTPException(status_code=400, detail="started_at is required.")
    try:
        result = (
            supabase.table("sessions")
            .insert({
                "user_id":          current_user["id"],
                "subject_id":       body.subject_id or None,
                "note":             body.note.strip() if body.note else None,
                "started_at":       body.started_at,
                "ended_at":         body.ended_at or datetime.utcnow().isoformat(),
                "duration_seconds": body.duration_seconds,
            })
            .select()
            .single()
            .execute()
        )
        return {"success": True, "message": "Session saved.", "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── PATCH /api/sessions/{session_id} ─────────────────────────
@router.patch("/{session_id}")
async def update_session(session_id: str, body: SessionUpdate, current_user: dict = Depends(get_current_user)):
    updates = {}
    if body.note             is not None: updates["note"]             = body.note.strip() or None
    if body.duration_seconds is not None: updates["duration_seconds"] = body.duration_seconds

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")

    try:
        result = (
            supabase.table("sessions")
            .update(updates)
            .eq("id", session_id)
            .eq("user_id", current_user["id"])
            .select()
            .single()
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Session not found.")
        return {"success": True, "message": "Session updated.", "data": result.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── DELETE /api/sessions/{session_id} ────────────────────────
@router.delete("/{session_id}")
async def delete_session(session_id: str, current_user: dict = Depends(get_current_user)):
    try:
        supabase.table("sessions").delete().eq("id", session_id).eq("user_id", current_user["id"]).execute()
        return {"success": True, "message": "Session deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
