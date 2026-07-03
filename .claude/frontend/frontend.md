# Frontend

Type: React + TypeScript SPA, built with Vite. CSS Modules per component.
Served as a static bundle by Nginx (the `gateway` service), which also
reverse-proxies the two backends on the same origin (no CORS).

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
- `WS /ws?token=<access>` — client sends `{content, conversation_id|recipient_id}`,
  server echoes/broadcasts `MessageOut`. Close codes: 4401 auth, 4403 not
  participant, 4422 bad frame.

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
- Conversations are strictly 1:1 — don't build group-chat affordances.
- Keep design tokens in `tokens.css`; components consume CSS vars, never
  hardcode palette hexes in `*.module.css`.
- Any new WS close code or error `code` must be mirrored in `core/types.ts`.