# app_unificador_cr.py
# ------------------------------------------------------------
# App Streamlit para unificar múltiplos arquivos XLSX de CR
# mantendo apenas um cabeçalho na base final.
#
# Como rodar:
#   pip install streamlit pandas openpyxl xlsxwriter
#   streamlit run app_unificador_cr.py
# ------------------------------------------------------------

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Iterable, Optional, Tuple

import pandas as pd
import streamlit as st


# =========================
# Configurações do app
# =========================
st.set_page_config(
    page_title="Unificador de CRs XLSX",
    page_icon="📊",
    layout="wide",
)


# =========================
# Funções auxiliares
# =========================
def limpar_nome_coluna(valor) -> str:
    """Padroniza nomes de colunas sem alterar demais o conteúdo original."""
    if pd.isna(valor):
        return ""
    return str(valor).strip().replace("\n", " ").replace("\r", " ")


def tornar_colunas_unicas(colunas: Iterable[str]) -> list[str]:
    """Garante que não existam nomes de colunas duplicados ou vazios."""
    resultado = []
    contagem = {}

    for i, col in enumerate(colunas, start=1):
        nome = limpar_nome_coluna(col)
        if not nome:
            nome = f"Coluna_{i}"

        if nome in contagem:
            contagem[nome] += 1
            nome_final = f"{nome}_{contagem[nome]}"
        else:
            contagem[nome] = 1
            nome_final = nome

        resultado.append(nome_final)

    return resultado


def detectar_linha_cabecalho(df_bruto: pd.DataFrame) -> int:
    """
    Detecta automaticamente a linha de cabeçalho.

    Para os arquivos CR exportados, normalmente existe uma linha inicial com título,
    uma linha em branco e depois o cabeçalho real contendo campos como:
    Group, Sub-Group, Business Unit, ID, Dates, Type, Status etc.
    """
    termos_fortes = {
        "group",
        "sub-group",
        "business unit",
        "id",
        "dates",
        "type",
        "status",
        "description",
        "closure due date",
        "closed date",
        "date reported",
    }

    melhor_indice = 0
    melhor_pontuacao = -1

    limite = min(len(df_bruto), 30)
    for idx in range(limite):
        valores = [limpar_nome_coluna(v).lower() for v in df_bruto.iloc[idx].tolist()]
        valores_set = set(v for v in valores if v)

        pontuacao = sum(1 for termo in termos_fortes if termo in valores_set)

        # Critério adicional: uma linha de cabeçalho costuma ter muitas células preenchidas
        preenchidas = sum(1 for v in valores if v)
        if preenchidas >= 8:
            pontuacao += 1

        if pontuacao > melhor_pontuacao:
            melhor_pontuacao = pontuacao
            melhor_indice = idx

    return melhor_indice


def ler_arquivo_cr(
    arquivo,
    nome_arquivo: str,
    aba: Optional[str] = None,
    adicionar_origem: bool = True,
) -> Tuple[pd.DataFrame, str, int]:
    """
    Lê um arquivo XLSX, encontra o cabeçalho real e retorna a tabela tratada.
    Remove linhas de título, linhas vazias e cabeçalhos repetidos.
    """
    xls = pd.ExcelFile(arquivo)

    if aba and aba in xls.sheet_names:
        sheet_name = aba
    elif "CR" in xls.sheet_names:
        sheet_name = "CR"
    else:
        sheet_name = xls.sheet_names[0]

    df_bruto = pd.read_excel(xls, sheet_name=sheet_name, header=None, dtype=object)

    if df_bruto.empty:
        return pd.DataFrame(), sheet_name, 0

    linha_cabecalho = detectar_linha_cabecalho(df_bruto)
    cabecalho = tornar_colunas_unicas(df_bruto.iloc[linha_cabecalho].tolist())

    df = df_bruto.iloc[linha_cabecalho + 1 :].copy()
    df.columns = cabecalho

    # Remove colunas totalmente vazias
    df = df.dropna(axis=1, how="all")

    # Remove linhas totalmente vazias
    df = df.dropna(axis=0, how="all")

    # Remove linhas que sejam repetição do cabeçalho dentro da própria base
    if not df.empty:
        primeira_coluna = df.columns[0]
        df = df[df[primeira_coluna].astype(str).str.strip().str.lower() != primeira_coluna.strip().lower()]

        # Critério mais forte: remove linha quando muitos valores são iguais aos nomes das colunas
        colunas_lower = [str(c).strip().lower() for c in df.columns]
        mascara_header_repetido = []
        for _, row in df.iterrows():
            valores_lower = [str(v).strip().lower() for v in row.tolist()]
            iguais = sum(1 for a, b in zip(valores_lower, colunas_lower) if a == b)
            mascara_header_repetido.append(iguais >= max(3, int(len(colunas_lower) * 0.25)))
        df = df.loc[[not x for x in mascara_header_repetido]].copy()

    if adicionar_origem:
        df.insert(0, "Arquivo_Origem", nome_arquivo)
        df.insert(1, "Aba_Origem", sheet_name)

    return df.reset_index(drop=True), sheet_name, linha_cabecalho + 1


