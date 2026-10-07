"""Botkeep deploy helper - buat server + upload file + start, via Developer API.

Temuan penting (semua terbukti):
  - POST /workloads butuh header Idempotency-Key
  - seedFiles di POST /workloads REwel (formatnya tidak jelas) -> buat server
    TANPA seedFiles, lalu upload file via /files/upload
  - /files/upload: path HARUS diawali "/" (mis. "/main.py"), dan
    data HARUS base64
  - Port: Botkeep assign port acak (lihat dashboard "Port"); server HARUS
    listen di port itu (atau baca env PORT). Jangan hardcode 8080.
  - Domain publik: PUT /workloads/{id}/domain {"enabled": true}
    -> hostname seperti xxxxxx.bot-keep.xyz
"""
import base64
import json
import time
import urllib.request
import uuid
from typing import Any, Dict, Optional

API = "https://api.botkeep.cloud/api/v1/developer"


def _req(method: str, path: str, apikey: str, body: dict = None,
         idem: bool = False, timeout: int = 40) -> Dict[str, Any]:
    url = path if path.startswith("http") else f"{API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {apikey}", "Content-Type": "application/json",
               "Accept": "application/json"}
    if idem:
        headers["Idempotency-Key"] = str(uuid.uuid4())
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return {"status": r.status, "data": json.loads(raw) if raw else {}}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "error": e.read().decode()[:300]}


def create_workload(apikey: str, name: str, runtime: str = "python",
                    runtime_version: str = "3.13", start_command: str = "python main.py",
                    platform: str = "general", memory: int = 256, cpu: int = 50,
                    storage: int = 512) -> Dict[str, Any]:
    """Buat workload (tanpa seedFiles). Return dict dengan id."""
    body = {
        "name": name, "platform": platform, "runtime": runtime,
        "runtimeVersion": runtime_version, "sourceType": "blank",
        "startCommand": start_command,
        "resources": {"memoryLimitMb": memory, "cpuLimitPercent": cpu,
                      "storageLimitMb": storage},
    }
    return _req("POST", "/workloads", apikey, body, idem=True)


def upload_file(apikey: str, wid: str, path: str, content: str) -> Dict[str, Any]:
    """Upload file. path HARUS diawali '/', data HARUS base64."""
    if not path.startswith("/"):
        path = "/" + path
    body = {"path": path, "data": base64.b64encode(content.encode()).decode(),
            "overwrite": True}
    return _req("POST", f"/workloads/{wid}/files/upload", apikey, body, idem=True)


def action(apikey: str, wid: str, act: str) -> Dict[str, Any]:
    """act: start | stop | restart | kill | redeploy"""
    return _req("POST", f"/workloads/{wid}/actions", apikey, {"action": act}, idem=True)


def get_workload(apikey: str, wid: str) -> Dict[str, Any]:
    return _req("GET", f"/workloads/{wid}", apikey)


def get_logs(apikey: str, wid: str) -> Dict[str, Any]:
    return _req("GET", f"/workloads/{wid}/logs", apikey)


def get_domain(apikey: str, wid: str) -> Dict[str, Any]:
    return _req("GET", f"/workloads/{wid}/domain", apikey)


def enable_domain(apikey: str, wid: str, enabled: bool = True) -> Dict[str, Any]:
    return _req("PUT", f"/workloads/{wid}/domain", apikey, {"enabled": enabled}, idem=True)


def wait_running(apikey: str, wid: str, timeout: int = 300) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = get_workload(apikey, wid)
        st = (r.get("data") or {}).get("status")
        if st == "running":
            return True
        time.sleep(10)
    return False


def deploy(apikey: str, name: str, files: Dict[str, str], start_command: str = "python main.py",
           port: Optional[int] = None, runtime: str = "python",
           runtime_version: str = "3.13") -> Dict[str, Any]:
    """Deploy lengkap: create -> upload files -> start -> domain.

    files: {path: content}. Kalau port=None, kode harus baca env PORT.
    """
    out: Dict[str, Any] = {}
    r = create_workload(apikey, name, runtime, runtime_version, start_command)
    if r.get("status") not in (200, 201, 202):
        out["error"] = f"create gagal: {r}"
        return out
    wid = (r.get("data") or {}).get("id")
    out["workload_id"] = wid
    for path, content in files.items():
        ur = upload_file(apikey, wid, path, content)
        if ur.get("status") != 200:
            out.setdefault("upload_errors", []).append(f"{path}: {ur}")
    # start
    out["start"] = action(apikey, wid, "start")
    out["running"] = wait_running(apikey, wid)
    out["domain"] = enable_domain(apikey, wid, True)
    out["domain_info"] = get_domain(apikey, wid)
    return out
