# Auditoria Cruzada de Conformidade — GdTs / EHS Directives

Aplicativo web em Python/Streamlit para planejar, executar, registrar e acompanhar auditorias cruzadas de conformidade com GdTs / EHS Directives entre as unidades **SJC, DIA, CAC, JAC, JUN e PER**.

## Arquitetura adotada

A solução foi organizada como um MVP corporativo simples e modular:

```text
app.py                    # Entrada Streamlit e navegação principal
.env.example              # Variáveis de ambiente locais
ehs_audit/
  auth.py                 # Regras simples de perfil e autorização MVP
  calculations.py         # KPIs, conformidade, maturidade e classificação
  config.py               # Configuração, dotenv e paths
  constants.py            # Domínios controlados e diretivas de referência
  db.py                   # Engine SQLAlchemy, sessão, init e seeds
  exporters.py            # Exportação PDF e Excel
  importer.py             # Importador robusto da matriz Excel
  models.py               # Modelos SQLAlchemy
  services.py             # Casos de uso: criar auditoria, salvar checklist, uploads
  ui.py                   # Componentes visuais comuns
uploads/                  # Evidências anexadas localmente
data/                     # SQLite local padrão
tests/                    # Testes básicos pytest
```

A aplicação usa SQLAlchemy para manter compatibilidade com migração futura para SQL Server via `mssql+pyodbc`, mas inicia por padrão com SQLite local.

## Instalação

Requer Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Configuração

Por padrão, o banco é criado automaticamente em:

```text
data/ehs_audit.db
```

Variáveis relevantes:

```env
DATABASE_URL=sqlite:///data/ehs_audit.db
APP_ENV=development
```

## Execução

```bash
streamlit run app.py
```

Na primeira execução, o sistema cria as tabelas e popula:

- Sites padrão: SJC, DIA, CAC, JAC, JUN, PER;
- Usuário `Admin LAG`;
- Usuários EHS locais por site.

## Fluxo básico de uso

1. Abra o app com `streamlit run app.py`.
2. Na sidebar, selecione o usuário **Admin LAG**.
3. Acesse **Administração > Importar matriz**.
4. Faça upload do arquivo `EHS Directives Gap Assessment_7-20-23.xlsx`.
5. Confira diretivas e requisitos importados.
6. Acesse **Planejamento** e crie uma auditoria para SJC, DIA, CAC, JAC, JUN ou PER.
7. O checklist completo é gerado automaticamente com todos os requisitos ativos.
8. Acesse **Checklist**, filtre por GdT/status/criticidade e preencha respostas.
9. Para desvios, revise a sugestão e crie achados/CAPA manualmente.
10. Acesse **Achados / CAPA** para atualizar plano de ação e eficácia.
11. Acesse **Dashboard** para visão consolidada.
12. Acesse **Relatórios** para exportar PDF, checklist Excel e plano de ação Excel.

## Importação da matriz Excel

O importador:

- percorre abas cujo nome contenha `4.12.xx`;
- extrai código e título da diretiva;
- tenta detectar colunas por nomes como requirement, requisito, question, pergunta, guidance, orientação e evidence;
- se não encontrar cabeçalho, aplica heurística por conteúdo textual;
- ignora linhas vazias;
- evita duplicidade pelo par `diretiva_id + codigo_requisito`;
- registra abas sem requisitos como **lacuna da base de referência**;
- não inventa requisitos para abas vazias.

## Regras implementadas

- Site auditado não pode ser igual ao site auditor líder.
- Auditoria criada gera respostas de checklist para todos os requisitos ativos.
- Status de conformidade segue a regra: Conforme 100%, Parcialmente Conforme 50%, Não Conforme 0%, Não Aplicável fora do denominador e Não Verificado fora do atendimento.
- Maturidade média considera apenas requisitos aplicáveis e verificados.
- Não conformidade crítica aberta bloqueia classificação `Referência / Maduro`.
- Achados não são criados automaticamente: o app apenas sugere criação quando há desvio.

## Migração futura para SQL Server

1. Instale driver ODBC do SQL Server e `pyodbc`.
2. Ajuste `requirements.txt` adicionando `pyodbc`.
3. Configure `DATABASE_URL` no `.env`, por exemplo:

```env
DATABASE_URL=mssql+pyodbc://usuario:senha@servidor/banco?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
```

4. Execute o app; o SQLAlchemy criará as tabelas se o usuário tiver permissão.
5. Em produção, recomenda-se substituir `Base.metadata.create_all` por Alembic migrations.

## Próximas evoluções recomendadas

- Integração SSO/Azure AD e grupos corporativos.
- Trilha de auditoria de alterações por campo.
- Controle formal de aprovação de CAPA e verificação de eficácia.
- Armazenamento de evidências em SharePoint, Blob Storage ou storage corporativo.
- Notificações por e-mail/Teams para ações vencidas.
- Alembic para versionamento de schema.
- Perfis por escopo multisite e segregação reforçada em banco.
- Catálogo editável de criticidade por requisito validado pelo LAG EHS.
