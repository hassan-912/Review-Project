# Last Update — Phase 1: Stabilize & Secure

## Changes Applied in Phase 1

### Step 2 — Secrets moved to environment variables
- `GEMINI_API_KEY` removed from source; now read via `os.environ.get("GEMINI_API_KEY")`.
- `SUPABASE_URL` and `SUPABASE_ANON_KEY` removed from source; now read via `os.environ.get(...)`.
- `SUPABASE_SERVICE_ROLE_KEY` was already read from `.env` — no change needed.
- If `GEMINI_API_KEY` is missing at startup, the app shows a friendly error and halts.
- If `SUPABASE_URL` or `SUPABASE_SERVICE_ROLE_KEY` is missing, `get_sb_client()` raises a clear error.
- Created `.env.example` with all four variable names, empty values, and purpose comments.
- `requirements.txt` encoding bug fixed (python-dotenv line had embedded null bytes from UTF-16 save).

### Step 3 — Auth bypasses removed
- Hardcoded master admin credential check (`admin` / redacted) removed from `_supabase_sign_in`.
- `_ma` query-parameter restore block removed from `_restore_session_from_params`.
- `_ma` no longer written in `_supabase_sign_in` or cleared in `_supabase_sign_out`.
- `master-admin` special-case removed from `render_my_history`.
- All logins now go through Supabase auth. Admin role is loaded from the `profiles` table.
- `_t` / `_r` session-survival tokens are unchanged and still work exactly as before.

### Step 1 — Git / safety
- Full backup at: `c:\Users\Menna\Documents\projects\Review_backup_pre_phase1`
- Branch: `phase1-stabilize` (snapshot commit: 21489a1)
- Unmerged `__pycache__` pyc files removed from git index (kept on disk).
- `.gitignore` updated to include `.env`, `*.pyo`, `*.pyd`, `.venv/`, IDE files.
- `.env` confirmed gitignored and untracked.

## Required Manual Action
Add the following variables to your `.env` file before restarting the app:

```
GEMINI_API_KEY=<your rotated key>
SUPABASE_URL=https://<your-project>.supabase.co
SUPABASE_ANON_KEY=<your anon key>
SUPABASE_SERVICE_ROLE_KEY=<already in .env — no change needed>
```

See `.env.example` for the template.

## Next Steps (Later Phases)
- Phase 2: UI/UX redesign
- Phase 3: `_t`/`_r` session-survival redesign
