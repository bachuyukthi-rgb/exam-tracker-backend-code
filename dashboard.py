# routes/dashboard.py
# Single endpoint returning all dashboard stats in one API call

from fastapi import APIRouter, HTTPException, Depends
from datetime import date
from config.supabase import supabase
from middleware.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


# ── GET /api/dashboard ────────────────────────────────────────
@router.get("/")
async def get_dashboard(current_user: dict = Depends(get_current_user)):
    try:
        user_id = current_user["id"]
        today   = date.today().isoformat()

        # Fetch all tables in parallel-ish (supabase-py is sync)
        subjects_res = supabase.table("subjects").select("*").eq("user_id", user_id).execute()
        syllabus_res = supabase.table("syllabus").select("status").eq("user_id", user_id).execute()
        todos_res    = supabase.table("todos").select("completed, priority").eq("user_id", user_id).execute()
        sessions_res = supabase.table("sessions").select("duration_seconds, subject_id").eq("user_id", user_id).execute()
        today_res    = (
            supabase.table("sessions")
            .select("duration_seconds, subject_id, note, started_at, subjects(name, color)")
            .eq("user_id", user_id)
            .gte("started_at", today + "T00:00:00")
            .lte("started_at", today + "T23:59:59")
            .order("started_at", desc=True)
            .execute()
        )

        subjects = subjects_res.data or []
        syllabus = syllabus_res.data or []
        todos    = todos_res.data    or []
        sessions = sessions_res.data or []
        today_sessions = today_res.data or []

        # Aggregate
        total_study_secs  = sum(s["duration_seconds"] for s in sessions)
        today_study_secs  = sum(s["duration_seconds"] for s in today_sessions)
        syl_completed     = len([t for t in syllabus if t["status"] == "completed"])
        syl_in_progress   = len([t for t in syllabus if t["status"] == "in-progress"])
        todos_done        = len([t for t in todos if t["completed"]])
        todos_high_pending = len([t for t in todos if not t["completed"] and t["priority"] == "high"])

        # Study hours per subject
        subject_hours: dict = {}
        for s in sessions:
            if s["subject_id"]:
                subject_hours[s["subject_id"]] = subject_hours.get(s["subject_id"], 0) + s["duration_seconds"]

        subject_list = [
            {
                "id":             s["id"],
                "name":           s["name"],
                "color":          s["color"],
                "exam_date":      s.get("exam_date"),
                "study_seconds":  subject_hours.get(s["id"], 0),
                "study_hours":    round(subject_hours.get(s["id"], 0) / 3600, 2),
            }
            for s in subjects
        ]

        return {
            "success": True,
            "data": {
                "summary": {
                    "total_subjects":        len(subjects),
                    "total_sessions":        len(sessions),
                    "total_study_seconds":   total_study_secs,
                    "total_study_hours":     round(total_study_secs / 3600, 2),
                    "today_study_seconds":   today_study_secs,
                    "today_study_hours":     round(today_study_secs / 3600, 2),
                    "syllabus_total":        len(syllabus),
                    "syllabus_completed":    syl_completed,
                    "syllabus_in_progress":  syl_in_progress,
                    "syllabus_pct":          round((syl_completed / len(syllabus)) * 100) if syllabus else 0,
                    "todos_total":           len(todos),
                    "todos_done":            todos_done,
                    "todos_pending_high":    todos_high_pending,
                },
                "today_sessions": today_sessions,
                "subject_hours":  subject_list,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
