#!/usr/bin/env python3
"""Botkeep Suite - CLI: factory akun Botkeep + panen API key (Founder Free).

Command:
  harvest [n]      Buat n akun (default 1) + panen API key
  test             Uji semua API key tersimpan (GET /plan)
  report           Ringkasan akun + plan + limit
  workloads        Daftar workload tiap akun
  probe            Cek apakah endpoint Botkeep hidup
"""
import argparse
import asyncio
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rich.console import Console
from rich.table import Table
from rich import box

from src import botkeep

C = Console()
ROOT = Path(__file__).resolve().parent
ACCOUNTS = ROOT / "accounts.txt"


def _load_accounts():
    if not ACCOUNTS.exists():
        return []
    out = []
    for line in ACCOUNTS.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split(":")
        if len(parts) >= 3:
            out.append({"email": parts[0], "password": parts[1], "apikey": parts[2],
                        "plan": parts[3] if len(parts) > 3 else ""})
    return out


def _proxies():
    for f in (ROOT / "proxies.txt"):
        if f.exists():
            lines = [l.strip() for l in f.read_text().splitlines()
                     if l.strip() and not l.startswith("#")]
            if lines:
                return lines
    return []


def cmd_harvest(n, no_proxy):
    proxies = [] if no_proxy else _proxies()
    if proxies:
        C.print(f"[cyan]Rotasi {len(proxies)} proxy[/]")
    ok = 0
    for i in range(1, n + 1):
        px = proxies[(i - 1) % len(proxies)] if proxies else None
        C.print(f"[cyan]=== Akun {i}/{n} ===[/]" + (f" [dim]via {px}[/]" if px else ""))
        r = asyncio.run(botkeep.harvest_botkeep(headless=False, proxy=px))
        if r.get("ok"):
            ok += 1
        else:
            C.print(f"[yellow]  gagal: {r.get('error')} {r.get('ui_error','')[:120]}[/]")
    C.print(f"\n[bold]Selesai: {ok}/{n} sukses[/]")


def cmd_test():
    accts = _load_accounts()
    if not accts:
        C.print("[yellow]Belum ada akun.[/]")
        return
    C.print(f"[cyan]Uji {len(accts)} API key...[/]")
    t = Table(box=box.ROUNDED, title="Test API key")
    t.add_column("Email", style="cyan")
    t.add_column("Status")
    t.add_column("Plan", style="green")
    t.add_column("Slots", justify="right")
    for a in accts:
        try:
            d = botkeep.api_get("/plan", a["apikey"])
            lim = d.get("limits", {})
            t.add_row(a["email"][:26], "[green]OK[/]", d.get("planName", "-"),
                      str(lim.get("slots", "-")))
        except Exception as e:
            t.add_row(a["email"][:26], "[red]FAIL[/]", str(e)[:30], "-")
    C.print(t)


def cmd_report():
    accts = _load_accounts()
    C.print(f"[bold]Total akun: {len(accts)}[/]")
    if not accts:
        return
    t = Table(box=box.ROUNDED)
    t.add_column("#", justify="right")
    t.add_column("Email", style="cyan")
    t.add_column("API key")
    t.add_column("Plan", style="green")
    for i, a in enumerate(accts, 1):
        t.add_row(str(i), a["email"], a["apikey"][:14] + "...", a.get("plan", "-"))
    C.print(t)


def cmd_workloads():
    accts = _load_accounts()
    for a in accts:
        try:
            d = botkeep.api_get("/workloads", a["apikey"])
            wl = d.get("data", [])
            C.print(f"[cyan]{a['email']}[/]: {len(wl)} workload")
            for w in wl:
                C.print(f"  - {w.get('name','?')} [{w.get('status','?')}]")
        except Exception as e:
            C.print(f"[yellow]{a['email']}: {e}[/]")


def cmd_probe():
    try:
        req = urllib.request.Request(botkeep.API_BASE + "/capabilities")
        with urllib.request.urlopen(req, timeout=20) as r:
            C.print(f"[green]API hidup — status {r.status}[/]")
    except urllib.error.HTTPError as e:
        C.print(f"[yellow]API merespon {e.code} (hidup)[/]")
    except Exception as e:
        C.print(f"[red]API bermasalah: {e}[/]")


def main():
    ap = argparse.ArgumentParser(prog="botkeep", description="Botkeep Suite")
    sub = ap.add_subparsers(dest="cmd")
    h = sub.add_parser("harvest"); h.add_argument("n", nargs="?", type=int, default=1)
    h.add_argument("--no-proxy", action="store_true")
    sub.add_parser("test")
    sub.add_parser("report")
    sub.add_parser("workloads")
    sub.add_parser("probe")
    a = ap.parse_args()
    if a.cmd == "harvest":
        cmd_harvest(a.n, a.no_proxy)
    elif a.cmd == "test":
        cmd_test()
    elif a.cmd == "report":
        cmd_report()
    elif a.cmd == "workloads":
        cmd_workloads()
    elif a.cmd == "probe":
        cmd_probe()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
