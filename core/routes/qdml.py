from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional

router = APIRouter(prefix="/api/qdml", tags=["qdml"])


async def require_auth(request: Request, authorization: Optional[str] = Header(None)):
    engine = request.app.state.engine
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization required")
    token = authorization.replace("Bearer ", "")
    user = await engine.verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


@router.post("")
async def execute_qdml(request: Request, authorization: Optional[str] = Header(None)):
    engine = request.app.state.engine
    user = await require_auth(request, authorization)
    body = await request.json()
    result = await engine.execute_json(body, user)
    return result


@router.get("/mini/{project_slug}")
async def mini(project_slug: str, level: int = 0, request: Request = None):
    engine = request.app.state.engine
    data = await engine.mini(project_slug, level)
    return {"ok": True, "data": data}


@router.get("/stats")
async def stats(request: Request):
    engine = request.app.state.engine
    data = await engine.stats()
    return {"ok": True, "data": data}


@router.get("/describe")
async def describe(project: Optional[str] = None, request: Request = None):
    engine = request.app.state.engine
    data = await engine.describe(project)
    return {"ok": True, "data": data}
