# Demo Checklist

Quick reference for bringing the project up from a cold machine (everything
closed — Docker Desktop quit, all terminals closed) to ready-to-present.

## 1. Check if anything's already running

Closing terminal windows does **not** stop Docker containers — they run as
background daemon processes independent of the terminal that started them.
Only quitting Docker Desktop entirely, or running `docker compose down`,
actually stops them.

```bash
docker ps --filter name=llmrouter
```

If both containers show as `Up`, skip to step 4.

## 2. Make sure Docker Desktop is running

If Docker Desktop was fully quit, `docker` commands fail until it's back up.
Open Docker Desktop and wait until the whale icon in the menu bar is steady
(not animating) — usually 15–30 seconds.

## 3. Bring the stack up

```bash
docker compose up -d --build
```

Starts both containers (router + MongoDB) in the background. Takes ~10–15
seconds since the image is already built.

## 4. Verify it's healthy

```bash
curl http://127.0.0.1:8000/health
```

Expect `{"status":"ok"}`. If you get "connection refused," wait 5 more
seconds — the container needs a moment to load the classifier model on
startup.

## 5. Send one test query before the audience arrives

Confirms the OpenAI API key/billing is still good, before anyone's watching:

```bash
curl -X POST http://127.0.0.1:8000/route -H "Content-Type: application/json" -d '{"query": "What is the capital of Japan?"}'
```

A real answer back (not an error) means you're ready.

## 6. Open the browser tabs

```
http://127.0.0.1:8000/          # interactive demo — start here
http://127.0.0.1:8000/dashboard # cost-savings dashboard
```

**Tip:** if it's been a while since the last test batch, the dashboard may
look stale or empty. Click 3–4 of the example chips on the demo page first
(mix of easy and hard queries) so the dashboard has fresh data to show.

## Shutting down afterward (optional)

```bash
docker compose stop
```

Stops the containers without deleting them or the logged data — next time,
`docker compose up -d` starts them right back up instantly, no rebuild
needed.
