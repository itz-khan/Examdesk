# Cloud deployment: Render, Neon, and Vercel

This deploys the API to Render, PostgreSQL to Neon, and the React/TypeScript
frontend to Vercel. The free plans are suitable for a class demo, but can sleep
or have usage limits. Check each provider's current pricing before creating
resources.

## 1. Create the hosted database

1. Create a PostgreSQL project in [Neon](https://neon.tech/).
2. Copy its connection string and keep it private.
3. Paste the connection string into Render's `DATABASE_URL` setting as Neon
   provides it. The backend converts standard `postgresql://` and `postgres://`
   URLs to the async SQLAlchemy driver and uses `DATABASE_SSL` for TLS, so
   libpq-only query options such as `sslmode` and `channel_binding` are removed.

Do not paste database credentials into source files or commit them.

## 2. Deploy the API

1. Push the project to a GitHub repository you control.
2. In Render, choose **New → Blueprint**, connect that repository, and select
   `render.yaml` at the repository root.
3. When prompted for `DATABASE_URL`, paste the Neon connection string as-is.
4. Review the blueprint and create the service. The API health check is
   `/ready`; it verifies database connectivity.
5. Copy the deployed service's HTTPS URL, for example
   `https://examdesk-api.onrender.com`.

The API initializes missing tables when it starts. This project does not yet
have usable Alembic migration revisions, so this is intended for a demo rather
than production schema management. It does not seed demo users automatically;
create an account through the app's registration page.

## 3. Deploy the frontend

1. In Vercel, import the same GitHub repository.
2. Set the project root directory to `frontend`.
3. Add the environment variable:
   `VITE_API_BASE_URL=https://examdesk-api.onrender.com/api/v1`
   Replace the hostname with the actual Render URL. Set it for Production (and
   Preview if needed) before deploying.
4. Deploy, open the Vercel site, and register an account to verify the API.

The backend already allows Vercel origins whose host starts with `examdesk`.
If the generated Vercel domain has a different name, add its exact HTTPS origin
to `ALLOWED_ORIGINS` in Render using JSON array syntax, for example:
`["https://your-project.vercel.app"]`, then redeploy the API.

## Important

- Never use the local demo account passwords on a public deployment.
- Keep `DATABASE_URL`, `SECRET_KEY`, and `CERT_SECRET_KEY` in provider
  environment settings only.
- The Render free service may take a short time to wake after inactivity.
- Cloud setup is separate from the local two-backend load-balancer demo.
