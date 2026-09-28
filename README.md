# Cadernos Técnicos SINAPI — Espelho automático no GitHub

Este repositório baixa e mantém atualizados automaticamente os 172 Cadernos
Técnicos de Composições do SINAPI (Caixa Econômica Federal), publicando uma
página de consulta/download no GitHub Pages — **sem precisar de nenhum
computador ligado**, tudo roda na nuvem do GitHub.

## Como funciona

```
┌─────────────────────┐    toda semana (ou manual)   ┌──────────────────┐
│  GitHub Actions      │ ───────────────────────────▶ │  Site da Caixa    │
│  (scripts/sync_...)  │ ◀─────────────────────────── │  (PDFs oficiais)  │
└──────────┬───────────┘        baixa PDFs             └──────────────────┘
           │ salva em docs/pdfs/ + docs/manifest.json
           ▼
┌─────────────────────┐
│  GitHub Pages        │  ← página estática (docs/index.html) lê o
│  (site público)       │    manifest.json e mostra a lista + links de download
└─────────────────────┘
```

- **GitHub Actions**: roda o script Python `scripts/sync_sinapi.py` em um
  servidor temporário do GitHub, sem custo (dentro do limite gratuito).
- **docs/**: pasta publicada como site (GitHub Pages). Contém a página HTML,
  o `manifest.json` (histórico dos cadernos) e os PDFs baixados.
- Como o `index.html` e o `manifest.json` ficam no **mesmo domínio**
  (`seu-usuario.github.io`), não há problema de CORS — diferente de tentar
  acessar `caixa.gov.br` direto do navegador.

## Passo a passo para publicar

### 1. Criar o repositório no GitHub
1. Acesse [github.com/new](https://github.com/new)
2. Dê um nome, ex: `sinapi-cadernos-tecnicos`
3. Deixe **Público** (necessário para GitHub Pages gratuito) e crie.

### 2. Enviar estes arquivos para o repositório
Se você tem o Git instalado:
```bash
cd sinapi-github
git init
git add .
git commit -m "Estrutura inicial do projeto"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/sinapi-cadernos-tecnicos.git
git push -u origin main
```

Ou, sem usar linha de comando: no GitHub, clique em **Add file → Upload
files** e arraste toda a pasta `sinapi-github` (mantendo a estrutura de
subpastas).

### 3. Ativar o GitHub Pages
1. No repositório, vá em **Settings → Pages**
2. Em **Source**, selecione a branch `main` e a pasta `/docs`
3. Clique em **Save**
4. Após 1-2 minutos, o site estará disponível em:
   `https://SEU_USUARIO.github.io/sinapi-cadernos-tecnicos/`

### 4. Rodar a primeira sincronização manualmente
Não espere a segunda-feira: rode na hora.
1. Vá na aba **Actions** do repositório
2. Clique no workflow **"Sincronizar Cadernos Técnicos SINAPI"**
3. Clique em **Run workflow → Run workflow**
4. Aguarde alguns minutos e acompanhe o progresso clicando na execução

Quando terminar, atualize a página do GitHub Pages — os cadernos devem
aparecer na tabela.

## Depois disso, é automático
O workflow roda sozinho **toda segunda-feira às 06:00 (horário de
Brasília)**, baixando apenas os cadernos novos ou que a Caixa atualizou.
Você pode alterar essa frequência editando o `cron` em
`.github/workflows/sync-sinapi.yml`.

## ⚠️ Aviso importante sobre bloqueios

O site da Caixa possui proteção anti-bot (WAF) que pode bloquear (erro 403)
requisições vindas de servidores de nuvem — incluindo os servidores do
GitHub Actions, que também são datacenter (Microsoft Azure). **Não há
garantia de que todos os 172 cadernos serão baixados com sucesso
automaticamente.**

Se isso acontecer:
- O script não trava — ele marca o caderno como 🔴 **Erro** no
  `manifest.json` e segue para o próximo.
- Veja o log completo na aba **Actions** → clique na execução → clique no
  passo "Rodar sincronização" para ver quais falharam.
- Como alternativa, você pode rodar `python scripts/sync_sinapi.py`
  localmente (no seu computador, com IP residencial — menos sujeito a
  bloqueio), e depois só fazer `git push` para enviar os arquivos baixados
  manualmente.

## Sobre o tamanho do repositório

PDFs binários não comprimem bem no Git. Com 172 cadernos, o repositório deve
ficar na casa de algumas dezenas/poucas centenas de MB — dentro do limite
gratuito do GitHub (repositórios até ~1 GB sem aviso, até 5 GB tolerado).
Não deve ser um problema para este caso de uso.

## Estrutura do projeto

```
sinapi-github/
├── .github/
│   └── workflows/
│       └── sync-sinapi.yml     # Agenda e roda a sincronização automática
├── scripts/
│   └── sync_sinapi.py           # Script que baixa e compara os cadernos
├── docs/                        # Publicado como site (GitHub Pages)
│   ├── index.html               # Página de consulta/download
│   ├── manifest.json            # Histórico (gerado/atualizado pelo script)
│   └── pdfs/                    # PDFs baixados ficam aqui
├── requirements.txt
└── README.md
```
