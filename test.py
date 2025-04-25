from fastapi import FastAPI, Header, HTTPException
from supabase import create_client
import jwt

app = FastAPI()

SUPABASE_URL = "https://fwbdrdjuzrykqpmevftt.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ3YmRyZGp1enJ5a3FwbWV2ZnR0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0NDgwOTAwNSwiZXhwIjoyMDYwMzg1MDA1fQ.9gasZr5wpH91P-A7ON38FiNO-8i6A8gs-vglNBjttNc"
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

@app.post("/api/delete-user")
async def delete_user(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")

    token = authorization.split(" ")[1]
    payload = jwt.decode(token, options={"verify_signature": False})
    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid token payload")

    supabase.auth.admin.delete_user(user_id)
    return {"status": "success"}
