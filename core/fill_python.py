"""Fill Python API Gateway pillars into DB components."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.engine import CoreEngine

DSN = "postgresql://aifirst:aifirst_password@localhost:5433/ai_first_platform"

PILLARS = {
"api-config": {"logic": r'''
import os
class Config:
    PG_URL = os.getenv("DATABASE_URL", "postgresql://aifirst:aifirst_password@localhost:5433/ai_first_platform")
    JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-key-123")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 1 day
'''},

"auth-models": {"logic": r'''
from pydantic import BaseModel
from typing import Optional

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[int] = None
    tenant_id: Optional[int] = None
'''},

"auth-service": {"logic": r'''
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from .api_config import Config

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=Config.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, Config.JWT_SECRET, algorithm=Config.ALGORITHM)
'''},

"perm-gate": {"logic": r'''
from fastapi import HTTPException, status
from .auth_models import TokenData

class PermissionGate:
    def __init__(self):
        # Table -> Role -> [operations]
        self.rules = {
            "users": {"admin": ["read", "save", "delete"], "user": ["read"]},
            "change_log": {"admin": ["read"]}
        }

    def check(self, user: TokenData, table: str, action: str):
        # Super admin bypass
        if user.username == "admin": return True
        
        table_rules = self.rules.get(table, {"user": ["read"]})
        allowed_actions = table_rules.get("user", []) # Default to user role
        if action in allowed_actions:
            return True
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Action {action} not allowed on {table}"
        )
'''},

"route-registry": {"logic": r'''
from .cpp_proxy import CppProxy
from .perm_gate import PermissionGate

class RouteRegistry:
    def __init__(self, app, proxy: CppProxy):
        self.app = app
        self.proxy = proxy
        self.gate = PermissionGate()

    def register_crud(self, table_name: str):
        @self.app.post(f"/api/{table_name}/{{action}}")
        async def handle(action: str, payload: dict, user = Depends(get_current_user)):
            self.gate.check(user, table_name, action)
            payload["object"] = {"name": table_name}
            payload["action"] = action
            payload["context"] = {"user_id": user.user_id, "tenant_id": user.tenant_id}
            return await self.proxy.call(payload)
'''}

"api-entry": {"logic": r'''
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from .auth_service import create_access_token, verify_password
from .auth_models import UserLogin, Token
from .cpp_proxy import CppProxy

app = FastAPI(title="AI-First Unified API")
proxy = CppProxy()

@app.get("/health")
async def health():
    return await proxy.call({"action": "health"})

@app.post("/login", response_model=Token)
async def login(data: UserLogin):
    # This would normally query the DB via proxy
    # For now, a hardcoded nucleus admin
    if data.username == "admin" and data.password == "admin123":
        token = create_access_token({"sub": data.username, "user_id": 1, "tenant_id": 1})
        return {"access_token": token, "token_type": "bearer"}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/api/{table}/{action}")
async def dynamic_crud(table: str, action: str, payload: dict):
    # Inject table and action into payload for CPP ORM
    payload["action"] = action
    payload["object"] = {"name": table}
    return await proxy.call(payload)
'''}
}

async def main():
    e = CoreEngine(DSN)
    # We don't connect here because DB might be down
    # We will just print the plan for now
    print("Plan: Fill Python API Gateway components")
    for slug, pillars in PILLARS.items():
        print(f"  + {slug}: {len(pillars.get('logic', ''))} bytes of logic")
    
    # In a real run, we would do:
    # await e.connect()
    # for slug, pillars in PILLARS.items():
    #     cid = await e.get_cid_by_slug(slug)
    #     for kind, content in pillars.items():
    #         await e.set_pillar(cid, kind, content, lang="python")
    
if __name__ == "__main__":
    asyncio.run(main())
