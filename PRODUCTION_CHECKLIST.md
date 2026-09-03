# Blxlerator Production Deployment Checklist

## Scope
Qlik → Power BI migration only. The deployed application preserves the six existing capabilities:
1. QVD → CSV
2. GenAI-assisted PII classification / PII Shield
3. Qlik Expressions → Power BI DAX
4. Qlik Load Script → Python
5. Documentation Generator
6. Power BI UI/UX Design Generator

## Pre-deployment
- Set `BLXLERATOR_LLM_API_KEY` in Render.
- Set `BLXLERATOR_IMAGE_API_KEY` in Render.
- Verify configured API URLs/models.
- Keep `BLXLERATOR_WORKERS=1` for the current in-process job registry.
- Use synthetic data for public demonstrations until organizational security/privacy approval is complete.

## Deployment
- Render service type: Web Service / Docker.
- Health check: `/api/health`.
- The Docker image builds the React frontend and serves it from FastAPI.
- Render supplies the runtime `PORT`; Uvicorn binds to `0.0.0.0`.

## Validation
- Open `/api/health` and confirm `status=ok`.
- Open the application root and verify the BIxlerator/Capgemini logo.
- Test one representative file through each of the six existing workspaces.
- Confirm job status changes to completed and output download works.
- For PII Shield, securely retain the one-time encryption key returned by the protection request; the job-status endpoint does not persist the key.
