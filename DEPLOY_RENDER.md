# Deploy Blxlerator publicly on Render

This build is a single Docker web service: React frontend + FastAPI backend + the existing Python Qlik-to-Power BI engines.

## 1. Put this folder in a Git repository

Create a private GitHub/GitLab repository and upload the contents of this folder. Do **not** commit `.env`, API keys, client data, `uploads/`, `output_data/`, logs, or the SQLite database.

## 2. Create the Render service

In Render: New → Web Service → connect the repository. Choose Docker. Render will use the included `Dockerfile` and `render.yaml` settings. The health check is `/api/health`.

## 3. Add secrets

In the Render service Environment settings, add:

- `BLXLERATOR_LLM_API_KEY`
- `BLXLERATOR_IMAGE_API_KEY`

The non-secret API URLs/models are already defined in `render.yaml`.

## 4. Deploy

Render builds the React application inside Docker, installs the Python dependencies, starts FastAPI, and serves the React application from the same public service.

The resulting URL will be similar to:

`https://blxlerator-<generated-name>.onrender.com`

You can optionally attach a custom domain later.

## Important for public sharing

This deployment intentionally has no login/SSO layer because the current product scope is the six Qlik-to-Power BI capabilities only. Do not upload confidential customer/client data to a public deployment until your organization's security/privacy approval and access-control requirements are satisfied.

For a public demo, use synthetic/sample Qlik files.
