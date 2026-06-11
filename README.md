# Notion GitHub Sync

Service Python untuk two-way synchronization antara Notion database dan GitHub Issues.

## Fitur

### Notion → GitHub (Polling)
- Polling Notion database setiap N detik (configurable via `POLL_INTERVAL`)
- Otomatis membuat GitHub Issue dari tiket Notion dengan status trigger + GitHub Issue Number kosong
- Membuat label GitHub otomatis berdasarkan field `Tipe` dan `Prioritas` (auto-create jika belum ada)
- Update balik Notion dengan nomor issue, URL, dan status sukses
- Repository tujuan diambil dari field `Modul` di Notion

### GitHub → Notion (Webhook)
- Menerima event dari GitHub Webhook (`issues` event)
- Developer assigned → Notion Status = `Assigned`
- Label `in progress` → Notion Status = `In progress`
- Label `in review` → Notion Status = `In Review`
- Label `blocked` → Notion Status = `Blocked`
- Label `done` → Notion Status = `Done`
- Issue closed → Notion Status = `Closed`
- Issue reopened → Notion Status = `GitHub Issue Created`

### Umum
- Retry dengan exponential backoff untuk Notion API & GitHub API (3x, via tenacity)
- HMAC-SHA256 signature verification untuk webhook
- Structured logging ke console + rotating file (`logs/app.log`)
- Graceful shutdown dengan `Ctrl+C`
- Docker-ready

---

## Prasyarat

- Python 3.12+
- Notion Integration Token (read + update content access ke database target)
- GitHub Personal Access Token (classic) dengan scope `repo`
- Docker & Docker Compose (opsional)
- **Webhook**: Server dengan IP publik / domain, atau ngrok untuk local development

---

## Setup

### 1. Clone repository

```bash
git clone <repo-url>
cd notion-github-sync
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment Variables

Salin `.env.example` menjadi `.env`:

```bash
cp .env.example .env
```

Isi file `.env`:

```env
NOTION_TOKEN=ntn_xxxxxxxxxxxx
NOTION_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
GITHUB_ORG=PT-SILK
POLL_INTERVAL=60
LOG_LEVEL=INFO
NOTION_TRIGGER_STATUS=Ready For Engineering
NOTION_SUCCESS_STATUS=GitHub Issue Created
WEBHOOK_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
WEBHOOK_HOST=[IP_ADDRESS]
WEBHOOK_PORT=5000
```

---

## Environment Variables

| Variable               | Deskripsi                                              | Default                     |
|------------------------|--------------------------------------------------------|-----------------------------|
| `NOTION_TOKEN`         | Notion Integration Token                               | *(wajib)*                   |
| `NOTION_DATABASE_ID`   | ID database Notion                                     | *(wajib)*                   |
| `GITHUB_TOKEN`         | GitHub Personal Access Token (scope: `repo`)            | *(wajib)*                   |
| `GITHUB_ORG`           | GitHub Organization / username pemilik repository       | `PT-SILK`                   |
| `POLL_INTERVAL`        | Interval polling Notion (detik)                        | `60`                        |
| `LOG_LEVEL`            | Level logging (`DEBUG`, `INFO`, `WARNING`, `ERROR`)     | `INFO`                      |
| `NOTION_TRIGGER_STATUS` | Status Notion yang mentrigger pembuatan issue           | `Ready For Engineering`     |
| `NOTION_SUCCESS_STATUS` | Status Notion setelah issue berhasil dibuat             | `GitHub Issue Created`      |
| `WEBHOOK_SECRET`       | Secret untuk verifikasi HMAC-SHA256 dari GitHub Webhook | `""` (optional)             |
| `WEBHOOK_HOST`         | IP/Domain publik server ini                             | `[IP_ADDRESS]`              |
| `WEBHOOK_PORT`         | Port untuk Flask HTTP server                            | `5000`                      |

---

## Cara Menjalankan (Tanpa Docker)

```bash
cd notion-github-sync
python app.py
```

Service berjalan:
1. **Polling loop** di main thread (Notion → GitHub)
2. **Webhook server** di background thread (GitHub → Notion) di `WEBHOOK_HOST:WEBHOOK_PORT`

Tekan `Ctrl+C` untuk menghentikan.

---

## GitHub Webhook Setup

### Di Server Produksi

1. Set `WEBHOOK_HOST` ke IP publik / domain server
2. Set `WEBHOOK_SECRET` ke random string (minimal 20 karakter):
   ```bash
   openssl rand -hex 32
   ```
3. Jalankan service: `python app.py`
4. Di GitHub repository → **Settings** → **Webhooks** → **Add webhook**:
   - **Payload URL**: `http://<WEBHOOK_HOST>:5000/webhook`
   - **Content type**: `application/json`
   - **Secret**: paste value `WEBHOOK_SECRET`
   - **Events**: `Let me select individual events` → centang **Issues**
   - **Active**: ✅

