"""Tests for production deployment configuration files."""

from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


class TestDockerfile:
    """Validate Dockerfile structure."""

    def test_dockerfile_exists(self):
        assert (BASE / "Dockerfile").is_file()

    def test_dockerfile_has_multi_stage_build(self):
        content = (BASE / "Dockerfile").read_text()
        assert "AS builder" in content
        assert "COPY --from=builder" in content

    def test_dockerfile_copies_source_before_install(self):
        content = (BASE / "Dockerfile").read_text()
        lines = content.splitlines()
        copy_line = next(i for i, line in enumerate(lines) if "COPY . ." in line)
        install_line = next(i for i, line in enumerate(lines) if "pip install" in line)
        assert copy_line < install_line

    def test_dockerfile_uses_entrypoint(self):
        content = (BASE / "Dockerfile").read_text()
        assert "ENTRYPOINT" in content
        assert "entrypoint.sh" in content

    def test_dockerfile_exposes_8000(self):
        content = (BASE / "Dockerfile").read_text()
        assert "EXPOSE 8000" in content

    def test_dockerfile_uses_gunicorn(self):
        content = (BASE / "Dockerfile").read_text()
        assert "gunicorn" in content


class TestDockerfileMcp:
    """Validate Dockerfile.mcp structure."""

    def test_dockerfile_mcp_exists(self):
        assert (BASE / "Dockerfile.mcp").is_file()

    def test_dockerfile_mcp_copies_source_before_install(self):
        content = (BASE / "Dockerfile.mcp").read_text()
        lines = content.splitlines()
        copy_line = next(i for i, line in enumerate(lines) if "COPY . ." in line)
        install_line = next(i for i, line in enumerate(lines) if "pip install" in line)
        assert copy_line < install_line

    def test_dockerfile_mcp_exposes_8080(self):
        content = (BASE / "Dockerfile.mcp").read_text()
        assert "EXPOSE 8080" in content

    def test_dockerfile_mcp_runs_mcp_server(self):
        content = (BASE / "Dockerfile.mcp").read_text()
        assert "mcp_server.server" in content


class TestEntrypoint:
    """Validate entrypoint script."""

    def test_entrypoint_exists(self):
        assert (BASE / "docker" / "entrypoint.sh").is_file()

    def test_entrypoint_runs_collectstatic(self):
        content = (BASE / "docker" / "entrypoint.sh").read_text()
        assert "collectstatic" in content

    def test_entrypoint_uses_exec(self):
        content = (BASE / "docker" / "entrypoint.sh").read_text()
        assert 'exec "$@"' in content

    def test_entrypoint_is_executable(self):
        import os

        path = BASE / "docker" / "entrypoint.sh"
        assert os.access(path, os.X_OK)


class TestDockerComposeProd:
    """Validate docker-compose.prod.yml structure."""

    def test_compose_file_exists(self):
        assert (BASE / "docker-compose.prod.yml").is_file()

    def test_compose_has_all_services(self):
        content = (BASE / "docker-compose.prod.yml").read_text()
        for service in ("nginx:", "django:", "mcp:", "db:", "ollama:"):
            assert service in content, f"Missing service: {service}"

    def test_only_nginx_exposes_ports(self):
        content = (BASE / "docker-compose.prod.yml").read_text()
        # Parse sections between services
        lines = content.splitlines()
        in_nginx = False
        nginx_has_ports = False
        non_nginx_ports = False
        current_service = None

        for line in lines:
            stripped = line.strip()
            # Detect top-level service definitions
            if stripped and not stripped.startswith("#") and not stripped.startswith("-"):
                if stripped.endswith(":") and line[0] == " " and line[1] == " " and line[2] != " ":
                    current_service = stripped.rstrip(":")
                    in_nginx = current_service == "nginx"

            if "ports:" in stripped:
                if in_nginx:
                    nginx_has_ports = True
                elif current_service in ("django", "mcp", "db", "ollama"):
                    non_nginx_ports = True

        assert nginx_has_ports, "Nginx should expose ports"
        assert not non_nginx_ports, "Only Nginx should expose host ports"

    def test_compose_has_gpu_config(self):
        content = (BASE / "docker-compose.prod.yml").read_text()
        assert "nvidia" in content
        assert "gpu" in content

    def test_compose_has_healthcheck(self):
        content = (BASE / "docker-compose.prod.yml").read_text()
        assert "healthcheck" in content
        assert "pg_isready" in content

    def test_compose_has_staticfiles_volume(self):
        content = (BASE / "docker-compose.prod.yml").read_text()
        assert "staticfiles" in content


