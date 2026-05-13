"""
Deploy & Test Routes
"""
import subprocess
import asyncio
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException

router = APIRouter(prefix="/api/deploy", tags=["Deploy & Test"])


@router.post("/{project_slug}")
async def deploy_project(request: Request, project_slug: str):
    """Deploy a project: compile → service → nginx → test"""
    from deployer import Deployer
    pool = request.app.state.pool
    deployer = Deployer(pool)
    result = await deployer.deploy_project(project_slug)
    return result


@router.post("/{project_slug}/compile")
async def compile_project(request: Request, project_slug: str):
    """Compile all project components"""
    from deployer import Deployer
    pool = request.app.state.pool
    deployer = Deployer(pool)
    result = await deployer._compile_project(project_slug)
    return result


@router.post("/{project_slug}/test")
async def test_project(request: Request, project_slug: str):
    """Run tests for a project"""
    pool = request.app.state.pool
    schema = request.app.state.engine.schema

    project = await pool.fetchrow(f"SELECT * FROM {schema}.project WHERE slug=$1", project_slug)
    if not project:
        raise HTTPException(404, "Project not found")

    port = project['port']
    if not port:
        raise HTTPException(400, "Project has no port configured. Deploy first.")

    results = {"project": project_slug, "port": port, "tests": []}

    # Health check
    try:
        proc = await asyncio.create_subprocess_exec(
            "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
            f"http://localhost:{port}/health",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        status = stdout.decode().strip()
        results["tests"].append({"name": "health", "status": status, "pass": status == "200"})
    except:
        results["tests"].append({"name": "health", "status": "timeout", "pass": False})

    # Root page
    try:
        proc = await asyncio.create_subprocess_exec(
            "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
            f"http://localhost:{port}/",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        status = stdout.decode().strip()
        results["tests"].append({"name": "index", "status": status, "pass": status == "200"})
    except:
        results["tests"].append({"name": "index", "status": "timeout", "pass": False})

    # Custom curl tests from project
    curl_tests = project.get('curl_tests')
    if curl_tests:
        import json
        tests = json.loads(curl_tests) if isinstance(curl_tests, str) else curl_tests
        for t in tests:
            try:
                url = f"http://localhost:{port}{t.get('path', '/')}"
                proc = await asyncio.create_subprocess_exec(
                    "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                    "-X", t.get("method", "GET"), url,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
                status = stdout.decode().strip()
                expected = str(t.get("expect_status", 200))
                results["tests"].append({
                    "name": f"{t.get('method','GET')} {t.get('path','/')}",
                    "status": status,
                    "pass": status == expected
                })
            except:
                results["tests"].append({"name": t.get('path', '/'), "status": "error", "pass": False})

    results["passed"] = sum(1 for t in results["tests"] if t["pass"])
    results["total"] = len(results["tests"])
    results["success"] = results["passed"] == results["total"]

    return results


@router.get("/{project_slug}/status")
async def project_status(request: Request, project_slug: str):
    """Check if project service is running"""
    pool = request.app.state.pool
    schema = request.app.state.engine.schema

    project = await pool.fetchrow(f"SELECT * FROM {schema}.project WHERE slug=$1", project_slug)
    if not project:
        raise HTTPException(404, "Project not found")

    service = project.get('service_name')
    port = project.get('port')

    result = {
        "project": project_slug,
        "service_name": service,
        "port": port,
        "subdomain": project.get('subdomain'),
        "test_url": project.get('test_url'),
    }

    # Check if port is listening
    if port:
        try:
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                f"http://localhost:{port}/health",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=3)
            result["running"] = stdout.decode().strip() == "200"
        except:
            result["running"] = False
    else:
        result["running"] = False

    return result
