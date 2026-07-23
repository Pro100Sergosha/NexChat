# Frontend

Type: React + TypeScript SPA, built with Vite. CSS Modules per component.

Running:
- **Dev (docker-compose)**: the `gateway` service runs the Vite dev server with
  `./frontend` bind-mounted, so edits hot-reload live. It proxies `/api/*` and
  `/ws` to the `auth`/`chat` services (targets from env, see `vite.config.ts`).
  App at `http://localhost:5173`.
- **Prod**: `frontend/Dockerfile` builds the static bundle and serves it from
  Nginx (`nginx/nginx.conf`) with the same-origin reverse proxy — no CORS.

## Stack

- React 18 + TypeScript, `react-router-dom` for routing
- Vite build (`npm run build` → `dist/`), `npm run dev` for local dev
- Styling: CSS Modules (`*.module.css`) + design tokens in `src/styles/tokens.css`
- No global UI framework; the "Exchange" design system lives in tokens + modules
- JWT pair stored in localStorage (`nexchat.access_token` / `nexchat.refresh_token`)

## Layout

```
frontend/
  index.html            # Vite entry (loads IBM Plex fonts)
  vite.config.ts        # dev proxy: /api/auth→8000, /api/chat→8001, /ws→8001
  Dockerfile            # node build → nginx:alpine serving dist/
  src/
    main.tsx  App.tsx           # bootstrap + routes (/login, /)
    auth/AuthContext.tsx        # session state, signIn/signUp/signOut, useAuth
    core/                       # (named 'core', NOT 'lib' — root .gitignore drops lib/)
      types.ts                  # wire contracts + WS_CLOSE codes
      tokens.ts                 # localStorage token store
      api.ts                    # apiFetch (Bearer + refresh-on-401), ApiError
      auth.ts  chat.ts          # auth + chat REST calls
      ws.ts                     # ChatSocket: connect/send/reconnect/close-codes
      format.ts                 # shortId / time helpers
    hooks/useChatSocket.ts      # binds ChatSocket to React (status + send)
    pages/Login/  pages/Chat/   # page + its .module.css
    components/LineRail  LiveLine  Transcript  Composer  BootScreen
    styles/tokens.css  global.css
```

## Routing & auth

- `/login` — sign in / register (OAuth2 password form: `username` = email).
- `/` — chat, guarded by auth phase; anon users are redirected to `/login`.
- `apiFetch` attaches the access token and, on a 401, does one silent
  `/refresh` + retry; if that fails it clears tokens and the router bounces to
  `/login`. WS 4401 triggers the same refresh-once-then-reconnect path.

## Same-origin paths (via Nginx / Vite proxy)

- `POST /api/auth/register|login|refresh|logout`, `GET /api/auth/me`
- `GET /api/chat/conversations`, `GET /api/chat/messages/{id}`
- `POST /api/chat/conversations` — create a group `{name, participant_ids[]}`;
  `POST|DELETE /api/chat/conversations/{id}/participants` (owner only),
  `POST /api/chat/conversations/{id}/leave`.
- `WS /ws?token=<access>` — client sends `{content, conversation_id|recipient_id}`
  (`recipient_id` is 1:1 only; groups are always addressed by `conversation_id`),
  server echoes/broadcasts `MessageOut` to every participant. Close codes: 4401
  auth, 4403 not participant, 4422 bad frame.

## Design — "Exchange"

Telephone-exchange console: conversations are "lines" on a patch panel.
Warm charcoal + brass (structure) + a live cyan current. Signature is the
**live line** in the conversation header — cyan+glowing while the WebSocket is
open, dim brass dashes when it isn't; a pulse travels it only when a message is
sent. Messages render as a teletype transcript (squared, tick-marked), not
chat pills. IBM Plex Mono (data/labels) + IBM Plex Sans (message body).

## Rules

- No user directory in the backend → "new line" = paste the other party's UUID;
  we surface the caller's own id (from `/me`) for sharing. Don't invent search.
- Conversations are 1:1 **or group**. A group is created with a name + a list of
  pasted participant UUIDs (same no-directory constraint — paste ids, no search).
  Only the group's `owner_id` may add/remove participants or rename; any member
  may leave. 1:1 lines have no name and no membership controls — render them as
  before; group affordances (name, member list, add/leave) appear only when
  `is_group`.
- Keep design tokens in `tokens.css`; components consume CSS vars, never
  hardcode palette hexes in `*.module.css`.
- Any new WS close code or error `code` must be mirrored in `core/types.ts`.