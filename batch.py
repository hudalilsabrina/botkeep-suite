#!/usr/bin/env python3
"""Botkeep batch runner - buat banyak akun berurutan dengan rotasi proxy.

Contoh:
  ./run.sh harvest 5
  .venv/bin/python batch.py 10 --proxy-file proxies.txt --delay 12
"""
import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rich.console import Console
from src import botkeep

C = Console()
ROOT = Path(__file__).resolve().parent


def load_proxies(path=None):
    cands = [Path(path)] if path else [ROOT / "proxies_webshare.txt", ROOT / "proxies.txt"]
    for f in cands:
        if f and f.exists():
            lines = [l.strip() for l in f.read_text().splitlines()
                     if l.strip() and not l.startswith("#")]
            if lines:
                return lines
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("n", type=int)
    ap.add_argument("--proxy-file", default=None)
    ap.add_argument("--delay", type=int, default=10)
    a = ap.parse_args()

    proxies = load_proxies(a.proxy_file)
    if proxies:
        C.print(f"[cyan]Rotasi {len(proxies)} proxy[/]")
    ok = 0
    t0 = time.time()
    for i in range(1, a.n + 1):
        px = proxies[(i - 1) % len(proxies)] if proxies else None
        C.print(f"[cyan]=== Akun {i}/{a.n} ===[/]" + (f" [dim]via {px}[/]" if px else ""))
        r = asyncio.run(botkeep.harvest_botkeep(headless=False, proxy=px))
        if r.get("ok"):
            ok += 1
            C.print(f"[green]  OK {r['email']} | key {r.get('apikey','')[:14]}...[/]")
        else:
            C.print(f"[yellow]  gagal: {r.get('error')}[/]")
        if i < a.n:
            time.sleep(a.delay)
    C.print(f"\n[bold]Selesai: {ok}/{a.n} sukses dalam {round(time.time()-t0)}s[/]")


if __name__ == "__main__":
    main()
