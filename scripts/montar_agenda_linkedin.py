#!/usr/bin/env python3
"""Copia um ciclo do LinkedIn renderizado para o repositório e atualiza agenda-linkedin.json.

Uso:
  python3 scripts/montar_agenda_linkedin.py --ciclo-dir <pasta do ciclo> --ciclo 2026-11_ciclo-01 --repo <raiz do repo>

A pasta do ciclo precisa ter cronograma.json e, para cada post, a pasta dia-XX_<tema> gerada
pelo render_linkedin.py (documento.pdf ou imagem.jpg). Entradas já existentes com o mesmo id
são substituídas; posts já publicados continuam em publicados-linkedin.json e não são republicados.
"""
import argparse, datetime as dt, json, re, shutil, unicodedata
from pathlib import Path


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
        item = {
            "id": f"{a.ciclo}_dia-{p['dia']:02d}",
            "data": (ini + dt.timedelta(days=p["dia"] - 1)).isoformat(),
            "tema": p["tema"],
            "formato": p["formato"],
            "texto": p["texto"],
            "hashtags": p.get("hashtags", []),
        }
        nome = {"documento": "documento.pdf", "imagem": "imagem.jpg"}.get(p["formato"])
        if nome:
            origem = src / pasta / nome
            if not origem.exists():
                raise SystemExit(f"{pasta}: falta {nome} (rode o render_linkedin.py antes)")
            destino = repo / "posts-linkedin" / a.ciclo / pasta / nome
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origem, destino)
            item["arquivo"] = destino.relative_to(repo).as_posix()
        if p["formato"] == "documento":
            item["titulo_documento"] = p["titulo_documento"]
        if p["formato"] == "imagem":
            item["alt"] = " ".join(p["slides"][0].get("texto", [])) or p["tema"]
        if p.get("primeiro_comentario"):
            item["primeiro_comentario"] = p["primeiro_comentario"]
        novos.append(item)

    arq = repo / "agenda-linkedin.json"
    agenda = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else []
    ids = {n["id"] for n in novos}
    agenda = sorted([x for x in agenda if x["id"] not in ids] + novos, key=lambda x: (x["data"], x["id"]))
    arq.write_text(json.dumps(agenda, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK: {len(novos)} posts do LinkedIn na agenda ({novos[0]['data']} a {novos[-1]['data']})")


if __name__ == "__main__":
    main()
