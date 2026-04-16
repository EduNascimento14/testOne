
import io
import os
import re
import unicodedata
from itertools import combinations

import numpy as np
import pandas as pd
import streamlit as st


st.set_page_config(page_title="Análise BID de EPIs", layout="wide")


def clean_text(x):
    if pd.isna(x):
        return None
    s = str(x).replace("\xa0", " ").strip()
    s = re.sub(r"\s+", " ", s)
    return s if s and s.lower() != "nan" else None


def normalize_text(s):
    s = clean_text(s)
    if s is None:
        return None
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.upper()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def categorize(epi_norm):
    e = epi_norm or ""
    if any(k in e for k in ["BOTA", "BOTINA", "SAPATO", "CALCADO", "CALÇADO"]):
        return "Botas/Sapatos"
    if "OCULOS" in e or "ÓCULOS" in e:
        return "Óculos"
    if "PROTETOR AURICULAR" in e or "TIPO CONCHA" in e or "ABAFADOR" in e:
        return "Proteção auditiva"
    return "Outros"


def make_unique(headers):
    counts = {}
    out = []
    for h in headers:
        h = h if h is not None else ""
        if h not in counts:
            counts[h] = 1
            out.append(h)
        else:
            counts[h] += 1
            out.append(f"{h}_{counts[h]}")
    return out


def parse_template_file(file_name, file_bytes):
    supplier = os.path.basename(file_name).replace("BID_", "").replace(".xlsx", "").upper()
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0, header=None)

    header_row = None
    for i, row in df.iterrows():
        vals = [clean_text(x).upper() for x in row.tolist() if clean_text(x)]
        if "EPI" in vals:
            header_row = i
            break

    if header_row is None:
        return None

    headers = make_unique([clean_text(x) for x in df.iloc[header_row].tolist()])
    data = df.iloc[header_row + 1 :].copy()
    data.columns = headers
    data = data.dropna(how="all")

    rename = {}
    delivery_count = 0
    for c in data.columns:
        uc = c.upper()
        if uc == "EPI":
            rename[c] = "epi"
        elif uc.startswith("DIVISÃO"):
            rename[c] = "division"
        elif uc == "CA ORÇADO":
            rename[c] = "ca_orcado"
        elif uc == "CA":
            rename[c] = "ca"
        elif "FABRICANTE" in uc:
            rename[c] = "manufacturer"
        elif "UNIDADE" in uc:
            rename[c] = "unit"
        elif "QUANTIDADE SEMESTRAL" in uc:
            rename[c] = "qty_semester"
        elif "QUANTIDADE ANUAL" in uc:
            rename[c] = "qty_annual"
        elif "PREÇO SP" in uc:
            rename[c] = "price_sp"
        elif "PREÇO RS" in uc:
            rename[c] = "price_rs"
        elif (uc.startswith("PREÇO") or "PREÇO (R$)" in uc) and "VIGÊNCIA" not in uc:
            rename[c] = "unit_price"
        elif "QTD MÍNIMA" in uc:
            rename[c] = "min_delivery"
        elif "TEMPO DE ENTREGA" in uc or uc == "ENTREGA":
            delivery_count += 1
            rename[c] = f"delivery_{delivery_count}"
        elif "VIGÊNCIA" in uc:
            rename[c] = "price_validity"
        elif "OBSERVA" in uc:
            rename[c] = "obs"
        elif "MULTIPLO" in uc:
            rename[c] = "multiple"

    data = data.rename(columns=rename)

    if "ca_orcado" not in data.columns and "ca" in data.columns:
        data["ca_orcado"] = data["ca"]

    if "unit_price" not in data.columns:
        if "price_sp" in data.columns or "price_rs" in data.columns:
            def choose_price(r):
                div = (clean_text(r.get("division")) or "").upper()
                sp = r.get("price_sp", np.nan)
                rs = r.get("price_rs", np.nan)
                if "SP" in div and pd.notna(sp):
                    return sp
                if "RS" in div and pd.notna(rs):
                    return rs
                return sp if pd.notna(sp) else rs

            data["unit_price"] = data.apply(choose_price, axis=1)
        else:
            data["unit_price"] = np.nan

    delivery_cols = [c for c in data.columns if c.startswith("delivery_")]
    if delivery_cols:
        if len(delivery_cols) >= 2 and ("price_sp" in data.columns or "price_rs" in data.columns):
            def choose_delivery(r):
                div = (clean_text(r.get("division")) or "").upper()
                if "SP" in div:
                    return r.get(delivery_cols[0])
                if "RS" in div and len(delivery_cols) >= 2:
                    return r.get(delivery_cols[1])
                return r.get(delivery_cols[0])

            data["delivery_raw"] = data.apply(choose_delivery, axis=1)
        else:
            data["delivery_raw"] = data[delivery_cols].bfill(axis=1).iloc[:, 0]
    else:
        data["delivery_raw"] = np.nan

    for col in ["qty_annual", "qty_semester", "unit_price", "min_delivery", "multiple"]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")

    def parse_days(v):
        if pd.isna(v):
            return np.nan
        if isinstance(v, (int, float, np.number)):
            return float(v)
        m = re.search(r"(\d+(?:[.,]\d+)?)", str(v))
        return float(m.group(1).replace(",", ".")) if m else np.nan

    data["delivery_days"] = data["delivery_raw"].map(parse_days)
    data["supplier"] = supplier

    keep = [
        "supplier", "division", "epi", "ca_orcado", "manufacturer", "unit",
        "qty_semester", "qty_annual", "unit_price", "delivery_days",
        "min_delivery", "price_validity", "multiple", "obs"
    ]
    for k in keep:
        if k not in data.columns:
            data[k] = np.nan

    data = data[keep].copy()
    for col in ["division", "epi", "ca_orcado", "manufacturer", "unit", "price_validity", "obs"]:
        data[col] = data[col].map(clean_text)

    data = data[data["epi"].notna()]
    return data.reset_index(drop=True)


