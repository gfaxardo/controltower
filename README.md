# YEGO Control Tower

Plataforma de inteligencia operacional para monitoreo de flotas de ride-hailing.

## Stack

| Capa | Tecnología |
|------|-----------|
| Frontend | React 18 + Vite 5 + TailwindCSS 3 + ECharts 6 |
| Backend | FastAPI (Python) + Uvicorn |
| DB | PostgreSQL |
| Deploy | Nginx + systemd |

## Arquitectura

El proyecto se organiza en **9 motores arquitectónicos** de madurez operacional. Actualmente en **Control Foundation** (ACTIVE). Ver:

- [Documentación de arquitectura canónica](docs/architecture/ARCHITECTURE_CANONICAL_ROADMAP.md)
- [Índice de documentación](docs/index.md)

## Desarrollo

```bash
# Backend
cd backend
pip install -r requirements.txt
python run_server.py

# Frontend
cd frontend
npm install
npm run dev
```

O usar el launcher:
```bash
bash dev.sh
```
