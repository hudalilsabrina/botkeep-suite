# Botkeep Suite

Factory akun **Botkeep** (free hosting) + panen **API key** otomatis.
Signup → plan **Founder Free** (gratis selamanya) → API key `bk_live_...`.

## Cara kerja

```
1. buat inbox temp-mail (tempik)
2. buka https://botkeep.cloud/register
3. centang Terms → isi Display name + Email + Password (min 12 char)
4. Create account  → langsung masuk /app, plan Founder Free aktif
5. /app/developer → Generate API key (scoped) → secret bk_live_...
6. simpan ke accounts.txt
```

**Tanpa** captcha, verifikasi email, atau Discord.

## Founder Free (plan gratis)

| Resource | Jumlah |
|---|---|
| Hosting slots | 5 |
| RAM | 2 GB |
| CPU | 1.5 vCore |
| Storage | 2 GB |
| Backup | 2 (retensi 14 hari) |
| Expiry | tidak ada (free forever) |

## Instalasi

```bash
python3 -m venv .venv
.venv/bin/pip install rich requests patchright
.venv/bin/patchright install chromium

cp config.example.toml config.toml   # isi endpoint tempmail Anda
```

## Command

```bash
./run.sh harvest 1            # buat 1 akun + panen API key
./run.sh harvest 5            # 5 akun
./run.sh harvest 1 --no-proxy # tanpa proxy
./run.sh test                 # uji semua API key (GET /plan)
./run.sh report               # ringkasan akun
./run.sh workloads            # daftar workload tiap akun
./run.sh probe                # cek API hidup
```

Batch dengan rotasi proxy:

```bash
.venv/bin/python batch.py 10 --proxy-file proxies.txt --delay 12
```

## ⚠️ Penting: limit 1 akun per IP

Server Botkeep menolak pendaftaran kedua dari IP yang sama:

```
409  "Another account may already exist for this connection or browser."
```

**Wajib pakai proxy residensial** (rotating) untuk batch. Proxy datacenter
sering ditolak; residensial berhasil.

## 🚀 Deploy server (terbukti jalan)

```bash
./run.sh deploy api-server-1          # deploy server Python contoh
./run.sh deploy myapp --port 32728    # listen di port tertentu
```

Hasil nyata: **server live di `https://xxxxx.bot-keep.xyz`** ✅

### Temuan penting deploy (semua terbukti)

1. **Buat workload TANPA `seedFiles`** — format `seedFiles` di `POST /workloads`
   rewel/tidak jelas. Buat kosong dulu, upload file menyusul.
2. **`POST /workloads/{id}/files/upload`**:
   - `path` **HARUS diawali `/`** (mis. `/main.py`) — tanpa slash → `Invalid file path`
   - `data` **HARUS base64** — teks mentah → `Invalid upload encoding`
   ```python
   {"path": "/main.py", "data": base64.b64encode(code.encode()).decode(), "overwrite": True}
   ```
3. **Port**: Botkeep assign **port acak** (lihat dashboard → Port, mis. `32728`).
   Server **harus listen di port itu** (atau baca env `PORT`). Hardcode 8080 → 503.
4. **Address**: `node1.botkeep.cloud` + port (dari dashboard).
5. **Domain publik**: `PUT /workloads/{id}/domain {"enabled": true}`
   → dapat `hostname` seperti `6wk3md.bot-keep.xyz` (propagasi ~20s).
6. **Rate limit**: `POST /workloads/{id}/actions` bisa balas
   `429 Developer API budget exceeded` — tunggu ~1 menit.

Helper: `src/deploy.py` (`create_workload`, `upload_file`, `action`, `enable_domain`, `deploy`).

## Developer API

Base: `https://api.botkeep.cloud/api/v1/developer`
Auth: header `Authorization: Bearer bk_live_...`
Write request butuh header **`Idempotency-Key`**.

Endpoint utama:

| Method | Path | Fungsi |
|---|---|---|
| GET | `/plan` | plan + limit |
| GET | `/workloads` | daftar server |
| POST | `/workloads` | buat server |
| POST | `/workloads/{id}/actions` | start/stop/restart |
| GET/PUT | `/workloads/{id}/environment` | env vars |
| POST | `/workloads/{id}/console/command` | eksekusi perintah |
| GET/PUT | `/workloads/{id}/file` `/files` | akses file |
| GET/POST | `/workloads/{id}/backups` | backup |
| GET/PUT | `/workloads/{id}/domain*` | domain (custom/wildcard) |
| GET | `/billing` `/projects` `/capabilities` | info |
| GET/POST | `/tickets` | support |

Spec lengkap: `GET /api/v1/developer/openapi.json`

Contoh:

```bash
curl -H "Authorization: Bearer bk_live_..." \
  "https://api.botkeep.cloud/api/v1/developer/plan"
```

## Format akun (`accounts.txt`)

```
email:password:apikey:plan
```

## ⚠️ Catatan

- **Promo deadline:** Founder Free sampai 15 Oktober 2026, 17:00 CEST.
- API key hanya tampil **sekali** saat dibuat.
- Maksimal 5 key aktif per akun.
- Pakai proxy **residensial** (bukan datacenter).

## Atribusi

Sumber kode temp-mail: **[hirotomasato/tempik](https://github.com/hirotomasato/tempik)**
(lihat `src/tempmail.py`).

## Struktur

```
main.py            # CLI
batch.py           # batch runner + rotasi proxy
src/botkeep.py     # engine: signup + panen API key + API helper
src/tempmail.py    # client temp-mail (tempik)
src/inboxstore.py  # riwayat inbox
src/router9.py     # sync ke 9router
config.example.toml
```

## Disclaimer

Untuk penggunaan pribadi/edukasi. Hormati Terms of Service Botkeep.
