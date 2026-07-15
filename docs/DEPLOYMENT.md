# Deployment Guide

Athena is designed to be lightweight and easily deployable via Docker or native Python environments. This guide covers deploying Athena to modern cloud platforms like Render and Railway.

## General Requirements

- **Environment Variables**:
  - `ATHENA_ENV=production`
  - `ATHENA_PROVIDER` (e.g., `openai`, `claude`, `demo`)
  - Provider API keys if applicable (e.g., `OPENAI_API_KEY`)
- **Port**: Athena runs on port `8501`. Ensure your platform exposes this port.

---

## Deploying on Render

Render makes it incredibly easy to deploy Dockerized applications.

1. **Connect your Repository**: Log into the [Render Dashboard](https://dashboard.render.com/) and click **New > Web Service**.
2. **Select GitHub**: Connect your GitHub account and select the Athena repository.
3. **Configuration**:
   - **Name**: `athena-intelligence` (or similar)
   - **Environment**: `Docker` (Render will automatically detect the `Dockerfile` in the root).
   - **Region**: Choose the region closest to you.
4. **Environment Variables**:
   - Click **Advanced** -> **Add Environment Variable**.
   - Add `ATHENA_ENV` = `production`.
   - Add your API keys if you wish to use the real providers (e.g., `ANTHROPIC_API_KEY`).
5. **Deploy**: Click **Create Web Service**. Render will build the Docker image and deploy it.

---

## Deploying on Railway

Railway is another excellent platform for quick Docker deployments.

1. **Create a Project**: Log into the [Railway Dashboard](https://railway.app/) and click **New Project**.
2. **Deploy from GitHub**: Select **Deploy from GitHub repo** and choose the Athena repository.
3. **Configure Variables**:
   - Once the project initializes, click on the service card, navigate to the **Variables** tab.
   - Add `ATHENA_ENV` = `production`.
   - Add `PORT` = `8501` (Railway uses the PORT variable to determine where to route traffic).
   - Add any necessary API keys.
4. **Deploy**: Railway will automatically detect the Dockerfile, build, and deploy the application.

---

## Local Docker Compose

For local testing in a production-like environment, simply use Docker Compose:

```bash
docker-compose up --build
```
This will spin up Athena locally on `http://localhost:8501`.
