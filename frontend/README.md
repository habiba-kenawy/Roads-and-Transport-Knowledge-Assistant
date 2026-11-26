# TAREEQ frontend

React + TypeScript page for the Roads and Transport Knowledge Assistant. It only calls the backend API (`/chat`, `/chat/resume`, `/search`);
there is no business logic here. The backend setup is in the [root README](../README.md).

## Run

```
cd frontend
npm install
copy .env.example .env        (macOS/Linux: cp .env.example .env)
npm run dev                   http://localhost:5180
```

The API must be running (default `http://127.0.0.1:8010`). `VITE_API_BASE_URL` in `.env` is its address; the app refuses to start without it.
The page's own address must be in the backend's `CORS_ORIGINS` (default `http://localhost:5180`; the dev server uses `strictPort` so it can never
drift to a port the backend refuses).

## Scripts

| Command                           | What it does                                                    |
| --------------------------------- | --------------------------------------------------------------- |
| `npm run dev`                     | dev server with hot reload                                      |
| `npm run build`                   | type-check, then bundle into `dist/`                            |
| `npm run lint`                    | oxlint (React hooks, accessibility, correctness)                |
| `npm run format` / `format:check` | Prettier write / check                                          |
| `npm test`                        | Vitest: pure logic, the chat reducer and the API-contract check |

## Layout

```
src/
  api/          axios client, plain-language error mapping, contract.json (the API's shapes, written by the backend)
  hooks/        useChat (reducer: messages, saved conversations, clarification) and useSearch (Search Inspector)
  lib/          history (localStorage), citations ([n] markers), scores (score labels), options (composer choices)
  components/
    chat/       answer, user and error cards, loading card, source drawer, clarification box, start screen
    inspector/  Search Inspector results
    layout/     sidebar and past-conversation list
    ui/         shadcn/ui parts (generated; do not restyle by hand)
  types.ts      the API's request/response shapes, checked against api/contract.json by `npm test`
```

## Notes

- Past conversations are kept in the browser (`localStorage`), with each conversation's server `thread_id`. The server has no history endpoint.
- `src/types.ts` is kept by hand. After an API change, run `python -m scripts.export_openapi` in the repository root, then update `types.ts`
  until `npm test` passes. The backend's own test fails if `api/contract.json` is stale.
- Model and document text is always rendered as plain text, never as HTML.
