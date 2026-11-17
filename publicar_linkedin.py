#!/usr/bin/env python3
"""Publica no LinkedIn (perfil pessoal) o post agendado para hoje (horário de Brasília).

Roda no GitHub Actions. Só usa a biblioteca padrão do Python.

Formatos (campo "formato" em agenda-linkedin.json):
  documento  PDF publicado como post de documento (carrossel)
  imagem     uma imagem JPEG
  texto      só texto

Variáveis de ambiente:
  LI_TOKEN        token de acesso do LinkedIn (secret; vale 60 dias)
  LI_TOKEN_VENCE  data de vencimento do token, AAAA-MM-DD (variável do repositório)
  MODO            "publicar" (padrão) ou "teste" (valida token, permissão e arquivos sem publicar)
  DATA            opcional, AAAA-MM-DD para publicar/testar outra data
  LI_VERSION      opcional, versão da API (AAAAMM), padrão abaixo
  LI_HOST         opcional, padrão "https://api.linkedin.com" (usado nos testes)

Arquivos:
  agenda-linkedin.json      lista de posts com data, arquivo e texto
  publicados-linkedin.json  registro do que já foi publicado (evita post duplicado)
"""
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
BRT = dt.timezone(dt.timedelta(hours=-3))
HOST = os.environ.get("LI_HOST", "https://api.linkedin.com").rstrip("/")
VERSAO = os.environ.get("LI_VERSION", "202609")
ESPERA_MAX_S = int(os.environ.get("ESPERA_MAX_S", "300"))
AVISO_DIAS = 7
LIMITE_TEXTO = 3000


class Falha(Exception):
    pass


def log(msg):
    print(msg, flush=True)


