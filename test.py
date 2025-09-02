import streamlit as st
import matplotlib.pyplot as plt

# Título do site
st.title('Meu Site Simples com Streamlit')

# Texto descritivo
st.write('Olá! Este é um site simples criado com Streamlit.')

# Entrada do usuário
nome = st.text_input('Qual é o seu nome?')

if nome:
    st.write(f'Olá, {nome}! Seja bem-vindo ao site.')

# Gráfico simples
st.write('Aqui está um gráfico linear simples:')

x = [1, 2, 3, 4, 5]
y = [2, 4, 6, 8, 10]

fig, ax = plt.subplots()
ax.plot(x, y, marker='o')
ax.set_xlabel('Eixo X')
ax.set_ylabel('Eixo Y')
ax.set_title('Gráfico Linear')

st.pyplot(fig)