def parse_roan_file(file_name, file_bytes):
    supplier = "ROAN"
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0)
    df.columns = [clean_text(c) or f"col{i}" for i, c in enumerate(df.columns)]
    rename = {}
    for c in df.columns:
        uc = c.upper()
        if uc == "ITEM":
            rename[c] = "item_desc"
        elif uc == "VALOR":
            rename[c] = "unit_price"
        elif "UNIDADE" in uc:
            rename[c] = "unit"
    df = df.rename(columns=rename)
    df["supplier"] = supplier
    df["item_desc"] = df["item_desc"].map(clean_text)
    df["unit"] = df["unit"].map(clean_text)
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df["ca_extraido"] = df["item_desc"].str.extract(r"CA\s*(\d+)", expand=False)
    df["categoria_core"] = df["item_desc"].map(normalize_text).map(categorize)
    return df[["supplier", "item_desc", "unit_price", "unit", "ca_extraido", "categoria_core"]]


def analyze_uploaded_files(uploaded_files):
    parsed = {}
    status_rows = []

    for f in uploaded_files:
        file_bytes = f.getvalue()
        supplier_name = os.path.basename(f.name).replace("BID_", "").replace(".xlsx", "").upper()

        if "ROAN" in supplier_name:
            roan_df = parse_roan_file(f.name, file_bytes)
            parsed["ROAN"] = roan_df
            status_rows.append({
                "Fornecedor": "ROAN",
                "Status": "Parcial",
                "Motivo": "Arquivo fora do template padrão; comparação apenas indicativa."
            })
            continue

        data = parse_template_file(f.name, file_bytes)
        if data is None:
            status_rows.append({
                "Fornecedor": supplier_name,
                "Status": "Erro",
                "Motivo": "Não foi possível identificar o cabeçalho padrão."
            })
            continue

        data["epi_norm"] = data["epi"].map(normalize_text)
        data["categoria_core"] = data["epi_norm"].map(categorize)
        valid_prices = int((data["unit_price"].fillna(0) > 0).sum())

        if supplier_name == "SAFETY":
            status_rows.append({
                "Fornecedor": supplier_name,
                "Status": "Excluído da análise de preço",
                "Motivo": f"Apenas {valid_prices} linhas com preço > 0."
            })
        else:
            status_rows.append({
                "Fornecedor": supplier_name,
                "Status": "Incluído",
                "Motivo": f"{valid_prices} linhas com preço > 0."
            })

        parsed[supplier_name] = data

    status_df = pd.DataFrame(status_rows)

    analysis_suppliers = [s for s in parsed if s not in ["ROAN", "SAFETY"]]
    if not analysis_suppliers:
        return {"status_df": status_df, "erro": "Nenhum fornecedor válido para analisar."}

    main = pd.concat([parsed[s].copy() for s in analysis_suppliers], ignore_index=True)
    main["division_norm"] = main["division"].map(normalize_text)
    main["epi_norm"] = main["epi"].map(normalize_text)
    main = main[main["epi_norm"].notna() & ~main["epi_norm"].str.fullmatch(r"\d+")]
    main.loc[main["unit_price"] <= 0, "unit_price"] = np.nan
    main["demand_key"] = main["division_norm"].fillna("") + "|" + main["epi_norm"].fillna("")
    main["annual_value"] = main["qty_annual"] * main["unit_price"]

    demand = main.groupby("demand_key").agg(
        division=("division", "first"),
        epi=("epi", "first"),
        qty_annual=("qty_annual", "max"),
        qty_semester=("qty_semester", "max"),
        ca_orcado=("ca_orcado", "first"),
        unit=("unit", "first"),
        categoria_core=("categoria_core", "first"),
    ).reset_index()

    valid = main[main["unit_price"].notna()].sort_values(["demand_key", "unit_price", "delivery_days", "supplier"])
    best = valid.groupby("demand_key").head(1).copy()
    second = valid.groupby("demand_key").nth(1).reset_index()
    best["second_supplier"] = best["demand_key"].map(second.set_index("demand_key")["supplier"])
    best["second_price"] = best["demand_key"].map(second.set_index("demand_key")["unit_price"])
    best["savings_vs_2nd_annual"] = (best["second_price"] - best["unit_price"]) * best["qty_annual"]

    best_total = float(best["annual_value"].sum())

    ranking = main.groupby("supplier").agg(
        linhas_cotadas=("demand_key", lambda x: x.nunique()),
        linhas_com_preco=("unit_price", lambda x: int(x.notna().sum())),
        valor_anual_cotado=("annual_value", "sum"),
        prazo_medio_dias=("delivery_days", "mean")
    ).reset_index()

    winners = best.groupby("supplier").agg(
        linhas_menor_preco=("demand_key", "count"),
        valor_vencedor=("annual_value", "sum")
    ).reset_index()

    ranking = ranking.merge(winners, on="supplier", how="left").fillna({"linhas_menor_preco": 0, "valor_vencedor": 0})
    ranking["cobertura_pct_demanda"] = ranking["linhas_cotadas"] / len(demand)

    pivot_price = main.pivot_table(index="demand_key", columns="supplier", values="unit_price", aggfunc="min")
    comparativo = demand.set_index("demand_key").join(pivot_price, how="left").reset_index()
    comparativo["Fornecedor vencedor"] = comparativo["demand_key"].map(best.set_index("demand_key")["supplier"])
    comparativo["Preço vencedor"] = comparativo["demand_key"].map(best.set_index("demand_key")["unit_price"])
    comparativo["2º fornecedor"] = comparativo["demand_key"].map(best.set_index("demand_key")["second_supplier"])
    comparativo["2º preço"] = comparativo["demand_key"].map(best.set_index("demand_key")["second_price"])
    comparativo["Economia anual vs 2º"] = comparativo["demand_key"].map(best.set_index("demand_key")["savings_vs_2nd_annual"])
    comparativo["Valor anual vencedor"] = comparativo["demand_key"].map(best.set_index("demand_key")["annual_value"])
    comparativo["Qtd cotações válidas"] = comparativo[analysis_suppliers].notna().sum(axis=1)

    core = main[main["categoria_core"] != "Outros"].copy()
    core_valid = core[core["unit_price"].notna()].sort_values(["demand_key", "unit_price"])
    core_best = core_valid.groupby("demand_key").head(1).copy()

    core_rows = []
    for cat in ["Botas/Sapatos", "Proteção auditiva", "Óculos"]:
        cat_keys = set(core[core["categoria_core"] == cat]["demand_key"])
        cat_best_total = float(core_best[core_best["categoria_core"] == cat]["annual_value"].sum())
        for s in analysis_suppliers:
            sdf = core[(core["supplier"] == s) & (core["categoria_core"] == cat)]
            supplied = set(sdf[sdf["unit_price"].notna()]["demand_key"])
            cost = float(sdf[sdf["unit_price"].notna()]["annual_value"].sum())
            missing = cat_keys - supplied
            fallback = float(core_best[core_best["demand_key"].isin(missing)]["annual_value"].sum())
            core_rows.append({
                "Categoria core": cat,
                "Fornecedor": s,
                "Linhas cotadas": len(supplied),
                "Linhas da categoria": len(cat_keys),
                "Cobertura %": (len(supplied) / len(cat_keys)) if cat_keys else np.nan,
                "Custo ótimo categoria": cat_best_total,
                "Custo c/ fallback": cost + fallback,
                "Diferença vs ótimo categoria": (cost + fallback) - cat_best_total
            })

    core_df = pd.DataFrame(core_rows).sort_values(["Categoria core", "Custo c/ fallback"])

    return {
        "status_df": status_df,
        "main": main,
        "demand": demand,
        "best": best,
        "ranking": ranking.sort_values(["valor_vencedor", "linhas_menor_preco"], ascending=False),
        "comparativo": comparativo.sort_values(["categoria_core", "division", "epi"]),
        "core_df": core_df,
        "best_total": best_total,
        "roan_df": parsed.get("ROAN"),
    }


