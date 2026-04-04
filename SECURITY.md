# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in Engram, please report it responsibly:

1. **Do not** open a public GitHub issue.
2. Email **security@engram.dev** (or open a private GitHub Security Advisory on this repo).
3. Include a description of the vulnerability, steps to reproduce, and any potential impact.
4. We will acknowledge receipt within 48 hours and aim to release a fix within 7 days for critical issues.

## Security Considerations

- **API Keys**: Set `REST_API_KEY` and `MCP_API_KEY` in production. When empty, endpoints are unauthenticated.
- **SSRF Protection**: The URL ingestion endpoint validates URLs and blocks private/internal network ranges.
- **TLS**: Production Docker Compose includes nginx with TLS. Always use HTTPS in production.
- **Database**: Use strong `POSTGRES_PASSWORD` values. The default dev credentials are for local development only.
- **Django Secret Key**: Always set a unique `DJANGO_SECRET_KEY` in production.