# ---------- API do LinkedIn ----------
def api(metodo, caminho, corpo=None, rest=True):
    url = caminho if caminho.startswith("http") else f"{HOST}{caminho}"
    cab = {"Authorization": f"Bearer {os.environ['LI_TOKEN'].strip()}"}
    if rest:
        cab.update({"LinkedIn-Version": VERSAO, "X-Restli-Protocol-Version": "2.0.0"})
    dados = None
    if corpo is not None:
        dados = json.dumps(corpo).encode()
        cab["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=dados, method=metodo, headers=cab)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            txt = r.read().decode() or "{}"
            return json.loads(txt), dict(r.headers)
    except urllib.error.HTTPError as e:
        det = e.read().decode(errors="replace")[:400]
        if e.code == 401:
            raise Falha("Token do LinkedIn inválido ou vencido (HTTP 401). Gere um novo token "
                        "(CONFIGURAR-LINKEDIN.md, passo 2) e atualize o secret LI_TOKEN e a variável LI_TOKEN_VENCE.") from None
        if e.code == 403:
            raise Falha(f"Sem permissão (HTTP 403) em {metodo} {caminho.split('?')[0]}. Confira se o app tem o produto "
                        f"'Share on LinkedIn' e se o token foi gerado com w_member_social. Detalhe: {det}") from None
        raise Falha(f"LinkedIn {metodo} {caminho.split('?')[0]} -> HTTP {e.code}: {det}") from None
    except urllib.error.URLError as e:
        raise Falha(f"Sem conexão com a API do LinkedIn: {e.reason}") from None


def autor():
    info, _ = api("GET", "/v2/userinfo", rest=False)
    if not info.get("sub"):
        raise Falha("Não consegui identificar o perfil (userinfo sem 'sub'). O token precisa dos escopos openid e profile.")
    return f"urn:li:person:{info['sub']}", info.get("name", "?")


def enviar_arquivo(tipo, caminho, dono):
    """tipo: 'documents' ou 'images'. Devolve o URN do arquivo já processado."""
    resp, _ = api("POST", f"/rest/{tipo}?action=initializeUpload", {"initializeUploadRequest": {"owner": dono}})
    v = resp.get("value", {})
    urn = v.get("document") or v.get("image")
    if not (urn and v.get("uploadUrl")):
        raise Falha(f"Resposta inesperada ao iniciar envio: {resp}")
    req = urllib.request.Request(v["uploadUrl"], data=Path(caminho).read_bytes(), method="PUT",
                                 headers={"Authorization": f"Bearer {os.environ['LI_TOKEN'].strip()}",
                                          "Content-Type": "application/octet-stream"})
    try:
        with urllib.request.urlopen(req, timeout=300):
            pass
    except urllib.error.HTTPError as e:
        raise Falha(f"Falha ao enviar {Path(caminho).name}: HTTP {e.code} {e.read().decode(errors='replace')[:200]}") from None
    inicio = time.time()
    while True:
        st, _ = api("GET", f"/rest/{tipo}/{urllib.parse.quote(urn, safe='')}")
        status = st.get("status")
        if status == "AVAILABLE":
            return urn
        if status in ("PROCESSING_FAILED", "CLIENT_ERROR"):
            raise Falha(f"LinkedIn não aceitou {Path(caminho).name}: {status}")
        if time.time() - inicio > ESPERA_MAX_S:
            raise Falha(f"{Path(caminho).name} ainda em {status} após {ESPERA_MAX_S}s")
        time.sleep(5)


# O texto do post usa o "little text format" do LinkedIn: estes caracteres precisam de barra
# invertida, senão o post é cortado ou some parte do texto.
RESERVADOS = re.compile(r"([\\|{}@\[\]()<>#*_~])")


def escapar(t):
    return RESERVADOS.sub(r"\\\1", t)


def montar_texto(p):
    txt = escapar(p["texto"].strip())
    tags = [h.lstrip("#") for h in p.get("hashtags", [])]
    if tags:
        txt += "\n\n" + " ".join("{hashtag|\\#|" + t + "}" for t in tags)
    visivel = len(p["texto"].strip()) + sum(len(t) + 2 for t in tags) + 2
    if visivel > LIMITE_TEXTO:
        raise Falha(f"Texto do dia {p['data']} tem {visivel} caracteres (máx. {LIMITE_TEXTO})")
    return txt


def publicar(p, dono):
    corpo = {
        "author": dono,
        "commentary": montar_texto(p),
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    if p["formato"] == "documento":
        urn = enviar_arquivo("documents", RAIZ / p["arquivo"], dono)
        corpo["content"] = {"media": {"title": p["titulo_documento"], "id": urn}}
    elif p["formato"] == "imagem":
        urn = enviar_arquivo("images", RAIZ / p["arquivo"], dono)
        corpo["content"] = {"media": {"id": urn, "altText": p.get("alt") or p["tema"]}}
    _, cab = api("POST", "/rest/posts", corpo)
    post = {k.lower(): v for k, v in cab.items()}.get("x-restli-id")
    if not post:
        raise Falha("O LinkedIn não devolveu o id do post (x-restli-id)")
    return post, f"https://www.linkedin.com/feed/update/{post}/"


def comentar(post, dono, texto):
    api("POST", f"/rest/socialActions/{urllib.parse.quote(post, safe='')}/comments",
        {"actor": dono, "object": post, "message": {"text": texto}})


# ---------- utilidades ----------
def checar_post(p):
    if p["formato"] not in ("documento", "imagem", "texto"):
        raise Falha(f"{p['id']}: formato inválido {p['formato']}")
    if p["formato"] != "texto":
        f = RAIZ / p["arquivo"]
        if not f.exists():
            raise Falha(f"{p['id']}: arquivo não encontrado: {p['arquivo']}")
        mb = f.stat().st_size / 1e6
        if p["formato"] == "documento" and (f.suffix.lower() != ".pdf" or mb > 100):
            raise Falha(f"{p['id']}: documento precisa ser PDF de até 100 MB ({mb:.1f} MB)")
        if p["formato"] == "imagem" and f.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            raise Falha(f"{p['id']}: imagem precisa ser JPG ou PNG")
    montar_texto(p)


def dias_para_vencer():
    v = (os.environ.get("LI_TOKEN_VENCE") or "").strip()
    if not v:
        return None
    try:
        return (dt.date.fromisoformat(v) - dt.datetime.now(BRT).date()).days
    except ValueError:
        raise Falha(f"LI_TOKEN_VENCE inválida ({v!r}); use AAAA-MM-DD") from None


def ler_json(nome, padrao):
    f = RAIZ / nome
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else padrao


# ---------- principal ----------
def main():
    modo = (os.environ.get("MODO") or "publicar").strip().lower()
    data = (os.environ.get("DATA") or "").strip() or dt.datetime.now(BRT).date().isoformat()
    agenda = ler_json("agenda-linkedin.json", [])
    publicados = ler_json("publicados-linkedin.json", {})
    do_dia = [p for p in agenda if p["data"] == data]
    log(f"Data: {data} | modo: {modo} | posts na agenda para hoje: {len(do_dia)}")

    if not (os.environ.get("LI_TOKEN") or "").strip():
        if modo == "teste":
            raise Falha("Secret LI_TOKEN não configurado no repositório")
        log("LinkedIn ainda não configurado (sem LI_TOKEN). Nada a fazer.")
        return

    restam = dias_para_vencer()
    if restam is None:
        log("Aviso: variável LI_TOKEN_VENCE não definida; não dá para avisar antes do token vencer.")
    elif restam < 0:
        raise Falha(f"O token do LinkedIn venceu há {-restam} dia(s). Gere outro (CONFIGURAR-LINKEDIN.md, passo 2).")
    else:
        log(f"Token vence em {restam} dia(s) ({os.environ['LI_TOKEN_VENCE']}).")

    if modo == "teste":
        dono, nome = autor()
        log(f"Token OK. Perfil: {nome} ({dono})")
        resp, _ = api("POST", "/rest/images?action=initializeUpload", {"initializeUploadRequest": {"owner": dono}})
        if not resp.get("value", {}).get("uploadUrl"):
            raise Falha(f"Permissão de publicação não confirmada: {resp}")
        log("Permissão de publicação (w_member_social) OK. Nenhum arquivo foi enviado.")
        alvo = do_dia or [p for p in agenda if p["data"] >= data][:1]
        for p in alvo:
            checar_post(p)
            log(f"Post de {p['data']} ({p['tema']}, {p['formato']}): arquivo e texto OK")
        log("Teste concluído. Nada foi publicado.")
        return

    if not do_dia:
        log("Nada agendado para hoje.")
    else:
        dono = None
        for p in do_dia:
            chave = p["id"]
            if chave in publicados:
                log(f"{chave} já publicado em {publicados[chave]['em']}. Pulando.")
                continue
            checar_post(p)
            dono = dono or autor()[0]
            log(f"Publicando {chave} ({p['tema']}, {p['formato']})...")
            post, link = publicar(p, dono)
            publicados[chave] = {"em": dt.datetime.now(BRT).isoformat(timespec="seconds"), "post": post, "link": link}
            (RAIZ / "publicados-linkedin.json").write_text(
                json.dumps(publicados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            log(f"Publicado: {link}")
            com = (p.get("primeiro_comentario") or "").strip()
            if com:
                try:
                    comentar(post, dono, com)
                    log("Primeiro comentário publicado.")
                except Falha as e:
                    log(f"Aviso: o post saiu, mas o primeiro comentário falhou: {e}")

    # Falhar de propósito faz o GitHub mandar e-mail: é o lembrete para renovar o token.
    if restam is not None and restam <= AVISO_DIAS:
        raise Falha(f"LEMBRETE: o token do LinkedIn vence em {restam} dia(s). "
                    f"Gere um novo (CONFIGURAR-LINKEDIN.md, passo 2). O post de hoje foi tratado normalmente.")


if __name__ == "__main__":
    try:
        main()
    except Falha as e:
        log(f"ERRO: {e}")
        sys.exit(1)
