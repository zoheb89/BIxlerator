# Blxlerator — Production React + FastAPI Build

Blxlerator is an enterprise UI for the existing Qlik-to-Power BI Python engines.

## Architecture
React / TypeScript UI → FastAPI → existing Python engines

Connected capabilities:
- QVD → CSV
- GenAI-assisted PII classification
- Fernet PII protection / unmasking
- Qlik → DAX
- Qlik Script → Python
- Documentation generation
- Generative Power BI wireframe generation

## PII positioning
The supplied PII engine performs GenAI-assisted classification from CSV column metadata. It does not inspect row values and should not be marketed as ML-based PII detection without a separate ML/value-level detector.

## Configuration
Copy `.env.example` to `.env` and add approved enterprise API credentials. Do not commit `.env`.

## Local development
Backend:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173`.

## Production
```bash
cd frontend
npm install
npm run build
cd ..
uvicorn main:app --host 0.0.0.0 --port 8000
```

Or:
```bash
docker compose up --build
```

## API
- `GET /api/health`
- `GET /api/dashboard`
- `POST /api/qvd/convert`
- `POST /api/dax/convert`
- `POST /api/script/convert`
- `POST /api/docs/generate`
- `POST /api/pii/scan`
- `POST /api/pii/mask`
- `POST /api/pii/unmask`
- `POST /api/uiux/generate`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/download`
- `GET /api/docs`

## Enterprise hardening
For a true multi-instance enterprise deployment, replace the in-process job executor and SQLite activity store with Redis + Celery/RQ and PostgreSQL, use object storage for artifacts, enterprise SSO/OIDC, audit logging, malware scanning, rate limits, request IDs, and a managed secrets vault.
