"""Botkeep engine - buat akun Botkeep + panen API key (Founder Free).

Alur (semua terbukti):
  1. buat inbox tempik
  2. buka https://botkeep.cloud/register via patchright
  3. centang Terms -> isi Display name + Email + Password (min 12 char)
  4. Create account  -> langsung masuk /app, plan Founder Free aktif
  5. Developer -> Generate API key (scoped) -> secret bk_live_...
  6. simpan ke accounts.txt

Tidak ada captcha / verifikasi email / Discord.
Sumber mail: https://github.com/hirotomasato/tempik
"""
import asyncio
import json
import random
import string
from typing import Any, Dict, List, Optional

from rich.console import Console

from .tempmail import TempikClient
from .inboxstore import save as save_inbox

C = Console()

REGISTER_URL = "https://botkeep.cloud/register"
DEVELOPER_URL = "https://botkeep.cloud/app/developer"
API_BASE = "https://api.botkeep.cloud/api/v1/developer"

GIVEN = ["Sirsak", "Mangga", "Duku", "Rambutan", "Salak", "Kedondong", "Markisa",
         "Belimbing", "Jambu", "Srikaya", "Cempedak", "Langsat", "Namnam",
         "Buni", "Kersen", "Gandaria"]
FAMILY = ["Lapang", "Wangun", "Asri", "Sari", "Mekar", "Hijau", "Teduh",
          "Rindang", "Subur", "Segar", "Harum", "Manis"]


def _rand_password(n: int = 14) -> str:
    core = "".join(random.choices(string.ascii_letters + string.digits, k=n))
    return f"Bk{core}!7"