def consolidar_arquivos(uploads, adicionar_origem: bool = True) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Consolida todos os arquivos enviados e gera também um log de processamento."""
    bases = []
    logs = []

    for upload in uploads:
        try:
            df, aba_usada, linha_cabecalho = ler_arquivo_cr(
                arquivo=upload,
                nome_arquivo=upload.name,
                adicionar_origem=adicionar_origem,
            )

            bases.append(df)
            logs.append(
                {
                    "Arquivo": upload.name,
                    "Status": "OK",
                    "Aba usada": aba_usada,
                    "Linha do cabeçalho detectada": linha_cabecalho,
                    "Linhas importadas": len(df),
                    "Colunas importadas": len(df.columns),
                    "Erro": "",
                }
            )
        except Exception as erro:
            logs.append(
                {
                    "Arquivo": upload.name,
                    "Status": "Erro",
                    "Aba usada": "",
                    "Linha do cabeçalho detectada": "",
                    "Linhas importadas": 0,
                    "Colunas importadas": 0,
                    "Erro": str(erro),
                }
            )

    if bases:
        # sort=False preserva todas as colunas encontradas sem ordenar alfabeticamente.
        base_final = pd.concat(bases, ignore_index=True, sort=False)
    else:
        base_final = pd.DataFrame()

    log_df = pd.DataFrame(logs)
    return base_final, log_df


def gerar_excel_download(base_final: pd.DataFrame, log_df: pd.DataFrame) -> bytes:
    """Gera um XLSX em memória com a base consolidada e uma aba de log."""
    output = BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter", datetime_format="dd/mm/yyyy", date_format="dd/mm/yyyy") as writer:
        base_final.to_excel(writer, sheet_name="Base Consolidada", index=False)
        log_df.to_excel(writer, sheet_name="Log", index=False)

        workbook = writer.book

        formato_titulo = workbook.add_format(
            {
                "bold": True,
                "font_color": "white",
                "bg_color": "#1F4E78",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            }
        )
        formato_texto = workbook.add_format({"border": 1, "valign": "top"})

        for sheet_name, df in [("Base Consolidada", base_final), ("Log", log_df)]:
            worksheet = writer.sheets[sheet_name]
            worksheet.freeze_panes(1, 0)
            worksheet.autofilter(0, 0, max(len(df), 1), max(len(df.columns) - 1, 0))

            for col_idx, col_name in enumerate(df.columns):
                worksheet.write(0, col_idx, col_name, formato_titulo)

                # Ajuste robusto de largura: trata números, datas, NaN/NA e qualquer objeto
                # sem depender de len() diretamente no valor original.
                if not df.empty:
                    serie_coluna = df.iloc[:, col_idx]
                    amostra = serie_coluna.head(500).map(
                        lambda valor: "" if pd.isna(valor) else str(valor)
                    ).tolist()
                else:
                    amostra = []

                tamanhos = [len(str(col_name))]
                tamanhos.extend(len(str(valor)) for valor in amostra)
                largura = max(tamanhos) + 2
                largura = min(max(largura, 10), 45)
                worksheet.set_column(col_idx, col_idx, largura, formato_texto)

    return output.getvalue()


# =========================
# Interface Streamlit
# =========================
st.title("📊 Unificador de CRs em XLSX")
st.caption("Envie quantos arquivos de CR quiser. O app retorna um único XLSX consolidado, mantendo apenas um cabeçalho.")

with st.expander("Como usar", expanded=False):
    st.markdown(
        """
        1. Clique em **Browse files** e selecione todos os arquivos `.xlsx` de CR.
        2. O app identifica automaticamente o cabeçalho real da planilha.
        3. As linhas de título e cabeçalhos repetidos são removidas.
        4. Clique em **Baixar XLSX consolidado**.
        """
    )

adicionar_origem = st.checkbox(
    "Adicionar colunas de origem do arquivo e da aba",
    value=True,
    help="Recomendado para rastrear de qual arquivo cada linha veio.",
)

uploads = st.file_uploader(
    "Submeta os arquivos XLSX de CR",
    type=["xlsx"],
    accept_multiple_files=True,
)

if not uploads:
    st.info("Envie um ou mais arquivos `.xlsx` para iniciar a consolidação.")
    st.stop()

base_final, log_df = consolidar_arquivos(uploads, adicionar_origem=adicionar_origem)

st.subheader("Resumo do processamento")
st.dataframe(log_df, use_container_width=True)

if base_final.empty:
    st.error("Nenhuma linha foi consolidada. Verifique se os arquivos possuem dados válidos.")
    st.stop()

col1, col2, col3 = st.columns(3)
col1.metric("Arquivos enviados", len(uploads))
col2.metric("Linhas consolidadas", f"{len(base_final):,}".replace(",", "."))
col3.metric("Colunas finais", len(base_final.columns))

st.subheader("Prévia da base consolidada")
st.dataframe(base_final.head(1000), use_container_width=True)

arquivo_excel = gerar_excel_download(base_final, log_df)

st.download_button(
    label="⬇️ Baixar XLSX consolidado",
    data=arquivo_excel,
    file_name="CRs_consolidadas.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.success("Arquivo consolidado pronto para download.")
