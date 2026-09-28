# ==========================================================================
# Sincronizador dos Cadernos Técnicos SINAPI (Caixa)
# --------------------------------------------------------------------------
# Roda automaticamente via GitHub Actions (veja .github/workflows/sync-sinapi.yml)
# ou manualmente com: python scripts/sync_sinapi.py
#
# O que faz:
#  1. Lê a lista de cadernos técnicos do Buscador SINAPI
#  2. Para cada um, localiza o PDF oficial (caixa.gov.br)
#  3. Compara com o manifesto salvo (docs/manifest.json) para decidir se
#     precisa baixar (novo / atualizado) ou pular (sem alteração)
#  4. Salva os PDFs em docs/pdfs/ e atualiza docs/manifest.json
#
# O manifest.json é lido pela página estática (docs/index.html) publicada
# no GitHub Pages — por isso tudo fica dentro de docs/.
# ==========================================================================

import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# --------------------------------------------------------------------------
# CONFIGURAÇÕES
# --------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(REPO_ROOT, "docs")
PDFS_DIR = os.path.join(DOCS_DIR, "pdfs")
MANIFEST_PATH = os.path.join(DOCS_DIR, "manifest.json")

LISTAGEM_URL = "https://buscadorsinapi.com.br/cadernos-tecnicos"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

session = requests.Session()
session.headers.update(HEADERS)

os.makedirs(PDFS_DIR, exist_ok=True)


def slugify(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^\w\s-]", "", texto).strip().lower()
    texto = re.sub(r"[\s_]+", "-", texto)
    return texto or "caderno"


def agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def aquecer_sessao_caixa():
    for url in (
        "https://www.caixa.gov.br/Downloads/sinapi-cadernos-tecnicos/",
        "https://www.caixa.gov.br/poder-publico/modernizacao-gestao/sinapi/Paginas/default.aspx",
    ):
        try:
            session.get(url, timeout=15)
        except requests.RequestException:
            pass