async def harvest_botkeep(headless: bool = False, verbose: bool = True,
                          proxy: Optional[str] = None) -> Dict[str, Any]:
    """Buat 1 akun Botkeep + panen API key.

    Return dict {ok, email, password, apikey, plan, error, ...}
    """
    from patchright.async_api import async_playwright

    out: Dict[str, Any] = {"site": "botkeep", "ok": False}
    tc = TempikClient()
    email = tc.create_inbox()
    save_inbox("botkeep", email, tc.session_id, "")
    pwd = _rand_password()
    name = f"{random.choice(GIVEN)} {random.choice(FAMILY)}"
    out.update(email=email, password=pwd, name=name)
    if verbose:
        C.print(f"[cyan]botkeep[/] inbox: {email}")

    async with async_playwright() as pw:
        launch_kw = {"headless": headless}
        if proxy:
            launch_kw["proxy"] = _parse_proxy(proxy)
        browser = await pw.chromium.launch(**launch_kw)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        try:
            await page.goto(REGISTER_URL, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(4000)
            # dismiss cookie banner kalau ada (menutupi form)
            try:
                await page.click("text=Continue with necessary only", timeout=4000)
                await page.wait_for_timeout(1000)
            except Exception:
                pass
            # tunggu form muncul (React render)
            try:
                await page.wait_for_selector("input[type=email]", timeout=20000)
            except Exception:
                pass
            await page.wait_for_timeout(1500)

            # 1. isi form — selector by placeholder (field nama TIDAK punya
            #    atribut type=text, jadi input[type=text] gagal).
            await page.fill("input[placeholder*='call you']", name)
            await page.fill("input[placeholder*='example.com']", email)
            await page.fill("input[placeholder*='12 characters']", pwd)
            await page.evaluate("""() => { const c=document.querySelector('input[type=checkbox]'); if(c&&!c.checked) c.click(); }""")
            filled = await page.evaluate("""() => {
                const t=document.querySelector("input[placeholder*='call you']");
                const e=document.querySelector("input[placeholder*='example.com']");
                const p=document.querySelector("input[placeholder*='12 characters']");
                const cb=document.querySelector('input[type=checkbox]');
                return {name:t?t.value:'', email:e?e.value:'', pwd:p?p.value.length:0, terms:cb?cb.checked:false};
            }""")
            if verbose:
                C.print(f"[dim]  form: {filled}[/]")
            await page.wait_for_timeout(800)

            # 2. submit
            await page.evaluate("""() => { const b=[...document.querySelectorAll('button')].find(x=>/create account/i.test(x.innerText||'')); if(b) b.click(); }""")
            await page.wait_for_timeout(9000)
            out["final_url"] = page.url

            if "/app" not in page.url:
                body = await page.evaluate("document.body.innerText")
                out["error"] = "register-failed"
                out["ui_error"] = body[:250]
                if verbose:
                    C.print(f"[yellow]  gagal register: {body[:150]}[/]")
                return out
            if verbose:
                C.print("[green]  akun jadi, masuk dashboard[/]")

            # 3. panen API key di halaman Developer
            key = await _create_api_key(page)
            if key:
                out["ok"] = True
                out["apikey"] = key
                out["plan"] = "Founder Free"
                if verbose:
                    C.print(f"[green]  API key: {key[:14]}...{key[-6:]}[/]")
                _append_account(email, pwd, key, "Founder Free")
            else:
                out["error"] = "no-apikey"
                if verbose:
                    C.print("[yellow]  gagal ambil API key[/]")
            return out
        except Exception as e:
            out["error"] = str(e)[:180]
            return out
        finally:
            try:
                await ctx.close()
                await browser.close()
            except Exception:
                pass


async def _create_api_key(page) -> Optional[str]:
    """Buka /app/developer, isi nama key, centang permission, generate, ambil secret."""
    try:
        await page.goto(DEVELOPER_URL, wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_timeout(5000)

        # isi nama key + centang semua permission
        await page.evaluate("""() => {
            const set=(el,v)=>{const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                s.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));};
            const inp=document.querySelector('input[type=text]')||document.querySelector('input:not([type])');
            if(inp) set(inp,'main');
            for(const c of document.querySelectorAll('input[type=checkbox]')){ if(!c.checked) c.click(); }
        }""")
        await page.wait_for_timeout(1000)

        # klik Generate key (pertama: muncul konfirmasi critical permission)
        await page.evaluate("""() => { const b=[...document.querySelectorAll('button')].find(x=>/generate key/i.test(x.innerText||'')); if(b) b.click(); }""")
        await page.wait_for_timeout(2500)

        # centang konfirmasi tambahan + generate lagi
        await page.evaluate("""() => {
            for(const c of document.querySelectorAll('input[type=checkbox]')){ if(!c.checked) c.click(); }
            const b=[...document.querySelectorAll('button')].find(x=>/generate key/i.test(x.innerText||''));
            if(b) b.click();
        }""")
        await page.wait_for_timeout(5000)

        # ambil secret dari textarea readonly di dialog
        secret = await page.evaluate("""() => { const t=document.querySelector('dialog textarea'); return t?t.value:''; }""")
        if secret and len(secret) > 20:
            return secret.strip()
        # fallback: cari textarea readonly manapun
        secret = await page.evaluate("""() => {
            for(const t of document.querySelectorAll('textarea[readonly]')){ if(t.value && t.value.length>20) return t.value; }
            return '';
        }""")
        return secret.strip() if secret and len(secret) > 20 else None
    except Exception:
        return None


def _parse_proxy(proxy: str) -> Dict[str, Any]:
    from urllib.parse import urlparse
    u = urlparse(proxy)
    scheme = u.scheme or "http"
    d: Dict[str, Any] = {"server": f"{scheme}://{u.hostname}:{u.port}"}
    if u.username:
        d["username"] = u.username
    if u.password:
        d["password"] = u.password
    return d


def _append_account(email: str, password: str, apikey: str, plan: str = ""):
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / "accounts.txt"
    with open(p, "a") as f:
        f.write(f"{email}:{password}:{apikey}:{plan}\n")


# ----------------------------- API helper (pakai key tersimpan) -----------------------------

def api_get(path: str, apikey: str, timeout: int = 20) -> Dict[str, Any]:
    """GET ke Developer API."""
    import urllib.request
    url = path if path.startswith("http") else f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {apikey}",
                                                "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def api_post(path: str, apikey: str, body: dict = None, idem: str = None,
             timeout: int = 30) -> Dict[str, Any]:
    """POST ke Developer API (write butuh Idempotency-Key)."""
    import urllib.request
    import uuid
    url = path if path.startswith("http") else f"{API_BASE}{path}"
    data = json.dumps(body or {}).encode()
    headers = {"Authorization": f"Bearer {apikey}", "Content-Type": "application/json",
               "Accept": "application/json", "Idempotency-Key": idem or str(uuid.uuid4())}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())