def build_excel_bytes(result):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        result["ranking"].to_excel(writer, index=False, sheet_name="ranking")
        result["comparativo"].to_excel(writer, index=False, sheet_name="comparativo")
        result["core_df"].to_excel(writer, index=False, sheet_name="unificacao_core")
        result["status_df"].to_excel(writer, index=False, sheet_name="status_arquivos")
        result["main"].to_excel(writer, index=False, sheet_name="base_consolidada")
        if result.get("roan_df") is not None:
            result["roan_df"].to_excel(writer, index=False, sheet_name="roan_parcial")
    output.seek(0)
    return output.getvalue()


st.title("Análise de BID de EPIs")
st.write("Faça upload dos arquivos de cotação em Excel para comparar fornecedores, identificar menores preços e analisar cenários de unificação dos EPIs principais.")

uploaded_files = st.file_uploader(
    "Envie os arquivos .xlsx dos fornecedores",
    type=["xlsx"],
    accept_multiple_files=True
)

if uploaded_files:
    result = analyze_uploaded_files(uploaded_files)

    if result.get("erro"):
        st.error(result["erro"])
    else:
        st.success(f"Custo anual ótimo (menor preço por item): R$ {result['best_total']:,.2f}")

        c1, c2, c3 = st.columns(3)
        c1.metric("Linhas de demanda comparadas", len(result["demand"]))
        c2.metric("Fornecedores no ranking", result["ranking"]["supplier"].nunique())
        c3.metric("Valor ótimo anual", f"R$ {result['best_total']:,.2f}")

        st.subheader("Status dos arquivos")
        st.dataframe(result["status_df"], use_container_width=True)

        st.subheader("Ranking dos fornecedores")
        st.dataframe(result["ranking"], use_container_width=True)

        st.subheader("Unificação dos EPIs core")
        st.dataframe(result["core_df"], use_container_width=True)

        st.subheader("Comparativo item a item")
        st.dataframe(result["comparativo"], use_container_width=True, height=600)

        excel_bytes = build_excel_bytes(result)
        st.download_button(
            "Baixar Excel da análise",
            data=excel_bytes,
            file_name="analise_bid_epi_streamlit.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

st.caption("Recomendação prática: usar item a item para menor custo; se quiser simplificar a operação, eleja um fornecedor âncora e complemente apenas os gaps.")
