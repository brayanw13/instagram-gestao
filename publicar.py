#!/usr/bin/env python3
"""Publica no Instagram o post agendado para hoje (horário de Brasília).

Roda no GitHub Actions. Só usa a biblioteca padrão do Python.

Variáveis de ambiente:
  IG_TOKEN        token de acesso da Página (secret)
  IG_USER_ID      ID da conta do Instagram (secret)
  GITHUB_REPOSITORY  owner/repo (o GitHub preenche)
  MODO            "publicar" (padrão) ou "teste" (valida tudo e não publica)
  DATA            opcional, AAAA-MM-DD para publicar/testar outra data
  BRANCH          opcional, padrão "main"
  GRAPH_VERSION   opcional, padrão "v26.0"
  GRAPH_HOST      opcional, padrão "https://graph.facebook.com" (usado nos testes)

Arquivos:
  agenda.json      lista de posts com data, imagens e legenda
  publicados.json  registro do que já foi publicado (evita post duplicado)
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
BRT = dt.timezone(dt.timedelta(hours=-3))
HOST = os.environ.get("GRAPH_HOST", "https://graph.facebook.com").rstrip("/")
VERSAO = os.environ.get("GRAPH_VERSION", "v26.0")
ESPERA_MAX_S = int(os.environ.get("ESPERA_MAX_S", "180"))


class Falha(Exception):
    pass


def log(msg):
    print(msg, flush=True)


# ---------- Graph API ----------
def graph(metodo, caminho, params=None):
    params = dict(params or {})
    params["access_token"] = os.environ["IG_TOKEN"]
    url = f"{HOST}/{VERSAO}/{caminho}"
    dados = urllib.parse.urlencode(params).encode()
    if metodo == "GET":
        req = urllib.request.Request(f"{url}?{dados.decode()}", method="GET")
    else:
        req = urllib.request.Request(url, data=dados, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        corpo = e.read().decode(errors="replace")
        try:
            err = json.loads(corpo).get("error", {})
            detalhe = f"{err.get('message')} (code {err.get('code')}, subcode {err.get('error_subcode')})"
        except Exception:
            detalhe = corpo[:300]
        raise Falha(f"Graph API {metodo} {caminho.split('?')[0]} -> HTTP {e.code}: {detalhe}") from None
    except urllib.error.URLError as e:
        raise Falha(f"Sem conexão com a Graph API: {e.reason}") from None


def esperar_container(cid):
    inicio = time.time()
    while True:
        st = graph("GET", cid, {"fields": "status_code,status"})
        code = st.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise Falha(f"Container {cid} terminou com {code}: {st.get('status')}")
        if time.time() - inicio > ESPERA_MAX_S:
            raise Falha(f"Container {cid} ainda em {code} após {ESPERA_MAX_S}s")
        time.sleep(5)


def criar_e_publicar(ig, urls, legenda):
    if len(urls) == 1:
        c = graph("POST", f"{ig}/media", {"image_url": urls[0], "caption": legenda})["id"]
    else:
        filhos = []
        for u in urls:
            filhos.append(graph("POST", f"{ig}/media", {"image_url": u, "is_carousel_item": "true"})["id"])
        for f in filhos:
            esperar_container(f)
        c = graph("POST", f"{ig}/media", {"media_type": "CAROUSEL", "children": ",".join(filhos), "caption": legenda})["id"]
    esperar_container(c)
    mid = graph("POST", f"{ig}/media_publish", {"creation_id": c})["id"]
    link = None
    try:
        link = graph("GET", mid, {"fields": "permalink"}).get("permalink")
    except Falha:
        pass
    return mid, link


# ---------- utilidades ----------
def url_publica(caminho):
    base = os.environ.get("IMG_BASE")  # só para testes locais
    if base:
        return base.rstrip("/") + "/" + urllib.parse.quote(caminho)
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise Falha("GITHUB_REPOSITORY não definido")
    branch = os.environ.get("BRANCH", "main")
    return f"https://raw.githubusercontent.com/{repo}/{branch}/" + urllib.parse.quote(caminho)


def checar_imagem(url):
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            tipo = r.headers.get("Content-Type", "")
            if r.status != 200 or "jpeg" not in tipo:
                raise Falha(f"Imagem inválida ({r.status}, {tipo}): {url}")
    except urllib.error.HTTPError as e:
        raise Falha(f"Imagem não acessível (HTTP {e.code}): {url}") from None


def montar_legenda(p):
    txt = p["legenda"].strip()
    if p.get("hashtags"):
        txt += "\n\n" + " ".join(p["hashtags"])
    if len(txt) > 2200:
        raise Falha(f"Legenda do dia {p['data']} tem {len(txt)} caracteres (máx. 2200)")
    return txt


def ler_json(nome, padrao):
    f = RAIZ / nome
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else padrao


# ---------- principal ----------
def main():
    modo = (os.environ.get("MODO") or "publicar").strip().lower()
    data = (os.environ.get("DATA") or "").strip() or dt.datetime.now(BRT).date().isoformat()
    for v in ("IG_TOKEN", "IG_USER_ID"):
        if not os.environ.get(v):
            raise Falha(f"Secret {v} não configurado no repositório")
    ig = os.environ["IG_USER_ID"].strip()

    agenda = ler_json("agenda.json", [])
    publicados = ler_json("publicados.json", {})
    do_dia = [p for p in agenda if p["data"] == data]
    log(f"Data: {data} | modo: {modo} | posts na agenda para hoje: {len(do_dia)}")

    if modo == "teste":
        conta = graph("GET", ig, {"fields": "username"})
        log(f"Token OK. Conta: @{conta.get('username')}")
        try:
            lim = graph("GET", f"{ig}/content_publishing_limit", {"fields": "quota_usage,config"})
            log(f"Limite de publicação: {json.dumps(lim.get('data', lim), ensure_ascii=False)}")
        except Falha as e:
            log(f"(não foi possível ler o limite: {e})")
        alvo = do_dia or [p for p in agenda if p["data"] >= data][:1]
        for p in alvo:
            urls = [url_publica(i) for i in p["imagens"]]
            for u in urls:
                checar_imagem(u)
            montar_legenda(p)
            log(f"Post de {p['data']} ({p['tema']}): {len(urls)} imagem(ns) acessível(is) e legenda OK")
        log("Teste concluído. Nada foi publicado.")
        return

    if not do_dia:
        log("Nada agendado para hoje.")
        return
    for p in do_dia:
        chave = p["id"]
        if chave in publicados:
            log(f"{chave} já publicado em {publicados[chave]['em']}. Pulando.")
            continue
        if len(p["imagens"]) > 10:
            raise Falha(f"{chave}: carrossel com {len(p['imagens'])} imagens (máx. 10)")
        urls = [url_publica(i) for i in p["imagens"]]
        for u in urls:
            checar_imagem(u)
        log(f"Publicando {chave} ({p['tema']}, {len(urls)} imagem(ns))...")
        mid, link = criar_e_publicar(ig, urls, montar_legenda(p))
        publicados[chave] = {"em": dt.datetime.now(BRT).isoformat(timespec="seconds"), "media_id": mid, "link": link}
        (RAIZ / "publicados.json").write_text(json.dumps(publicados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        log(f"Publicado: {link or mid}")


if __name__ == "__main__":
    try:
        main()
    except Falha as e:
        print(f"::error::{e}", flush=True)
        sys.exit(1)
