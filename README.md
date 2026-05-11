# Auditoria Cruzada de Conformidade — GdTs / EHS Directives

Aplicativo web em Python/Streamlit para planejar, executar, registrar e acompanhar auditorias cruzadas de conformidade com GdTs / EHS Directives entre as unidades **SJC, DIA, CAC, JAC, JUN e PER**.

A base do checklist já vem incorporada ao sistema em português. Na primeira execução, o banco é criado automaticamente e recebe as 19 GdTs e os 221 requisitos auditáveis ativos. As GdTs **4.12.02** e **4.12.19** são cadastradas sem requisitos, com observação de lacuna da base de referência.

## Arquitetura adotada

A solução está organizada como um MVP corporativo simples e modular:

```text
app.py                    # Entrada Streamlit e navegação principal
.env.example              # Variáveis de ambiente locais
ehs_audit/
  auth.py                 # Regras simples de perfil e autorização MVP
  calculations.py         # KPIs, conformidade, maturidade e classificação
  checklist_seed.py       # Base incorporada de GdTs/requisitos e seed idempotente
  config.py               # Configuração, dotenv e paths
  constants.py            # Domínios controlados
  db.py                   # Engine SQLAlchemy, sessão, init e seeds
  exporters.py            # Exportação PDF e Excel
  models.py               # Modelos SQLAlchemy
  services.py             # Casos de uso: criar auditoria, salvar checklist, evidências
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

Na primeira execução, o sistema cria as tabelas e popula automaticamente:

- Sites padrão: SJC, DIA, CAC, JAC, JUN, PER;
- Usuário `Admin LAG`;
- Usuários EHS locais por site;
- 19 GdTs corporativas;
- 221 requisitos auditáveis em português;
- observação de lacuna para as GdTs 4.12.02 e 4.12.19.

## Fluxo básico de uso

1. Abra o app com `streamlit run app.py`.
2. Na sidebar, selecione o usuário desejado.
3. Acesse **Administração > Base do Checklist** para consultar a base incorporada, contagens, GdTs e requisitos.
4. Acesse **Planejamento** e crie uma auditoria para SJC, DIA, CAC, JAC, JUN ou PER.
5. O checklist completo é gerado automaticamente com todos os requisitos ativos.
6. Acesse **Checklist**, filtre por GdT/status/criticidade e preencha respostas.
7. Para desvios, revise a sugestão e crie achados/CAPA manualmente.
8. Acesse **Achados / CAPA** para atualizar plano de ação e eficácia.
9. Acesse **Dashboard** para visão consolidada.
10. Acesse **Relatórios** para exportar PDF, checklist Excel e plano de ação Excel.

## Base do checklist

A página **Administração** contém a área **Base do Checklist**, onde é possível:

- visualizar as GdTs cadastradas;
- visualizar requisitos cadastrados;
- consultar contagem de diretivas, requisitos totais e requisitos ativos;
- editar criticidade;
- ativar ou desativar requisito;
- reexecutar o seed idempotente da base quando necessário.

O seed é seguro para reexecução: ele insere itens ausentes e atualiza textos base sem duplicar registros existentes.

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
