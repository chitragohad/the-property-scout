# n8n — Shortlist PDF / email workflow

Property Scout posts the shortlist export payload to `N8N_WEBHOOK_URL`. This workflow receives it, builds an HTML email, and sends it to the recipient.

## 1. Configure Property Scout

In the repo root `.env`:

```env
N8N_WEBHOOK_URL=https://<your-workspace>.app.n8n.cloud/webhook/property-scout-shortlist
```

Restart the API after changing `.env` so settings reload.

## 2. Import & activate in n8n Cloud

1. Open [n8n Cloud](https://app.n8n.cloud/) → **Workflows** → **Import from File**
2. Import `integrations/n8n/shortlist_email_workflow.json`
3. Open the **Send Email** node and attach SMTP or Gmail credentials
4. Toggle the workflow **Active** (top right)
5. Confirm the production webhook URL matches `.env`:
   - `https://<workspace>.app.n8n.cloud/webhook/property-scout-shortlist`
   - Path must be exactly `property-scout-shortlist`

## 3. Test

From the app: complete a shortlist → **Email this shortlist** → enter your inbox.

Or with curl (after a search session has listings):

```bash
curl -s -X POST http://localhost:8000/session/<session_id>/export \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com"}'
```

Expected API response when delivery succeeds:

```json
{ "ok": true, "delivered": true, "message": "Your shortlist is on its way to you@example.com." }
```

Sample payload shape: `sample_payload.json`.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| API says local export only | `N8N_WEBHOOK_URL` empty or API not restarted |
| HTTP 404 from webhook | Workflow inactive or wrong path |
| Email not arriving | Configure SMTP/Gmail on **Send Email**; check n8n Executions |
| API error but shortlist kept | Retry from UI; shortlist is not cleared on failure |
