"""
Deployer — Auto nginx + systemd + certbot + test URL for each project
"""
import asyncio
import subprocess
import os
from pathlib import Path
from platform_pipeline import strip_code_fence


class Deployer:
    """Creates real running services from QDML projects"""

    NGINX_SITES = Path("/etc/nginx/sites-available")
    NGINX_ENABLED = Path("/etc/nginx/sites-enabled")
    SYSTEMD_DIR = Path("/etc/systemd/system")
    BASE_PORT = 9000  # Projects get 9001, 9002, etc.

    def __init__(self, pool, schema="qdml"):
        self.pool = pool
        self.schema = schema

    async def deploy_project(self, project_slug: str) -> dict:
        """Full deploy: compile → service → nginx → certbot → test"""
        project = await self.pool.fetchrow(
            f"SELECT * FROM {self.schema}.project WHERE slug=$1", project_slug
        )
        if not project:
            return {"error": f"Project {project_slug} not found"}

        subdomain = project['subdomain'] or f"{project_slug}.test.localhost"
        port = project['port'] or await self._next_port()
        service_name = project['service_name'] or f"qdml-{project_slug}"
        scheme = "http" if ("localhost" in subdomain or "test" in subdomain) else "https"

        # Update project with deploy info
        await self.pool.execute(f"""
            UPDATE {self.schema}.project
            SET subdomain=$2, port=$3, service_name=$4, nginx_domain=$5, test_url=$6
            WHERE slug=$1
        """, project_slug, subdomain, port, service_name, subdomain,
            f"{scheme}://{subdomain}")

        results = {"project": project_slug, "steps": []}

        # 1. Compile all components
        results["steps"].append(await self._compile_project(project_slug))

        # 2. Create systemd service
        results["steps"].append(await self._create_service(project_slug, port, service_name))

        # 3. Create nginx config
        results["steps"].append(await self._create_nginx(project_slug, subdomain, port))

        # 4. SSL (certbot)
        results["steps"].append(await self._setup_ssl(subdomain))

        # 5. Start service
        results["steps"].append(await self._start_service(service_name))

        # 6. Generate test script
        results["steps"].append(await self._generate_tests(project_slug, subdomain, port))

        # Log
        await self.pool.execute(f"""
            INSERT INTO {self.schema}.deploy_log (project_id, action, status, output)
            VALUES ($1, 'deploy', 'completed', $2)
        """, project['id'], str(results))

        return results

    async def _next_port(self):
        """Find next available port"""
        max_port = await self.pool.fetchval(
            f"SELECT COALESCE(MAX(port), {self.BASE_PORT}) FROM {self.schema}.project WHERE port IS NOT NULL"
        )
        return max_port + 1

    async def _compile_project(self, slug):
        """Compile all components to _generated with language-aware assets."""

        components = await self.pool.fetch(f"""
            SELECT c.id, c.slug, c.target FROM {self.schema}.component c
            JOIN {self.schema}.module m ON c.module_id = m.id
            JOIN {self.schema}.project p ON m.project_id = p.id
            WHERE p.slug = $1
            ORDER BY m.sort_order, c.sort_order, c.slug
        """, slug)

        gen_dir = Path(f"/srv/apps/ai-first/{slug}/_generated")
        gen_dir.mkdir(parents=True, exist_ok=True)

        compiled = 0
        css_parts = []
        lang_ext = {
            "python": ".py",
            "cpp": ".cpp",
            "sql": ".sql",
            "docker": ".dockerfile",
            "html": ".html",
            "css": ".css",
            "javascript": ".js",
            "mas-js": ".js",
            "node": ".js",
            "bun": ".js",
        }
        for comp in components:
            bulks = await self.pool.fetch(
                f"""
                SELECT bulk_name, content, lang
                FROM {self.schema}.pillar
                WHERE component_id=$1 AND kind='bulk'
                ORDER BY bulk_order, bulk_name
                """,
                comp["id"],
            )
            by_lang = {}
            for bulk in bulks:
                lang = (bulk["lang"] or comp["target"] or "javascript").lower()
                content = strip_code_fence(bulk["content"] or "")
                if lang == "css":
                    css_parts.append(f"/* {comp['slug']}:{bulk['bulk_name']} */\n{content}")
                    continue
                by_lang.setdefault(lang, []).append(content)

            for lang, parts in by_lang.items():
                ext = lang_ext.get(lang, ".txt")
                target = gen_dir / f"{comp['slug']}{ext}"
                target.write_text("\n\n".join(parts), encoding="utf-8")
                compiled += 1

        if css_parts:
            (gen_dir / "styles.css").write_text("\n\n".join(css_parts), encoding="utf-8")

        return {"step": "compile", "status": "ok", "compiled": compiled, "css_bundle": bool(css_parts)}

    async def _create_service(self, slug, port, service_name):
        """Create systemd service file"""
        gen_dir = Path(f"/srv/apps/ai-first/{slug}/_generated")

        service_content = f"""[Unit]
Description=QDML {slug} Service
After=network.target postgresql.service

[Service]
Type=simple
WorkingDirectory={gen_dir}
Environment=PORT={port}
Environment=DATABASE_URL=postgresql://ai_auto:233f290cb68a514e3bb740d134f5bd50@127.0.0.1:5432/ai_auto
ExecStart=/usr/bin/node server.js
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
        service_path = self.SYSTEMD_DIR / f"{service_name}.service"

        try:
            service_path.write_text(service_content)
            subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
            return {"step": "systemd", "status": "ok", "path": str(service_path)}
        except PermissionError:
            # Save locally if no root
            local_path = gen_dir / f"{service_name}.service"
            local_path.write_text(service_content)
            return {"step": "systemd", "status": "saved_locally", "path": str(local_path)}

    async def _create_nginx(self, slug, subdomain, port):
        """Create nginx reverse proxy config"""
        nginx_conf = f"""server {{
    listen 80;
    server_name {subdomain};

    location / {{
        proxy_pass http://127.0.0.1:{port};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
}}
"""
        conf_path = self.NGINX_SITES / f"{subdomain}.conf"

        try:
            conf_path.write_text(nginx_conf)
            # Enable site
            enabled_path = self.NGINX_ENABLED / f"{subdomain}.conf"
            if not enabled_path.exists():
                enabled_path.symlink_to(conf_path)
            # Test nginx
            result = subprocess.run(["nginx", "-t"], capture_output=True, text=True)
            if result.returncode == 0:
                subprocess.run(["systemctl", "reload", "nginx"], capture_output=True)
                return {"step": "nginx", "status": "ok", "domain": subdomain}
            else:
                return {"step": "nginx", "status": "config_error", "error": result.stderr}
        except PermissionError:
            # Save locally
            gen_dir = Path(f"/srv/apps/ai-first/{slug}/_generated")
            gen_dir.mkdir(parents=True, exist_ok=True)
            (gen_dir / f"{subdomain}.nginx.conf").write_text(nginx_conf)
            return {"step": "nginx", "status": "saved_locally", "path": str(gen_dir / f"{subdomain}.nginx.conf")}

    async def _setup_ssl(self, subdomain):
        """Setup SSL with certbot"""
        if "localhost" in subdomain or "test" in subdomain:
            return {"step": "ssl", "status": "skipped", "reason": "localhost/test domain"}

        try:
            result = subprocess.run(
                ["certbot", "certonly", "--nginx", "-d", subdomain, "--non-interactive", "--agree-tos"],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                return {"step": "ssl", "status": "ok"}
            else:
                return {"step": "ssl", "status": "error", "error": result.stderr[:200]}
        except Exception as e:
            return {"step": "ssl", "status": "error", "error": str(e)[:200]}

    async def _start_service(self, service_name):
        """Start the systemd service"""
        try:
            subprocess.run(["systemctl", "start", service_name], capture_output=True)
            result = subprocess.run(["systemctl", "is-active", service_name], capture_output=True, text=True)
            return {"step": "start", "status": result.stdout.strip()}
        except Exception as e:
            return {"step": "start", "status": "error", "error": str(e)[:100]}

    async def _generate_tests(self, slug, subdomain, port):
        """Generate playwright + curl test scripts"""
        gen_dir = Path(f"/srv/apps/ai-first/{slug}/_generated")
        gen_dir.mkdir(parents=True, exist_ok=True)

        # Curl tests
        curl_tests = f"""#!/bin/bash
# Auto-generated tests for {slug}
echo "Testing {slug} on port {port}..."

# Health check
STATUS=$(curl -s -o /dev/null -w '%{{http_code}}' http://localhost:{port}/health 2>/dev/null || echo "000")
if [ "$STATUS" = "200" ]; then echo "✅ Health: OK"; else echo "❌ Health: $STATUS"; fi

# API test
STATUS=$(curl -s -o /dev/null -w '%{{http_code}}' http://localhost:{port}/ 2>/dev/null || echo "000")
if [ "$STATUS" = "200" ]; then echo "✅ Root: OK"; else echo "❌ Root: $STATUS"; fi

echo "Done."
"""
        (gen_dir / "test-curl.sh").write_text(curl_tests)
        (gen_dir / "test-curl.sh").chmod(0o755)

        # Playwright test
        playwright_test = f"""// Auto-generated Playwright test for {slug}
const {{ test, expect }} = require('@playwright/test');

test.describe('{slug}', () => {{
    test('loads main page', async ({{ page }}) => {{
        await page.goto('http://localhost:{port}/');
        await expect(page).toHaveTitle(/.+/);
    }});

    test('health endpoint', async ({{ request }}) => {{
        const response = await request.get('http://localhost:{port}/health');
        expect(response.ok()).toBeTruthy();
    }});
}});
"""
        (gen_dir / "test.spec.js").write_text(playwright_test)

        # Save to project
        await self.pool.execute(f"""
            UPDATE {self.schema}.project
            SET curl_tests = $2::jsonb,
                playwright_script = $3
            WHERE slug = $1
        """, slug,
            f'[{{"method":"GET","path":"/health","expect_status":200}},{{"method":"GET","path":"/","expect_status":200}}]',
            playwright_test)

        return {"step": "tests", "status": "ok", "files": ["test-curl.sh", "test.spec.js"]}
