import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base
import re

Base = declarative_base()

class Fornecedor(Base):
    __tablename__ = 'fornecedores'
    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)
    cpf_cnpj = Column(String, unique=True, nullable=False)
    endereco = Column(String)
    telefone = Column(String)

engine = create_engine('sqlite:///fornecedores.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def validar_cpf_cnpj(valor):
    numeros = re.sub(r'\D', '', valor)
    return len(numeros) == 11 or len(numeros) == 14

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

def main():
    st.title("Sistema de Gerenciamento de Fornecedores - Login")

    if "logado" not in st.session_state:
        st.session_state.logado = False
        st.session_state.usuario = None
        st.session_state.login_success = False  # flag para controlar rerun

    if not st.session_state.logado:
        st.subheader("Faça login para continuar")

        with st.form("form_login"):
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            enviar = st.form_submit_button("Entrar")

        if enviar:
            if autenticar(usuario, senha):
                st.session_state.logado = True
                st.session_state.usuario = usuario
                st.session_state.login_success = True  # sinaliza login ok
                st.success(f"Bem-vindo, {usuario}!")
            else:
                st.error("Usuário ou senha incorretos.")

        # Rerun fora do bloco do formulário, controlado pela flag
        if st.session_state.login_success:
            st.session_state.login_success = False
            st.experimental_rerun()

    else:
        st.sidebar.title(f"Usuário: {st.session_state.usuario}")
        menu = ["Cadastrar Fornecedor", "Listar Fornecedores", "Sair"]
        escolha = st.sidebar.selectbox("Menu", menu)

        session = Session()

        if escolha == "Cadastrar Fornecedor":
            st.header("Cadastrar novo fornecedor")

            with st.form("form_cadastro"):
                nome = st.text_input("Nome do fornecedor")
                cpf_cnpj = st.text_input("CPF ou CNPJ")
                endereco = st.text_area("Endereço")
                telefone = st.text_input("Telefone")
                enviar = st.form_submit_button("Cadastrar")

            if enviar:
                if not nome or not cpf_cnpj:
                    st.error("Por favor, preencha os campos obrigatórios: Nome e CPF/CNPJ.")
                elif not validar_cpf_cnpj(cpf_cnpj):
                    st.error("CPF/CNPJ inválido. Deve conter 11 (CPF) ou 14 (CNPJ) dígitos numéricos.")
                else:
                    existe = session.query(Fornecedor).filter_by(cpf_cnpj=cpf_cnpj).first()
                    if existe:
                        st.warning("Fornecedor com esse CPF/CNPJ já está cadastrado.")
                    else:
                        fornecedor = Fornecedor(nome=nome, cpf_cnpj=cpf_cnpj, endereco=endereco, telefone=telefone)
                        session.add(fornecedor)
                        session.commit()
                        st.success("Fornecedor cadastrado com sucesso!")

        elif escolha == "Listar Fornecedores":
            st.header("Fornecedores cadastrados")
            fornecedores = session.query(Fornecedor).all()
            if not fornecedores:
                st.info("Nenhum fornecedor cadastrado.")
            else:
                for f in fornecedores:
                    st.write(f"**ID:** {f.id}  |  **Nome:** {f.nome}  |  **CPF/CNPJ:** {f.cpf_cnpj}")
                    st.write(f"Endereço: {f.endereco}")
                    st.write(f"Telefone: {f.telefone}")
                    st.markdown("---")

        elif escolha == "Sair":
            st.session_state.logado = False
            st.session_state.usuario = None
            st.experimental_rerun()

if __name__ == "__main__":
    main()
