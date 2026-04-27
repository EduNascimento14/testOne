import os
from datetime import date
from unittest.mock import patch

import pytest

os.environ['SIGOR_ENABLE_INTEGRATION'] = 'true'

from services.sigor_client import (
    SigorMTRClient,
    SigorAuthenticationError,
    SigorPDFDownloadError,
    SigorValidationError,
    build_manifesto_payload,
    gerar_seu_codigo,
)


class DummyResp:
    def __init__(self, status_code=200, headers=None, json_data=None, text='', content=b''):
        self.status_code = status_code
        self.headers = headers or {'Content-Type': 'application/json'}
        self._json = json_data
        self.text = text
        self.content = content

    def json(self):
        if self._json is None:
            raise ValueError('no json')
        return self._json


def test_gerar_seu_codigo_unique():
    c1 = gerar_seu_codigo('CAC')
    c2 = gerar_seu_codigo('CAC')
    assert c1 != c2
    assert len(c1) <= 30


def test_build_manifesto_payload_ok():
    payload = build_manifesto_payload(
        {
            'nome_responsavel': 'Resp',
            'data_expedicao': date.today(),
            'nome_motorista': 'Motorista',
            'placa_veiculo': 'ABC-1234',
            'transportador_unidade': '1',
            'transportador_cnpj': '12.345.678/0001-90',
            'destinador_unidade': '2',
            'destinador_cnpj': '12.345.678/0001-90',
            'residuos': [
                {
                    'marQuantidade': 10,
                    'resCodigoIbama': '010101',
                    'uniCodigo': '1',
                    'traCodigo': '4',
                    'tieCodigo': '4',
                    'tiaCodigo': '26',
                    'claCodigo': '42',
                }
            ],
        },
        'CAC',
    )
    assert payload['transportador']['cpfCnpj'] == '12345678000190'
    assert payload['placaVeiculo'] == 'ABC1234'


def test_build_manifesto_payload_validation_error():
    with pytest.raises(SigorValidationError):
        build_manifesto_payload({'nome_responsavel': 'x', 'data_expedicao': date.today(), 'residuos': []}, 'CAC')


@patch('services.sigor_client.requests.request')
def test_get_token_success(mock_req):
    mock_req.return_value = DummyResp(json_data={'objetoResposta': 'token123'})
    c = SigorMTRClient(base_url='http://x', cpf_cnpj='1', password='2', unidade='3', timeout=5)
    token = c.get_token()
    assert token == 'token123'


@patch('services.sigor_client.requests.request')
def test_get_token_error(mock_req):
    mock_req.return_value = DummyResp(json_data={'objetoResposta': ''})
    c = SigorMTRClient(base_url='http://x', cpf_cnpj='1', password='2', unidade='3', timeout=5)
    with pytest.raises(SigorAuthenticationError):
        c.get_token()


@patch('services.sigor_client.requests.request')
def test_download_manifesto_pdf_ok(mock_req):
    mock_req.return_value = DummyResp(status_code=200, headers={'Content-Type': 'application/pdf'}, content=b'%PDF-1.5 abc')
    c = SigorMTRClient(base_url='http://x', cpf_cnpj='1', password='2', unidade='3', timeout=5)
    c._token = 'abc'
    data = c.download_manifesto('123')
    assert data.startswith(b'%PDF')


@patch('services.sigor_client.requests.request')
def test_download_manifesto_error_payload(mock_req):
    mock_req.return_value = DummyResp(status_code=200, headers={'Content-Type': 'application/json'}, json_data={'erro': 'x'}, content=b'{}')
    c = SigorMTRClient(base_url='http://x', cpf_cnpj='1', password='2', unidade='3', timeout=5)
    c._token = 'abc'
    with pytest.raises(SigorPDFDownloadError):
        c.download_manifesto('123')


@patch('services.sigor_client.requests.request')
def test_emissao_mock_api(mock_req):
    mock_req.side_effect = [
        DummyResp(json_data={'objetoResposta': 'tok'}),
        DummyResp(json_data={'manNumero': '100'}),
    ]
    c = SigorMTRClient(base_url='http://x', cpf_cnpj='1', password='2', unidade='3', timeout=5)
    c.get_token()
    r = c.salvar_manifesto_lote([{'seuCodigo': 'ABC'}])
    assert r['manNumero'] == '100'


@patch('services.sigor_client.requests.request')
def test_cancelamento_mock_api(mock_req):
    mock_req.side_effect = [
        DummyResp(json_data={'objetoResposta': 'tok'}),
        DummyResp(json_data={'mensagem': 'cancelado'}),
    ]
    c = SigorMTRClient(base_url='http://x', cpf_cnpj='1', password='2', unidade='3', timeout=5)
    c.get_token()
    r = c.cancelar_manifesto('100', 'teste')
    assert r['mensagem'] == 'cancelado'
