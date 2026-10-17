# Security Policy

## Supported versions

Only the latest commit on the default branch is supported for security fixes.

## Reporting

Please report suspected vulnerabilities privately to the repository owner instead of opening a public issue containing customer data, images, credentials, or exploitation details.

## Deployment boundaries

- This repository is a single-node reference implementation, not a certified medical product.
- Session cookies are scoped to the active `APP_PROFILE`, and profile data uses separate database files.
- Keep `APP_BIND=127.0.0.1` unless access is protected by HTTPS, authentication, and network controls.
- Use a unique `ADMIN_TOKEN` and `SESSION_SECRET`. Never commit `.env`.
- Review every configured `TEXT_BASE_URL`, `VISION_BASE_URL`, endpoint override, SDK, and custom Provider before processing customer data.
- Set `TEXT_PRIVACY_MODE` and `VISION_PRIVACY_MODE` to match the real network path; `local` is a deployment claim, not an automatic security guarantee.
- Custom Provider factories execute in the application process. Install and review only trusted code.
- Do not commit customer databases, chat checkpoints, screenshots containing real people, downloaded datasets, or third-party product packshots.
- Delete customer data when it is no longer needed. The API supports customer deletion, but database backups and checkpoints may retain older copies.
