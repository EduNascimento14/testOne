# Plataforma Integrada EHS

Este repositório contém os dois aplicativos Streamlit atualmente utilizados:

- `app.py`: aplicação principal da Plataforma Integrada EHS, com módulos de proteções de máquinas, auditorias, energia e emissões, Near Miss, requisitos legais e relatórios.
- `app_unificador_cr.py`: utilitário para consolidar vários arquivos XLSX de CR em uma única planilha, mantendo somente um cabeçalho e gerando um log de processamento.

## Requisitos

- Python 3.12, conforme `runtime.txt`
- `pip`

As principais dependências são Streamlit, pandas, SQLAlchemy, Plotly, openpyxl, XlsxWriter e ReportLab.

## Instalação

```bash
python -m venv .venv
```

Ative o ambiente virtual:

```bash
# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

## Executar a Plataforma Integrada EHS

```bash
streamlit run app.py
```

Por padrão, o app usa SQLite e cria o banco local `plataforma_ehs_integrada.db` na raiz do projeto. Esse arquivo é ignorado pelo Git.

Para usar outra conexão compatível com SQLAlchemy, defina a variável de ambiente `DATABASE_URL` antes de iniciar o app. Exemplo:

```bash
DATABASE_URL=sqlite:///plataforma_ehs_integrada.db
```

Um modelo de configuração está disponível em `.env.example`. O app lê `DATABASE_URL` diretamente do ambiente; o arquivo `.env` não é carregado automaticamente.

## Executar o Unificador de CR

```bash
streamlit run app_unificador_cr.py
```

Envie um ou mais arquivos `.xlsx` pela interface. O resultado consolidado é gerado em memória e disponibilizado para download.

## Arquivos de configuração

- `.streamlit/config.toml`: tema e opções da interface Streamlit.
- `runtime.txt`: versão do Python usada em ambientes de deploy compatíveis.
- `.env.example`: exemplo da configuração de banco do app principal.
