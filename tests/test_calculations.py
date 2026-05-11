import pandas as pd

from ehs_audit.calculations import classificar_resultado, conformidade_percentual, maturidade_media


def test_conformidade_exclui_na_e_nao_verificado():
    df = pd.DataFrame([
        {"aplicavel": True, "status": "Conforme", "nota_maturidade": 5},
        {"aplicavel": True, "status": "Parcialmente Conforme", "nota_maturidade": 3},
        {"aplicavel": True, "status": "Não Conforme", "nota_maturidade": 1},
        {"aplicavel": True, "status": "Não Verificado", "nota_maturidade": 5},
        {"aplicavel": False, "status": "Não Aplicável", "nota_maturidade": 5},
    ])
    assert conformidade_percentual(df) == 50.0
    assert maturidade_media(df) == 3.0


def test_classificacao_bloqueia_referencia_com_nc_critica():
    assert classificar_resultado(95, nc_critica_aberta=1) == "Conforme com oportunidades de melhoria"
    assert classificar_resultado(95, nc_critica_aberta=0) == "Referência / Maduro"
