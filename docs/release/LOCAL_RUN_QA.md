# LOCAL RUN QA

**Date**: 2026-05-25

## COMMANDS

### Terminal 1 — Backend
```powershell
cd C:\cursor\controltower\controltower\backend
python -m uvicorn app.main:app --reload --port 8001
```

### Terminal 2 — Frontend
```powershell
cd C:\cursor\controltower\controltower\frontend
npm run dev
```

### Browser
```
http://localhost:5173/
```

### Hard refresh
```
Ctrl + Shift + R
```

## EXPECTED

- Vite proxy: 5173 → 8001
- No ECONNREFUSED
- Omniview loads at /operacion/omniview-matrix
- Weekly loads at /performance/plan-vs-real
- Loyalty loads at /performance/yango-loyalty

## VERDICT: Ready for local test
