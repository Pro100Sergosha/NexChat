# Frontend

Type: Static HTML/JS (no framework, no build step)
Served by: Nginx

## Files

| File | Purpose |
|---|---|
| `index.html` | Login / registration page |
| `chat.html` | Chat UI (conversations list + message area) |
| `main.js` | API calls + WebSocket client logic |

## Rules

- No bundler, no npm — plain browser JS
- JWT stored in localStorage
- WebSocket connects to `/ws?token=<jwt>` via Nginx proxy
- On 401 response → redirect to index.html
