import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, joinedload
import re
import os
import json
from datetime import datetime
import plotly.express as px

Base = declarative_base()

# --- Modelos ---

class Fornecedor(Base):
    __tablename__ = 'fornecedores'
    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)
    cpf_cnpj = Column(String, unique=True, nullable=False)
    endereco = Column(String)
    telefone = Column(String)
    
    documentos = relationship("Documento", back_populates="fornecedor")
    auditoria = relationship("Auditoria", uselist=False, back_populates="fornecedor")
    planos_acao = relationship("PlanoAcao", back_populates="fornecedor")
    contratos = relationship("Contrato", back_populates="fornecedor")

class Documento(Base):
    __tablename__ = 'documentos'
    id = Column(Integer, primary_key=True)
    fornecedor_id = Column(Integer, ForeignKey('fornecedores.id'))
    tipo = Column(String)
    arquivo = Column(String)
    data_inicio = Column(Date)
    data_validade = Column(Date)
    
    fornecedor = relationship("Fornecedor", back_populates="documentos")

class Auditoria(Base):
    __tablename__ = 'auditorias'
    id = Column(Integer, primary_key=True)
    fornecedor_id = Column(Integer, ForeignKey('fornecedores.id'))
    respostas = Column(String)  # JSON string para simplificar
    score = Column(Integer)
    classificado = Column(String)  # "Conforme" ou "Não Conforme"
    
    fornecedor = relationship("Fornecedor", back_populates="auditoria")

class PlanoAcao(Base):
    __tablename__ = 'planos_acao'
    id = Column(Integer, primary_key=True)
    fornecedor_id = Column(Integer, ForeignKey('fornecedores.id'))
    descricao = Column(String)
    data_inicio = Column(Date)
    data_fim = Column(Date)
    status_mensal = Column(String)  # JSON string com checklist mensal
    
    fornecedor = relationship("Fornecedor", back_populates="planos_acao")

class Contrato(Base):
    __tablename__ = 'contratos'
    id = Column(Integer, primary_key=True)
    fornecedor_id = Column(Integer, ForeignKey('fornecedores.id'))
    arquivo = Column(String)
    data_assinatura = Column(Date)
    data_validade = Column(Date)
    
    fornecedor = relationship("Fornecedor", back_populates="contratos")

# --- Setup banco e sessão ---

