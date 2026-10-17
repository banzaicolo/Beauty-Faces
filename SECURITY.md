# Security Policy

## Supported versions

Only the latest commit on the default branch is supported for security fixes.

## Reporting

Please report suspected vulnerabilities privately to the repository owner instead of opening a public issue containing customer data, images, credentials, or exploitation details.

## Deployment boundaries

- This repository is a single-node reference implementation, not a certified medical product.
- Keep `APP_BIND=127.0.0.1` unless access is protected by HTTPS, authentication, and network controls.
- Use a unique `ADMIN_TOKEN` and `SESSION_SECRET`. Never commit `.env`.
- Only use a trusted `OLLAMA_URL`. An apparently local interface may still send prompts to a remote host if configured that way.
- Enabling `DEEPSEEK_API_KEY` sends text prompts and customer report context to an external service.
- Do not commit customer databases, chat checkpoints, screenshots containing real people, downloaded datasets, or third-party product packshots.
- Delete customer data when it is no longer needed. The API supports customer deletion, but database backups and checkpoints may retain older copies.
