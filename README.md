# Exam Tracker — Python Backend

REST API for the Exam Tracker website built with **Python**, **FastAPI**, and **Supabase**.

---

## Folder Structure

```
exam-tracker-python-backend/
├── main.py                    ← Entry point (FastAPI app)
├── requirements.txt           ← Python dependencies
├── .env.example               ← Copy to .env and fill in values
├── config/
│   ├── __init__.py
│   └── supabase.py            ← Supabase admin client
├── middleware/
│   ├── __init__.py
│   └── auth.py                ← JWT verification dependency
└── routes/
    ├── __init__.py
    ├── auth.py                ← signup, login, logout, /me
    ├── subjects.py            ← Subject CRUD + stats
    ├── syllabus.py            ← Syllabus CRUD + cycle-status
    ├── todos.py               ← Todo CRUD + toggle + stats
    ├── sessions.py            ← Session CRUD + analytics
    └── dashboard.py           ← All stats in one call
```

---

## Setup

### 1. Create virtual environment
```bash
python -m venv venv

# Activate:
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
```

Edit `.env` and fill in:
```env
SUPABASE_URL=https://YOUR_PROJECT_ID.supabase.co
SUPABASE_SERVICE_KEY=YOUR_SERVICE_ROLE_KEY
SUPABASE_JWT_SECRET=YOUR_JWT_SECRET
PORT=8000
FRONTEND_URL=http://127.0.0.1:5500
```

**Where to find these values:**
| Variable | Location in Supabase |
|---|---|
| `SUPABASE_URL` | Settings → API → Project URL |
| `SUPABASE_SERVICE_KEY` | Settings → API → `service_role` key |
| `SUPABASE_JWT_SECRET` | Settings → API → JWT Secret |

### 4. Run the server
```bash
python main.py
```

---

## API Docs

FastAPI auto-generates interactive API docs:

| URL | Description |
|-----|-------------|
| `http://localhost:8000/docs`   | Swagger UI — test endpoints in browser |
| `http://localhost:8000/redoc`  | ReDoc — clean reference docs |
| `http://localhost:8000/health` | Health check |
| `http://localhost:8000/api`    | JSON endpoint list |

---

## API Reference

All protected endpoints require:
```
Authorization: Bearer <supabase_access_token>
```

### Auth

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/signup` | `{email, password, full_name?}` | Create account |
| POST | `/api/auth/login` | `{email, password}` | Sign in → returns tokens |
| POST | `/api/auth/logout` | — | Sign out |
| GET | `/api/auth/me` | — | Current user info |
| POST | `/api/auth/reset-password` | `{email}` | Send reset email |
| POST | `/api/auth/refresh` | `{refresh_token}` | Get new access token |

### Subjects

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/subjects` | All subjects |
| GET | `/api/subjects/{id}` | Single subject |
| GET | `/api/subjects/{id}/stats` | Subject + completion + study hours |
| POST | `/api/subjects` | Create — `{name, code?, exam_date?, color?}` |
| PATCH | `/api/subjects/{id}` | Update any field |
| DELETE | `/api/subjects/{id}` | Delete (cascades to syllabus/sessions) |

### Syllabus

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/syllabus` | All topics. Filter: `?subject_id=&status=` |
| GET | `/api/syllabus/{id}` | Single topic |
| POST | `/api/syllabus` | Create — `{subject_id, topic, unit?, status?}` |
| PATCH | `/api/syllabus/{id}` | Update topic/unit/status |
| PATCH | `/api/syllabus/{id}/cycle-status` | pending → in-progress → completed → pending |
| DELETE | `/api/syllabus/{id}` | Delete topic |
| DELETE | `/api/syllabus/subject/{subject_id}` | Delete all for a subject |

### Todos

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/todos` | All tasks. Filter: `?completed=true&priority=high` |
| GET | `/api/todos/stats` | Stats by priority |
| GET | `/api/todos/{id}` | Single task |
| POST | `/api/todos` | Create — `{task, subject_id?, due_date?, priority?}` |
| PATCH | `/api/todos/{id}` | Update any field |
| PATCH | `/api/todos/{id}/toggle` | Toggle completed |
| DELETE | `/api/todos/{id}` | Delete task |
| DELETE | `/api/todos/completed/all` | Clear all completed |

### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sessions` | All sessions. Filter: `?subject_id=&from=&to=` |
| GET | `/api/sessions/today` | Today's sessions + total time |
| GET | `/api/sessions/analytics` | Analytics `?days=14` |
| GET | `/api/sessions/{id}` | Single session |
| POST | `/api/sessions` | Save — `{subject_id?, note?, started_at, ended_at?, duration_seconds}` |
| PATCH | `/api/sessions/{id}` | Update note/duration |
| DELETE | `/api/sessions/{id}` | Delete session |

### Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard` | All stats in one call |

---

## Connecting to the Frontend

In your `app.js`, call this backend instead of Supabase directly:

```js
const API = 'http://localhost:8000/api';

async function loadAllData() {
  const token = (await db.auth.getSession()).data.session?.access_token;
  const headers = { Authorization: `Bearer ${token}` };

  const [subjects, syllabus, todos, sessions] = await Promise.all([
    fetch(`${API}/subjects`,  { headers }).then(r => r.json()),
    fetch(`${API}/syllabus`,  { headers }).then(r => r.json()),
    fetch(`${API}/todos`,     { headers }).then(r => r.json()),
    fetch(`${API}/sessions`,  { headers }).then(r => r.json()),
  ]);

  state.subjects = subjects.data;
  state.syllabus = syllabus.data;
  state.todos    = todos.data;
  state.sessions = sessions.data;
  renderAll();
}
```

---

## Security Features

- **JWT verification** on every protected route via FastAPI `Depends`
- **CORS** restricted to your frontend URL
- **Rate limiting** via SlowAPI
- **Service Role key** used server-side only — never exposed to browser
- All DB queries are scoped to `user_id` — users cannot access each other's data
