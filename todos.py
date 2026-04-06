# routes/todos.py
# Full CRUD for to-do tasks — all scoped to the authenticated user

from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel
from typing import Optional, Literal
from config.supabase import supabase
from middleware.auth import get_current_user

router = APIRouter(prefix="/api/todos", tags=["Todos"])

VALID_PRIORITIES = ["low", "medium", "high"]


# ── SCHEMAS ──────────────────────────────────────────────────
class TodoCreate(BaseModel):
    task: str
    subject_id: Optional[str]  = None
    due_date:   Optional[str]  = None   # YYYY-MM-DD
    priority:   Optional[Literal["low", "medium", "high"]] = "medium"

class TodoUpdate(BaseModel):
    task:       Optional[str]  = None
    subject_id: Optional[str]  = None
    due_date:   Optional[str]  = None
    priority:   Optional[Literal["low", "medium", "high"]] = None
    completed:  Optional[bool] = None


# ── GET /api/todos ────────────────────────────────────────────
@router.get("/")
async def get_todos(
    subject_id: Optional[str]  = Query(None),
    completed:  Optional[bool] = Query(None),
    priority:   Optional[str]  = Query(None),
    current_user: dict = Depends(get_current_user),
):
    try:
        query = (
            supabase.table("todos")
            .select("*, subjects(name, color)")
            .eq("user_id", current_user["id"])
            .order("created_at")
        )
        if subject_id is not None: query = query.eq("subject_id", subject_id)
        if completed  is not None: query = query.eq("completed",  completed)
        if priority and priority in VALID_PRIORITIES: query = query.eq("priority", priority)

        result = query.execute()
        return {"success": True, "count": len(result.data), "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /api/todos/stats ──────────────────────────────────────
@router.get("/stats")
async def get_todo_stats(current_user: dict = Depends(get_current_user)):
    try:
        result = (
            supabase.table("todos")
            .select("priority, completed")
            .eq("user_id", current_user["id"])
            .execute()
        )
        todos = result.data or []
        total = len(todos)
        done  = len([t for t in todos if t["completed"]])

        by_priority = {p: {"total": 0, "done": 0} for p in VALID_PRIORITIES}
        for t in todos:
            p = t.get("priority", "medium")
            by_priority[p]["total"] += 1
            if t["completed"]:
                by_priority[p]["done"] += 1

        return {
            "success": True,
            "data": {
                "total":          total,
                "completed":      done,
                "pending":        total - done,
                "completion_pct": round((done / total) * 100) if total else 0,
                "by_priority":    by_priority,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /api/todos/{todo_id} ──────────────────────────────────
@router.get("/{todo_id}")
async def get_todo(todo_id: str, current_user: dict = Depends(get_current_user)):
    try:
        result = (
            supabase.table("todos")
            .select("*, subjects(name, color)")
            .eq("id", todo_id)
            .eq("user_id", current_user["id"])
            .maybe_single()
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Task not found.")
        return {"success": True, "data": result.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── POST /api/todos ───────────────────────────────────────────
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_todo(body: TodoCreate, current_user: dict = Depends(get_current_user)):
    if not body.task or not body.task.strip():
        raise HTTPException(status_code=400, detail="Task description is required.")
    try:
        result = (
            supabase.table("todos")
            .insert({
                "user_id":    current_user["id"],
                "task":       body.task.strip(),
                "subject_id": body.subject_id or None,
                "due_date":   body.due_date   or None,
                "priority":   body.priority   or "medium",
                "completed":  False,
            })
            .select()
            .single()
            .execute()
        )
        return {"success": True, "message": "Task created.", "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── PATCH /api/todos/{todo_id} ────────────────────────────────
@router.patch("/{todo_id}")
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
        result = (
            supabase.table("todos")
            .update(updates)
            .eq("id", todo_id)
            .eq("user_id", current_user["id"])
            .select()
            .single()
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Task not found.")
        return {"success": True, "message": "Task updated.", "data": result.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── PATCH /api/todos/{todo_id}/toggle ────────────────────────
@router.patch("/{todo_id}/toggle")
async def toggle_todo(todo_id: str, current_user: dict = Depends(get_current_user)):
    try:
        existing = (
            supabase.table("todos")
            .select("completed")
            .eq("id", todo_id)
            .eq("user_id", current_user["id"])
            .maybe_single()
            .execute()
        )
        if not existing.data:
            raise HTTPException(status_code=404, detail="Task not found.")

        new_val = not existing.data["completed"]
        result  = (
            supabase.table("todos")
            .update({"completed": new_val})
            .eq("id", todo_id)
            .eq("user_id", current_user["id"])
            .select()
            .single()
            .execute()
        )
        label = "completed" if new_val else "pending"
        return {"success": True, "message": f"Task marked as {label}.", "data": result.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── DELETE /api/todos/{todo_id} ───────────────────────────────
@router.delete("/{todo_id}")
async def delete_todo(todo_id: str, current_user: dict = Depends(get_current_user)):
    try:
        supabase.table("todos").delete().eq("id", todo_id).eq("user_id", current_user["id"]).execute()
        return {"success": True, "message": "Task deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── DELETE /api/todos/completed/all ──────────────────────────
@router.delete("/completed/all")
async def clear_completed(current_user: dict = Depends(get_current_user)):
    try:
        result = (
            supabase.table("todos")
            .delete()
            .eq("user_id", current_user["id"])
            .eq("completed", True)
            .execute()
        )
        count = len(result.data) if result.data else 0
        return {"success": True, "message": f"{count} completed tasks deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