### Untuk Local Development (ngrok)

```bash
# Install ngrok
brew install ngrok

# Jalankan service dulu
python app.py

# Di terminal lain, expose port 5000
ngrok http 5000

# Dapatkan URL publik: https://abc123.ngrok-free.app
# Update .env: WEBHOOK_HOST=abc123.ngrok-free.app
# (Pembuatan webhook sama seperti di atas, gunakan URL ngrok)
```

---

## Cara Menjalankan (Dengan Docker)

### Build & Run

```bash
docker compose up -d
```

Menghentikan:

```bash
docker compose down
```

Melihat log:

```bash
docker compose logs -f
```

### Manual Docker

```bash
docker build -t notion-github-sync .
docker run -d \
  --name notion-github-sync \
  --restart unless-stopped \
  --env-file .env \
  -p 5000:5000 \
  -v "$(pwd)/logs:/app/logs" \
  notion-github-sync
```

---

## Workflow Status Mapping

### Notion → GitHub (Polling)

| Notion Status (trigger)     | GitHub Action              | Notion Status (hasil)     |
|-----------------------------|----------------------------|---------------------------|
| `NOTION_TRIGGER_STATUS`     | Create Issue + Labels      | `NOTION_SUCCESS_STATUS`   |

### GitHub → Notion (Webhook)

| GitHub Event        | Notion Status              |
|---------------------|----------------------------|
| `assigned`           | `Assigned`                 |
| `labeled: in progress`| `In progress`             |
| `labeled: in review` | `In Review`                |
| `labeled: blocked`   | `Blocked`                  |
| `labeled: done`      | `Done`                     |
| `closed`            | `Closed`                   |
| `reopened`          | `GitHub Issue Created`     |
| `unlabeled` (status label removed) | `In progress`   |

---

## Testing

### Test Notion → GitHub Sync

1. Buat page di Notion database dengan:
   - Status: `GitHub Issue Created` (atau sesuai `NOTION_TRIGGER_STATUS`)
   - GitHub Issue Number: *(kosong)*
   - Judul + field lainnya diisi
2. Jalankan service
3. Amati log:
   ```
   2026-06-10 14:11:39 INFO Creating issue in PT-SILK/notion_github_sync: <Judul>
   2026-06-10 14:11:41 INFO Issue created #1 in PT-SILK/notion_github_sync
   2026-06-10 14:11:42 INFO Notion page xxx updated successfully
   ```
4. Verifikasi:
   - GitHub Issue terbuat
   - Notion: GitHub Issue Number, URL, Status ter-update

### Test GitHub → Notion Webhook

1. Setup webhook di GitHub (lihat section GitHub Webhook Setup)
2. Assign developer ke issue → Notion Status = `Assigned`
3. Tambah label `in progress` → Notion Status = `In progress`
4. Close issue → Notion Status = `Closed`

### Test Webhook Endpoint (cURL)

```bash
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: issues" \
  -d '{"action":"closed","issue":{"html_url":"https://github.com/PT-SILK/notion_github_sync/issues/1"}}'
```

---

## Struktur Folder

```
notion-github-sync/
│
├── app.py                     # Entry point (webhook + polling)
├── config.py                  # Konfigurasi aplikasi (dataclass)
├── requirements.txt           # Python dependencies
├── README.md                  # Dokumentasi
├── .env.example               # Template environment variables
│
├── clients/
│   ├── notion_client.py       # Notion API: query, parse, update, find by URL
│   └── github_client.py       # GitHub API: create issue, auto-create labels
│
├── services/
│   └── sync_service.py        # Core sync logic + repo name cleaner
│
├── webhooks/
│   ├── server.py              # Flask HTTP server (webhook endpoint)
│   └── handler.py             # Event handler + status mapping
│
├── utils/
│   ├── formatter.py           # Issue body markdown + labels builder
│   └── logger.py              # Structured logging (console + file)
│
├── logs/                      # Log files (mounted di Docker)
│
├── Dockerfile                 # python:3.12-slim
│
└── docker-compose.yml         # restart: unless-stopped, ports 5000:5000