class TestNginxConfig:
    """Validate nginx configuration."""

    def test_nginx_conf_exists(self):
        assert (BASE / "nginx" / "nginx.conf").is_file()

    def test_nginx_has_ssl(self):
        content = (BASE / "nginx" / "nginx.conf").read_text()
        assert "ssl_certificate" in content
        assert "ssl_certificate_key" in content

    def test_nginx_has_http_redirect(self):
        content = (BASE / "nginx" / "nginx.conf").read_text()
        assert "return 301 https" in content

    def test_nginx_proxies_to_django(self):
        content = (BASE / "nginx" / "nginx.conf").read_text()
        assert "proxy_pass http://django:8000" in content

    def test_nginx_proxies_to_mcp(self):
        content = (BASE / "nginx" / "nginx.conf").read_text()
        assert "proxy_pass http://mcp:8080" in content

    def test_nginx_serves_static_files(self):
        content = (BASE / "nginx" / "nginx.conf").read_text()
        assert "location /static/" in content
        assert "/app/staticfiles/" in content

    def test_nginx_sets_forwarded_proto(self):
        content = (BASE / "nginx" / "nginx.conf").read_text()
        assert "X-Forwarded-Proto" in content

    def test_nginx_sets_client_max_body_size(self):
        content = (BASE / "nginx" / "nginx.conf").read_text()
        assert "client_max_body_size" in content


class TestScripts:
    """Validate shell scripts."""

    def test_generate_certs_exists_and_executable(self):
        import os

        path = BASE / "scripts" / "generate_certs.sh"
        assert path.is_file()
        assert os.access(path, os.X_OK)

    def test_generate_certs_creates_key_and_cert(self):
        content = (BASE / "scripts" / "generate_certs.sh").read_text()
        assert "server.key" in content
        assert "server.crt" in content
        assert "openssl" in content

    def test_backup_exists_and_executable(self):
        import os

        path = BASE / "scripts" / "backup.sh"
        assert path.is_file()
        assert os.access(path, os.X_OK)

    def test_backup_uses_pg_dump(self):
        content = (BASE / "scripts" / "backup.sh").read_text()
        assert "pg_dump" in content
        assert "-Fc" in content

    def test_restore_exists_and_executable(self):
        import os

        path = BASE / "scripts" / "restore.sh"
        assert path.is_file()
        assert os.access(path, os.X_OK)

    def test_restore_uses_pg_restore(self):
        content = (BASE / "scripts" / "restore.sh").read_text()
        assert "pg_restore" in content
        assert "--clean" in content


class TestProductionSettings:
    """Validate production settings."""

    def test_production_settings_exists(self):
        assert (BASE / "engram" / "settings" / "production.py").is_file()

    def test_has_secure_proxy_ssl_header(self):
        content = (BASE / "engram" / "settings" / "production.py").read_text()
        assert "SECURE_PROXY_SSL_HEADER" in content
        assert "X-Forwarded-Proto" in content

    def test_has_conn_max_age(self):
        content = (BASE / "engram" / "settings" / "production.py").read_text()
        assert "CONN_MAX_AGE" in content

    def test_debug_is_false(self):
        content = (BASE / "engram" / "settings" / "production.py").read_text()
        assert "DEBUG = False" in content

    def test_ssl_redirect_enabled(self):
        content = (BASE / "engram" / "settings" / "production.py").read_text()
        assert "SECURE_SSL_REDIRECT = True" in content


class TestDockerignore:
    """Validate .dockerignore."""

    def test_dockerignore_exists(self):
        assert (BASE / ".dockerignore").is_file()

    def test_dockerignore_excludes_secrets(self):
        content = (BASE / ".dockerignore").read_text()
        assert ".env" in content
        assert "certs/" in content

    def test_dockerignore_excludes_git(self):
        content = (BASE / ".dockerignore").read_text()
        assert ".git" in content


class TestCleanup:
    """Verify obsolete files are removed."""

    def test_server_py_removed(self):
        assert not (BASE / "server.py").exists()

    def test_embedder_py_removed(self):
        assert not (BASE / "embedder.py").exists()


class TestGitignore:
    """Verify .gitignore includes production artifacts."""

    def test_gitignore_has_certs(self):
        content = (BASE / ".gitignore").read_text()
        assert "certs/" in content

    def test_gitignore_has_backups(self):
        content = (BASE / ".gitignore").read_text()
        assert "backups/" in content

    def test_gitignore_has_dump(self):
        content = (BASE / ".gitignore").read_text()
        assert "*.dump" in content