def carregar_lista_cadernos():
    resp = session.get(LISTAGEM_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    dados = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/caderno-tecnico/" in href:
            url_pagina = urljoin(LISTAGEM_URL, href)
            nome_bruto = a.get_text(separator=" ", strip=True) or slugify(href)
            nome = re.sub(r"\s*\d+\s*$", "", nome_bruto).strip() or nome_bruto
            slug = slugify(nome)
            if slug not in dados:
                dados[slug] = {"nome": nome, "url_pagina": url_pagina}
    return dados


def resolver_url_pdf(url_pagina: str):
    resp = session.get(url_pagina, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "caixa.gov.br" in href and href.lower().endswith(".pdf"):
            return href
    for a in soup.find_all("a", href=True):
        if a["href"].lower().endswith(".pdf"):
            return urljoin(url_pagina, a["href"])
    return None


def verificar_cabecalhos(url_pdf: str, referer: str):
    try:
        r = session.head(url_pdf, timeout=30, headers={"Referer": referer}, allow_redirects=True)
        if r.status_code != 200:
            return None
        content_length = r.headers.get("Content-Length")
        last_modified = r.headers.get("Last-Modified")
        if content_length is None and last_modified is None:
            return None
        return {"content_length": content_length, "last_modified": last_modified}
    except requests.RequestException:
        return None


def baixar_para_arquivo(url_pdf: str, referer: str, caminho_destino: str, tentativas: int = 3):
    extras = {"Referer": referer}
    for tentativa in range(1, tentativas + 1):
        try:
            with session.get(url_pdf, stream=True, timeout=60, headers=extras) as r:
                if r.status_code == 200:
                    sha256 = hashlib.sha256()
                    tamanho = 0
                    with open(caminho_destino, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                            sha256.update(chunk)
                            tamanho += len(chunk)
                    return tamanho, sha256.hexdigest(), r.headers.get("Last-Modified")
                elif r.status_code == 403:
                    time.sleep(2 * tentativa)
                    continue
                else:
                    raise RuntimeError(f"HTTP {r.status_code}")
        except requests.RequestException as e:
            if tentativa == tentativas:
                raise
            time.sleep(1.5 * tentativa)
    raise RuntimeError("Bloqueado (403) após todas as tentativas")


def carregar_manifesto() -> dict:
    if not os.path.exists(MANIFEST_PATH):
        return {"atualizado_em": None, "cadernos": {}}
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"atualizado_em": None, "cadernos": {}}


def salvar_manifesto(manifesto: dict):
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifesto, f, ensure_ascii=False, indent=2)


def main():
    print("=" * 70)
    print("Sincronizador de Cadernos Técnicos SINAPI")
    print("=" * 70)

    print("Aquecendo sessão no site da Caixa...")
    aquecer_sessao_caixa()

    print(f"Carregando lista de cadernos em {LISTAGEM_URL} ...")
    try:
        cadernos = carregar_lista_cadernos()
    except requests.RequestException as e:
        print(f"ERRO FATAL: não foi possível carregar a lista de cadernos: {e}")
        sys.exit(1)

    print(f"-> {len(cadernos)} cadernos encontrados.\n")

    manifesto = carregar_manifesto()
    itens = manifesto.get("cadernos", {})

    contagem = {"novos": 0, "atualizados": 0, "sem_alteracao": 0, "erros": 0}

    for i, (slug, item) in enumerate(sorted(cadernos.items(), key=lambda kv: kv[1]["nome"]), start=1):
        nome = item["nome"]
        url_pagina = item["url_pagina"]
        print(f"({i}/{len(cadernos)}) {nome}")

        try:
            url_pdf = resolver_url_pdf(url_pagina)
        except requests.RequestException as e:
            print(f"   [ERRO] falha ao abrir página do caderno: {e}")
            contagem["erros"] += 1
            if slug in itens:
                itens[slug]["status_ultima_sincronizacao"] = "erro"
                itens[slug]["ultima_verificacao"] = agora_iso()
            continue

        if not url_pdf:
            print("   [AVISO] PDF não encontrado na página.")
            contagem["erros"] += 1
            continue

        nome_arquivo = f"SINAPI-CT-{slug.upper()}.pdf"
        caminho_destino = os.path.join(PDFS_DIR, nome_arquivo)
        registro_anterior = itens.get(slug)

        cabecalhos = verificar_cabecalhos(url_pdf, referer=url_pagina)

        precisa_baixar = True
        if registro_anterior and cabecalhos and os.path.exists(caminho_destino):
            mudou_tamanho = (
                cabecalhos["content_length"] is not None
                and str(registro_anterior.get("content_length")) != str(cabecalhos["content_length"])
            )
            mudou_data = (
                cabecalhos["last_modified"] is not None
                and registro_anterior.get("last_modified_http") != cabecalhos["last_modified"]
            )
            if not mudou_tamanho and not mudou_data:
                precisa_baixar = False

        if not precisa_baixar:
            print("   -> sem alterações (cabeçalhos HTTP idênticos).")
            contagem["sem_alteracao"] += 1
            registro_anterior["ultima_verificacao"] = agora_iso()
            registro_anterior["status_ultima_sincronizacao"] = "sem_alteracao"
            time.sleep(0.3)
            continue

        try:
            tamanho, sha256, last_modified = baixar_para_arquivo(
                url_pdf, referer=url_pagina, caminho_destino=caminho_destino
            )
        except Exception as e:
            print(f"   [ERRO no download] {e}")
            contagem["erros"] += 1
            continue

        if registro_anterior and registro_anterior.get("sha256") == sha256:
            status = "sem_alteracao"
            print("   -> conteúdo idêntico ao já salvo (confirmado por hash).")
            contagem["sem_alteracao"] += 1
        elif registro_anterior:
            status = "atualizado"
            print(f"   -> ATUALIZADO ({tamanho} bytes).")
            contagem["atualizados"] += 1
        else:
            status = "novo"
            print(f"   -> NOVO ({tamanho} bytes).")
            contagem["novos"] += 1

        itens[slug] = {
            "nome": nome,
            "url_pagina": url_pagina,
            "url_pdf_original": url_pdf,
            "arquivo": f"pdfs/{nome_arquivo}",
            "content_length": cabecalhos["content_length"] if cabecalhos else str(tamanho),
            "last_modified_http": last_modified,
            "sha256": sha256,
            "tamanho_bytes": tamanho,
            "status_ultima_sincronizacao": status,
            "baixado_em": agora_iso() if status != "sem_alteracao" else registro_anterior.get("baixado_em", agora_iso()),
            "ultima_verificacao": agora_iso(),
        }

        time.sleep(0.4)

    manifesto["cadernos"] = itens
    manifesto["atualizado_em"] = agora_iso()
    manifesto["resumo_ultima_execucao"] = contagem
    salvar_manifesto(manifesto)

    print("\n" + "=" * 70)
    print(
        f"Concluído: {contagem['novos']} novos, {contagem['atualizados']} atualizados, "
        f"{contagem['sem_alteracao']} sem alteração, {contagem['erros']} erros."
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
