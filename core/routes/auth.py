from fastapi import APIRouter, Request, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(body: LoginRequest, request: Request):
    engine = request.app.state.engine
    result = await engine.login(body.username, body.password)
    if not result:
        return {"ok": False, "error": "Invalid credentials"}
    return {"ok": True, "token": result["token"], "user": result["user"]}


@router.post("/logout")
async def logout(request: Request, authorization: Optional[str] = Header(None)):
    engine = request.app.state.engine
    if authorization:
        token = authorization.replace("Bearer ", "")
        await engine.logout(token)
    return {"ok": True}


@router.post("/verify")
async def verify(request: Request, authorization: Optional[str] = Header(None)):
    engine = request.app.state.engine
    if not authorization:
        raise HTTPException(status_code=401, detail="No token")
    token = authorization.replace("Bearer ", "")
    user = await engine.verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"ok": True, "user": user}
