from fastapi import APIRouter, Request, HTTPException, Header
from pathlib import Path
from typing import Optional

router = APIRouter(prefix="/api/compile", tags=["compile"])

GENERATED_DIR = Path(__file__).parent.parent.parent / "mas-front" / "_generated"


@router.post("/{component_slug}")
async def compile_component(component_slug: str, request: Request, authorization: Optional[str] = Header(None)):
    engine = request.app.state.engine
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization required")
    token = authorization.replace("Bearer ", "")
    user = await engine.verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    body = await request.json() if await request.body() else {}
    markers = body.get("markers", False)
    project = body.get("project")
    output_path = body.get("output_path")

    code = await engine.compile_component(component_slug, inject_markers=markers, project_slug=project)
    if code is None:
        raise HTTPException(status_code=404, detail=f"Component not found: {component_slug}")

    if output_path:
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(code, encoding="utf-8")
        return {"ok": True, "lines": code.count('\n') + 1, "chars": len(code), "written_to": str(out_file)}

    return {"ok": True, "data": code, "lines": code.count('\n') + 1, "chars": len(code)}


@router.post("/all/{project_slug}")
async def compile_all(project_slug: str, request: Request, authorization: Optional[str] = Header(None)):
    engine = request.app.state.engine
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization required")
    token = authorization.replace("Bearer ", "")
    user = await engine.verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    tree = await engine.describe(project_slug)
    if not tree:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_slug}")

    results = []
    for module in tree[0]["modules"]:
        for comp in module["components"]:
            code = await engine.compile_component(comp["slug"], inject_markers=False, project_slug=project_slug)
            marked = await engine.compile_component(comp["slug"], inject_markers=True, project_slug=project_slug)
            if code:
                results.append({
                    "component": comp["slug"],
                    "module": module["slug"],
                    "lines": code.count('\n') + 1,
                    "chars": len(code)
                })

    return {"ok": True, "compiled": len(results), "components": results}
