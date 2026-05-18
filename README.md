# NR-12 Manager — Sustentação da Conformidade

Aplicativo MVP em Python/Streamlit para gestão de sustentação da conformidade NR-12 em máquinas e equipamentos industriais.

## Funcionalidades

- Login simples com perfis: Admin Corporativo, EHS Site, Manutenção, Produção / Operação e Visualizador.
- Inventário completo de máquinas por site, área, status e criticidade.
- Controle documental NR-12 com cálculo automático de vencido/próximo do vencimento em 60 dias.
- Auditorias e inspeções com checklist padrão de sustentação NR-12, cálculo de pontuação e geração de planos de ação.
- Planos de ação com classificação, prazo, evidência e validação EHS.
- Gestão de mudanças/intervenções com alertas para mudanças críticas sem aprovação.
- Dashboard corporativo com KPIs e gráficos Plotly.
- Exportações Excel para inventário, documentos, auditorias e plano de ação; PDF por máquina.
- Banco SQLite local com preparo para SQL Server via variável `DATABASE_URL`.

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Execução

```bash
streamlit run nr12_manager.py
```

Na primeira execução o banco `nr12_app.db` é criado automaticamente com dados iniciais.

## Usuários iniciais

| Usuário | Perfil | Senha |
| --- | --- | --- |
| Eduardo | Admin Corporativo | `admin123` |
| Capitu | Admin Corporativo | `admin123` |

## Dados iniciais

- Sites: SJC, DIA, CAC, JAC, JUN e PER.
- Duas máquinas fictícias para teste.
- Checklist padrão de 15 itens de sustentação NR-12.
- Documentos, auditoria e ação crítica fictícios para validar dashboard e regras.

## Regras de negócio implementadas

- Documento com validade vencida vira `Vencido`; documento com validade em até 60 dias vira `Próximo do vencimento`.
- Documentos obrigatórios essenciais: Laudo NR-12, ART e Apreciação de risco.
- Pontuação da auditoria = itens conformes / itens aplicáveis.
- Auditoria fica `Não conforme` quando houver item crítico não conforme ou pontuação menor que 70%.
- Auditoria fica `Conforme com ressalvas` entre 70% e 89%.
- Auditoria fica `Conforme` com 90% ou mais e sem item crítico não conforme.
- Itens não conformes marcados no checklist geram planos de ação automaticamente.
- Ação crítica aberta/vencida, documentação essencial ausente/vencida, última auditoria não conforme e mudança crítica sem validação bloqueiam status `Conforme`.
- Mudanças em sistemas de segurança exigem MOC, aprovação EHS e manutenção ou engenharia.
- Ação concluída exige evidência e validação EHS.

## Estrutura principal

```text
nr12_manager.py
database.py
models.py
auth.py
pages/
  01_dashboard.py
  02_inventario_maquinas.py
  03_documentos_nr12.py
  04_auditorias_inspecoes.py
  05_planos_acao.py
  06_gestao_mudancas.py
  07_relatorios.py
  08_admin.py
utils/
  calculations.py
  exports.py
  validations.py
  seed_data.py
```

## Migração futura para SQL Server

Configure a variável de ambiente `DATABASE_URL` com a string SQLAlchemy do SQL Server, por exemplo:

```bash
export DATABASE_URL='mssql+pyodbc://usuario:senha@servidor/base?driver=ODBC+Driver+18+for+SQL+Server'
```

O restante do app usa SQLAlchemy e não depende diretamente do SQLite.
