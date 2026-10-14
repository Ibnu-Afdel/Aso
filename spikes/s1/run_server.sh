#!/bin/sh
# restart the spike server; pid kept in server.pid
[ -f server.pid ] && kill "$(cat server.pid)" 2>/dev/null
for p in $(pgrep -f "uvicorn app:app --port 8765"); do kill $p 2>/dev/null; done
sleep 1
uv run --project .. uvicorn app:app --port 8765 --log-level warning > server.log 2>&1 &
echo $! > server.pid
until curl -s -o /dev/null 127.0.0.1:8765/posts; do sleep 0.5; done
