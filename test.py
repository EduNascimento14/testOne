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

def validar_cpf_cnpj(valor):
    numeros = re.sub(r'\D', '', valor)
    return len(numeros) == 11 or len(numeros) == 14

# Configuração do banco SQLite
engine = create_engine('sqlite:///fornecedores.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def main():
    st.title("Cadastro de Fornecedores de Destinação de Resíduos")

    session = Session()

    menu = ["Cadastrar Fornecedor", "Listar Fornecedores"]
    escolha = st.sidebar.selectbox("Menu", menu)

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
                # Verificar se já existe fornecedor com mesmo CPF/CNPJ
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

if __name__ == "__main__":
    main()
