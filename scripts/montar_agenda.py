#!/usr/bin/env python3
"""Converte um ciclo renderizado (PNG) em JPG dentro do repositório e atualiza agenda.json.

Uso:
  python3 scripts/montar_agenda.py --ciclo-dir <pasta do ciclo> --ciclo 2026-11_ciclo-01 --repo <raiz do repo>

A pasta do ciclo precisa ter cronograma.json e as pastas dia-XX_<tema>/slide-N.png.
Entradas já existentes na agenda com o mesmo id são substituídas (posts já publicados
continuam registrados em publicados.json e não são republicados).
"""
import argparse, datetime as dt, json, re, unicodedata
from pathlib import Path
from PIL import Image


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()[:40]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ciclo-dir", required=True)
    ap.add_argument("--ciclo", required=True)
    ap.add_argument("--repo", required=True)
    a = ap.parse_args()

    src, repo = Path(a.ciclo_dir), Path(a.repo)
    cron = json.loads((src / "cronograma.json").read_text(encoding="utf-8"))
    ini = dt.date.fromisoformat(cron["inicio"])
    novos = []
    for p in cron["posts"]:
        pasta = f"dia-{p['dia']:02d}_{slug(p['tema'])}"
        pngs = sorted((src / pasta).glob("slide-*.png"), key=lambda f: int(f.stem.split("-")[1]))
        if len(pngs) != len(p["slides"]):
            raise SystemExit(f"{pasta}: esperava {len(p['slides'])} slides, achei {len(pngs)}")
        destino = repo / "posts" / a.ciclo / pasta
        destino.mkdir(parents=True, exist_ok=True)
        imagens = []
        for f in pngs:
            jpg = destino / (f.stem + ".jpg")
            Image.open(f).convert("RGB").save(jpg, "JPEG", quality=92, optimize=True, progressive=False)
            imagens.append(jpg.relative_to(repo).as_posix())
        novos.append({
            "id": f"{a.ciclo}_dia-{p['dia']:02d}",
            "data": (ini + dt.timedelta(days=p["dia"] - 1)).isoformat(),
            "tema": p["tema"],
            "formato": p["formato"],
            "imagens": imagens,
            "legenda": p["legenda"],
            "hashtags": p["hashtags"],
        })

    agenda_f = repo / "agenda.json"
    agenda = json.loads(agenda_f.read_text(encoding="utf-8")) if agenda_f.exists() else []
    ids = {n["id"] for n in novos}
    agenda = [x for x in agenda if x["id"] not in ids] + novos
    agenda.sort(key=lambda x: (x["data"], x["id"]))
    datas = [x["data"] for x in agenda]
    dup = {d for d in datas if datas.count(d) > 1}
    if dup:
        raise SystemExit(f"Mais de um post na mesma data: {sorted(dup)}")
    agenda_f.write_text(json.dumps(agenda, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK: {len(novos)} posts do ciclo {a.ciclo} na agenda ({novos[0]['data']} a {novos[-1]['data']})")


if __name__ == "__main__":
    main()
