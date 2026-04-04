# Deploying Engram on a Windows Server (Home LAN)

This guide deploys the full Engram stack on a Windows server so every device on your home network can access the REST API, MCP server, and React dashboard.

## Prerequisites

- **Windows 10/11 Pro or Server** with WSL2 enabled
- **Docker Desktop for Windows** (with WSL2 backend)
- **Git** installed
- A static LAN IP for the server (e.g., `192.168.1.100`), or a hostname

## 1. Install Docker Desktop

1. Download from https://www.docker.com/products/docker-desktop/
2. During install, enable **WSL2 backend**
3. After install, open Docker Desktop and verify it's running
4. (Optional) Enable GPU support: Settings → Resources → WSL Integration → enable for your distro

## 2. Clone and Configure

Open PowerShell or WSL terminal:

```powershell
git clone https://github.com/jblacketter/engram.git
cd engram
copy .env.example .env
```

Edit `.env` with your production settings:

```ini
DJANGO_SECRET_KEY=<generate-a-random-64-char-string>
DJANGO_SETTINGS_MODULE=engram.settings.production
POSTGRES_DB=engram
POSTGRES_USER=engram
POSTGRES_PASSWORD=<strong-password>
POSTGRES_HOST=db
POSTGRES_PORT=5432
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_CHAT_MODEL=llama3.2:3b

# Set API keys for production security
MCP_API_KEY=<your-mcp-key>
REST_API_KEY=<your-rest-key>

# LAN access: add your server's LAN IP
ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.100,engram.local
CORS_ALLOWED_ORIGINS=http://192.168.1.100,https://192.168.1.100
```

Replace `192.168.1.100` with your server's actual LAN IP.

## 3. Generate TLS Certificates (Optional but Recommended)

For HTTPS on the LAN:

```powershell
mkdir -p nginx/certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/certs/key.pem \
  -out nginx/certs/cert.pem \
  -subj "/CN=engram.local"
```

If you skip this, edit `docker-compose.prod.yml` to remove the TLS listener and use port 80 only.

## 4. Deploy

```powershell
docker compose -f docker-compose.prod.yml up -d
```

This starts:
- **nginx** (ports 80 + 443) — reverse proxy, serves dashboard
- **django** (port 8000 internal) — REST API via gunicorn
- **mcp** (port 8080 internal) — MCP server
- **db** — PostgreSQL 16 + pgvector
- **ollama** — embedding + chat model

## 5. Pull the Embedding Model

```powershell
docker compose -f docker-compose.prod.yml exec ollama ollama pull nomic-embed-text
```

(Optional) Pull the chat model for auto-enrichment:

```powershell
docker compose -f docker-compose.prod.yml exec ollama ollama pull llama3.2:3b
```

## 6. Run Migrations

```powershell
docker compose -f docker-compose.prod.yml exec django python manage.py migrate
```

## 7. Open Windows Firewall

Allow other LAN devices to reach the server:

```powershell
# Run PowerShell as Administrator
New-NetFirewallRule -DisplayName "Engram HTTP" -Direction Inbound -Port 80 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Engram HTTPS" -Direction Inbound -Port 443 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Engram MCP" -Direction Inbound -Port 8080 -Protocol TCP -Action Allow
```

## 8. Verify

From any device on your LAN:

| Service | URL |
|---------|-----|
| Dashboard | `http://192.168.1.100/` |
| REST API | `http://192.168.1.100/api/memories/` |
| API Docs | `http://192.168.1.100/api/docs/` |
| MCP Server | `http://192.168.1.100/mcp/` |
| Health Check | `http://192.168.1.100/api/health/` |

## 9. Connect AI Clients on the LAN

### Claude Code (from any machine on LAN)

```bash
claude mcp add engram http://192.168.1.100/mcp/ --header "Authorization: Bearer <your-mcp-key>"
```

### Claude Desktop

Add to your MCP config:

```json
{
  "mcpServers": {
    "engram": {
      "url": "http://192.168.1.100/mcp/",
      "headers": {
        "Authorization": "Bearer <your-mcp-key>"
      }
    }
  }
}
```

## Troubleshooting

**Docker won't start:** Ensure WSL2 is enabled (`wsl --install` in PowerShell as admin), then restart Docker Desktop.

**Can't reach from other devices:** Check firewall rules (step 7), verify the server's LAN IP with `ipconfig`, and ensure the devices are on the same subnet.

**Ollama GPU not working:** Docker Desktop → Settings → Resources → WSL Integration. Ensure your NVIDIA drivers are installed in Windows and the `deploy.resources.reservations` section in `docker-compose.prod.yml` matches your GPU.

**Slow embedding on first use:** The first `store_memory` call downloads the model to the Ollama container. Subsequent calls use the cached model.

## Updating

```powershell
cd engram
git pull
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec django python manage.py migrate
```