engine = create_engine('sqlite:///fornecedores.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine, expire_on_commit=False)  # Evita DetachedInstanceError

# --- Funções utilitárias ---

def validar_cpf_cnpj(valor):
    numeros = re.sub(r'\D', '', valor)
    return len(numeros) == 11 or len(numeros) == 14

def salvar_arquivo(uploaded_file, pasta_destino, nome_prefixo):
    if not os.path.exists(pasta_destino):
        os.makedirs(pasta_destino)
    caminho = os.path.join(pasta_destino, f"{nome_prefixo}_{uploaded_file.name}")
    with open(caminho, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return caminho

def exibir_preview_arquivo(caminho, mime_type):
    ext = os.path.splitext(caminho)[1].lower()
    try:
        if mime_type is None:
            if ext in ['.png', '.jpg', '.jpeg']:
                mime_type = f"image/{ext[1:]}"
            elif ext == '.pdf':
                mime_type = "application/pdf"
            else:
                mime_type = "application/octet-stream"

        if "image" in mime_type:
            st.image(caminho)
        elif mime_type == "application/pdf":
            with open(caminho, "rb") as f:
                base64_pdf = f.read()
            st.download_button(label="Download PDF", data=base64_pdf, file_name=os.path.basename(caminho))
            st.markdown(f"[Visualizar PDF](./{caminho})")
        else:
            st.write(f"Arquivo salvo: {os.path.basename(caminho)}")
    except Exception as e:
        st.error(f"Erro ao exibir arquivo: {e}")

# --- Checklist da auditoria ---

PERGUNTAS_AUDITORIA = [
    "A empresa possui o sistema de gestão ISO 14001?",
    "A empresa possui licença do órgão ambiental responsável? (Licença Instalação/Operação/polícia federal/CADRI/ Outorga)",
    "Há evidências de que as restrições da licença estão sendo cumpridas?",
    "A empresa sofreu alguma autuação ambiental nos últimos anos?",
    "Há evidências de visitas fiscalizadoras do órgão ambiental? (3 últimos laudos de inspeção)",
    "Existe alguma estrutura de documentação do sistema de gestão (manual, procedimentos, instruções de trabalho) e de controle de registros?",
    "A empresa possui uma Política (Qualidade, Meio Ambiente, Segurança) com objetivos e metas estabelecidos?",
    "A empresa realizou levantamento de seus aspectos e impactos ambientais estabelecendo controle sobre os significativos?",
    "O espaço físico (tamanho) é suficiente para receber a quantidade de material gerado pela Parker?",
    "A empresa possui ETE para tratar seus resíduos líquidos?",
    "Caso exista ETE, são realizadas análises do efluente tratado?",
    "A empresa possui sua área coberta para armazenagem dos resíduos?",
    "A empresa possui sua área impermeabilizada?",
    "Os equipamentos de transporte (caminhões e caçambas) estão em bom estado de conservação? Para os caminhões é feito o controle de índice de fumaça preta? (MOPE -motorista / operacionalidade Diesel do caminhão)",
    "A empresa possui licença do IBAMA?",
    "A empresa destina seus resíduos sólidos adequadamente, caso os gere?",
    "A empresa possui Alvará do Corpo de Bombeiros? E alvará municipal de funcionamento?",
    "Todos os funcionários da empresa são registrados?",
    "Os funcionários trabalham uniformizados e com os devidos EPI`s pertinentes ao seu serviço?",
    "A empresa atende as chamadas para as retiradas com pontualidade?",
    "Os funcionários da empresa recebem, frequentemente, treinamentos sobre saúde, segurança e meio ambiente?",
]

# --- Usuários para login ---
USUARIOS = {
    "usuario1": "senha1",
    "usuario2": "senha2",
    "usuario3": "senha3",
    "usuario4": "senha4",
    "usuario5": "senha5",
    "usuario6": "senha6",
    "usuario7": "senha7",
    "usuario8": "senha8",
}

def autenticar(usuario, senha):
    return USUARIOS.get(usuario) == senha

# --- App Streamlit ---

def main():
    # Controle de login
    if "logado" not in st.session_state:
        st.session_state.logado = False
        st.session_state.usuario = None

    if not st.session_state.logado:
        st.title("Sistema de Gerenciamento de Fornecedores - Login")
        with st.form("form_login"):
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            enviar = st.form_submit_button("Entrar")

        if enviar:
            if autenticar(usuario, senha):
                st.session_state.logado = True
                st.session_state.usuario = usuario
                st.success(f"Bem-vindo, {usuario}!")
                st.experimental_rerun()
            else:
                st.error("Usuário ou senha incorretos.")
        return

    # Após login
    st.sidebar.title(f"Usuário: {st.session_state.usuario}")
    menu = st.sidebar.selectbox("Menu", [
        "Overview",
        "Cadastrar Fornecedor",
        "Visualizar Fornecedores",
        "Sair"
    ])

    session = Session()

    if menu == "Overview":
        st.header("Resumo Geral dos Fornecedores")

        total_fornecedores = session.query(Fornecedor).count()
        conformes = session.query(Auditoria).filter(Auditoria.classificado == "Conforme").count()
        nao_conformes = session.query(Auditoria).filter(Auditoria.classificado == "Não Conforme").count()

        fornecedores_com_contrato = session.query(Fornecedor).join(Contrato).distinct().count()
        fornecedores_sem_contrato = total_fornecedores - fornecedores_com_contrato

        # Gráficos com plotly
        fig_total = px.pie(
            names=["Conforme", "Não Conforme"],
            values=[conformes, nao_conformes],
            title="Classificação da Auditoria"
        )
        st.plotly_chart(fig_total, use_container_width=True)

        fig_contrato = px.pie(
            names=["Com Contrato", "Sem Contrato"],
            values=[fornecedores_com_contrato, fornecedores_sem_contrato],
            title="Situação Contratual"
        )
        st.plotly_chart(fig_contrato, use_container_width=True)

        st.metric("Total de Fornecedores", total_fornecedores)
        st.metric("Fornecedores Conformes", conformes)
        st.metric("Fornecedores Não Conformes", nao_conformes)
        st.metric("Fornecedores com Contrato", fornecedores_com_contrato)
        st.metric("Fornecedores sem Contrato", fornecedores_sem_contrato)

        st.markdown("### Insights")
        if nao_conformes > 0:
            st.warning(f"Existem {nao_conformes} fornecedores classificados como Não Conforme. Recomenda-se auditorias e planos de ação.")
        else:
            st.success("Todos os fornecedores estão classificados como Conforme.")

        if fornecedores_sem_contrato > 0:
            st.warning(f"Existem {fornecedores_sem_contrato} fornecedores sem contrato formalizado.")
        else:
            st.success("Todos os fornecedores possuem contrato formalizado.")

    elif menu == "Cadastrar Fornecedor":
        st.header("Cadastrar novo fornecedor")
        with st.form("form_cadastro"):
            nome = st.text_input("Nome do fornecedor")
            cpf_cnpj = st.text_input("CPF ou CNPJ")
            endereco = st.text_area("Endereço")
            telefone = st.text_input("Telefone")
            enviar = st.form_submit_button("Cadastrar")

        if enviar:
            if not nome or not cpf_cnpj:
                st.error("Nome e CPF/CNPJ são obrigatórios.")
            elif not validar_cpf_cnpj(cpf_cnpj):
                st.error("CPF/CNPJ inválido.")
            else:
                existe = session.query(Fornecedor).filter_by(cpf_cnpj=cpf_cnpj).first()
                if existe:
                    st.warning("Fornecedor já cadastrado.")
                else:
                    fornecedor = Fornecedor(nome=nome, cpf_cnpj=cpf_cnpj, endereco=endereco, telefone=telefone)
                    session.add(fornecedor)
                    session.commit()
                    st.success("Fornecedor cadastrado com sucesso!")

    elif menu == "Visualizar Fornecedores":
        st.header("Fornecedores cadastrados")
        fornecedores = session.query(Fornecedor).options(
            joinedload(Fornecedor.documentos),
            joinedload(Fornecedor.auditoria),
            joinedload(Fornecedor.planos_acao),
            joinedload(Fornecedor.contratos)
        ).all()
        if not fornecedores:
            st.info("Nenhum fornecedor cadastrado.")
            return

        fornecedor_selecionado = st.selectbox("Selecione o fornecedor", fornecedores, format_func=lambda f: f.nome)

        if fornecedor_selecionado:
            tabs = st.tabs(["Informações", "Documentação", "Auditoria", "Planos de Ação", "Contratos"])

            with tabs[0]:
                st.subheader("Informações Básicas")
                st.write(f"**Nome:** {fornecedor_selecionado.nome}")
                st.write(f"**CPF/CNPJ:** {fornecedor_selecionado.cpf_cnpj}")
                st.write(f"**Endereço:** {fornecedor_selecionado.endereco}")
                st.write(f"**Telefone:** {fornecedor_selecionado.telefone}")

            with tabs[1]:
                st.subheader("Documentação")
                tipos_documentos = [
                    "Licença Ambiental de Operação",
                    "Alvará de Funcionamento",
                    "Comprovante de regularidade (CETESB ou órgão estadual)",
                    "Certificado de regularidade do IBAMA CTF/APP",
                    "Consulta de Área Contaminada"
                ]
                tipo_doc = st.selectbox("Tipo de Documento para Upload", tipos_documentos)
                arquivo_doc = st.file_uploader("Anexar Documento", type=["pdf", "jpg", "png", "jpeg"])
                data_inicio = st.date_input("Data de Início")
                data_validade = st.date_input("Data de Validade")

                if st.button("Salvar Documento"):
                    if arquivo_doc is None:
                        st.error("Envie um arquivo.")
                    else:
                        caminho = salvar_arquivo(arquivo_doc, "uploads/documentos", f"{fornecedor_selecionado.id}_{tipo_doc}")
                        doc = Documento(
                            fornecedor_id=fornecedor_selecionado.id,
                            tipo=tipo_doc,
                            arquivo=caminho,
                            data_inicio=data_inicio,
                            data_validade=data_validade
                        )
                        session.add(doc)
                        session.commit()
                        st.success("Documento salvo com sucesso!")
                        exibir_preview_arquivo(caminho, arquivo_doc.type)

                st.markdown("### Documentos Cadastrados")
                docs = session.query(Documento).filter_by(fornecedor_id=fornecedor_selecionado.id).all()
                for d in docs:
                    st.write(f"- {d.tipo} (Início: {d.data_inicio}, Validade: {d.data_validade})")
                    if os.path.exists(d.arquivo):
                        exibir_preview_arquivo(d.arquivo, None)

            with tabs[2]:
                st.subheader("Auditoria")
                auditoria = session.query(Auditoria).filter_by(fornecedor_id=fornecedor_selecionado.id).first()
                respostas = {}
                if auditoria:
                    respostas = json.loads(auditoria.respostas)

                with st.form("form_auditoria"):
                    respostas_form = {}
                    for i, pergunta in enumerate(PERGUNTAS_AUDITORIA, 1):
                        default = respostas.get(str(i), None)
                        respostas_form[str(i)] = st.radio(f"{i}) {pergunta}", ["Sim", "Não"], index=0 if default=="Sim" else 1)

                    enviar_aud = st.form_submit_button("Salvar Auditoria")

                if enviar_aud:
                    total = len(PERGUNTAS_AUDITORIA)
                    aprovados = sum(1 for r in respostas_form.values() if r == "Sim")
                    score = int((aprovados / total) * 100)
                    classificado = "Conforme" if score >= 80 else "Não Conforme"

                    if auditoria is None:
                        auditoria = Auditoria(
                            fornecedor_id=fornecedor_selecionado.id,
                            respostas=json.dumps(respostas_form),
                            score=score,
                            classificado=classificado
                        )
                        session.add(auditoria)
                    else:
                        auditoria.respostas = json.dumps(respostas_form)
                        auditoria.score = score
                        auditoria.classificado = classificado
                    session.commit()
                    st.success(f"Auditoria salva. Score: {score}%. Classificação: {classificado}")

                if auditoria:
                    st.markdown(f"**Última auditoria:** Score {auditoria.score}%, Classificação: {auditoria.classificado}")

            with tabs[3]:
                st.subheader("Planos de Ação")
                descricao = st.text_area("Descrição da Ação")
                data_inicio = st.date_input("Data de Início da Ação")
                data_fim = st.date_input("Data Final da Ação")

                if st.button("Adicionar Plano de Ação"):
                    if not descricao:
                        st.error("Descreva a ação.")
                    elif data_fim < data_inicio:
                        st.error("Data final deve ser maior ou igual à data inicial.")
                    else:
                        plano = PlanoAcao(
                            fornecedor_id=fornecedor_selecionado.id,
                            descricao=descricao,
                            data_inicio=data_inicio,
                            data_fim=data_fim,
                            status_mensal=json.dumps({})
                        )
                        session.add(plano)
                        session.commit()
                        st.success("Plano de ação adicionado.")

                planos = session.query(PlanoAcao).filter_by(fornecedor_id=fornecedor_selecionado.id).all()
                for p in planos:
                    st.markdown(f"**{p.descricao}** - De {p.data_inicio} até {p.data_fim}")

            with tabs[4]:
                st.subheader("Contratos")
                arquivo_contrato = st.file_uploader("Anexar Contrato", type=["pdf", "docx", "doc"])
                data_assinatura = st.date_input("Data de Assinatura do Contrato")
                data_validade = st.date_input("Data de Validade do Contrato")

                if st.button("Salvar Contrato"):
                    if arquivo_contrato is None:
                        st.error("Envie um arquivo.")
                    else:
                        caminho = salvar_arquivo(arquivo_contrato, "uploads/contratos", f"{fornecedor_selecionado.id}_contrato")
                        contrato = Contrato(
                            fornecedor_id=fornecedor_selecionado.id,
                            arquivo=caminho,
                            data_assinatura=data_assinatura,
                            data_validade=data_validade
                        )
                        session.add(contrato)
                        session.commit()
                        st.success("Contrato salvo com sucesso!")
                        exibir_preview_arquivo(caminho, arquivo_contrato.type)

                contratos = session.query(Contrato).filter_by(fornecedor_id=fornecedor_selecionado.id).all()
                for c in contratos:
                    st.write(f"- Assinado em: {c.data_assinatura}, Validade: {c.data_validade}")
                    if os.path.exists(c.arquivo):
                        exibir_preview_arquivo(c.arquivo, None)

    elif menu == "Sair":
        st.session_state.logado = False
        st.session_state.usuario = None
        st.experimental_rerun()

if __name__ == "__main__":
    main()
