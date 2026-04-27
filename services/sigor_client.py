import os
import re
import time
import uuid
from datetime import date, datetime

import requests


SIGOR_ENV = os.getenv('SIGOR_ENV', 'homologation').strip().lower()
SIGOR_BASE_URL = os.getenv(
    'SIGOR_BASE_URL',
    'https://mtrr-hom.cetesb.sp.gov.br/apiws/rest' if SIGOR_ENV == 'homologation' else 'https://mtrr.cetesb.sp.gov.br/apiws/rest',
).rstrip('/')
SIGOR_CPF_CNPJ = os.getenv('SIGOR_CPF_CNPJ', '').strip()
SIGOR_PASSWORD = os.getenv('SIGOR_PASSWORD', '').strip()
SIGOR_UNIDADE = os.getenv('SIGOR_UNIDADE', '').strip()
SIGOR_TIMEOUT_SECONDS = int(os.getenv('SIGOR_TIMEOUT_SECONDS', '30') or '30')
SIGOR_ENABLE_INTEGRATION = os.getenv('SIGOR_ENABLE_INTEGRATION', 'false').strip().lower() in ('1', 'true', 'yes', 'on')


class SigorAuthenticationError(Exception): ...
class SigorValidationError(Exception): ...
class SigorAPIError(Exception): ...
class SigorPDFDownloadError(Exception): ...


def so_digitos(s: str) -> str:
    return re.sub(r'\D', '', s or '')


def gerar_seu_codigo(site_code: str) -> str:
    base = re.sub(r'[^A-Z0-9]', '', (site_code or 'GEN').upper())[:6] or 'GEN'
    return f"MTR-{base}-{uuid.uuid4().hex[:12].upper()}"[:30]


def validar_placa(placa: str | None) -> str:
    if not placa:
        return ''
    v = re.sub(r'[^A-Za-z0-9]', '', placa).upper()
    if len(v) > 7:
        raise SigorValidationError('Placa do veículo deve ter no máximo 7 caracteres sem hífen.')
    return v


def validar_mtr_payload(payload_item: dict):
    erros = []
    if not payload_item.get('nomeResponsavel'):
        erros.append('Nome do responsável é obrigatório.')
    if not payload_item.get('seuCodigo'):
        erros.append('seuCodigo é obrigatório.')
    if payload_item.get('dataExpedicao') is None:
        erros.append('Data de expedição é obrigatória.')
    if payload_item.get('transportador', {}).get('cpfCnpj', '') == '':
        erros.append('Transportador com CNPJ/CPF obrigatório.')
    if payload_item.get('destinador', {}).get('cpfCnpj', '') == '':
        erros.append('Destinador com CNPJ/CPF obrigatório.')
    lista = payload_item.get('listaManifestoResiduos') or []
    if not lista:
        erros.append('Lista de resíduos não pode ser vazia.')
    for i, r in enumerate(lista):
        if float(r.get('marQuantidade') or 0) <= 0:
            erros.append(f'Resíduo #{i+1}: quantidade deve ser maior que zero.')
    if erros:
        raise SigorValidationError(' | '.join(erros))


def build_manifesto_payload(form_data: dict, site_code: str) -> dict:
    expedicao = form_data.get('data_expedicao') or date.today()
    if expedicao < date.today():
        raise SigorValidationError('Data de expedição não pode ser anterior à data atual.')
    transportador_unidade = form_data.get('transportador_unidade')
    destinador_unidade = form_data.get('destinador_unidade')
    item = {
        'nomeResponsavel': form_data.get('nome_responsavel'),
        'seuCodigo': form_data.get('seu_codigo') or gerar_seu_codigo(site_code),
        'dataExpedicao': int(datetime.combine(expedicao, datetime.min.time()).timestamp() * 1000),
        'nomeMotorista': form_data.get('nome_motorista'),
        'placaVeiculo': validar_placa(form_data.get('placa_veiculo')),
        'observacoes': form_data.get('observacoes'),
        'transportador': {'unidade': int(transportador_unidade) if transportador_unidade not in (None, '') else '', 'cpfCnpj': so_digitos(form_data.get('transportador_cnpj'))},
        'destinador': {'unidade': int(destinador_unidade) if destinador_unidade not in (None, '') else '', 'cpfCnpj': so_digitos(form_data.get('destinador_cnpj'))},
        'listaManifestoResiduos': form_data.get('residuos') or [],
    }
    if form_data.get('armazenador_unidade') and form_data.get('armazenador_cnpj'):
        item['armazenadorTemporario'] = {'unidade': int(form_data.get('armazenador_unidade')), 'cpfCnpj': so_digitos(form_data.get('armazenador_cnpj'))}
    validar_mtr_payload(item)
    return item


class SigorMTRClient:
    def __init__(self, base_url: str | None = None, cpf_cnpj: str | None = None, password: str | None = None, unidade: str | None = None, timeout: int | None = None):
        self.base_url = (base_url or SIGOR_BASE_URL).rstrip('/')
        self.cpf_cnpj = cpf_cnpj or SIGOR_CPF_CNPJ
        self.password = password or SIGOR_PASSWORD
        self.unidade = unidade or SIGOR_UNIDADE
        self.timeout = int(timeout or SIGOR_TIMEOUT_SECONDS)
        self._token = None

    def get_headers(self):
        headers = {'Content-Type': 'application/json'}
        if self._token:
            headers['Authorization'] = f'Bearer {self._token}'
        return headers

    def request(self, method: str, endpoint: str, payload=None, expect_pdf: bool = False, retries: int = 2):
        if not SIGOR_ENABLE_INTEGRATION:
            raise SigorValidationError('Integração SIGOR está desabilitada por configuração.')
        url = f'{self.base_url}{endpoint}'
        for attempt in range(retries + 1):
            try:
                resp = requests.request(method=method.upper(), url=url, json=payload if payload is not None else None, headers=self.get_headers(), timeout=self.timeout)
                ctype = (resp.headers.get('Content-Type') or '').lower()
                if expect_pdf:
                    if 'application/pdf' in ctype or resp.content.startswith(b'%PDF'):
                        return resp.content
                    try:
                        err_payload = resp.json()
                    except Exception:
                        err_payload = {'raw': resp.text[:500]}
                    raise SigorPDFDownloadError(f'Resposta inválida para PDF ({resp.status_code}): {err_payload}')
                if resp.status_code == 401:
                    raise SigorAuthenticationError('Falha de autenticação no SIGOR (401).')
                if resp.status_code >= 400:
                    try:
                        detail = resp.json()
                    except Exception:
                        detail = {'raw': resp.text[:500]}
                    raise SigorAPIError(f'Erro SIGOR {resp.status_code}: {detail}')
                if 'application/json' in ctype or resp.text.strip().startswith('{') or resp.text.strip().startswith('['):
                    return resp.json()
                return {'raw': resp.text}
            except (requests.Timeout, requests.ConnectionError) as exc:
                if attempt < retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise SigorAPIError(f'Falha de comunicação com SIGOR: {exc}') from exc

    def get_token(self):
        payload = {'cpfCnpj': self.cpf_cnpj, 'senha': self.password, 'unidade': self.unidade}
        data = self.request('POST', '/gettoken', payload=payload)
        token = (data or {}).get('objetoResposta') or (data or {}).get('token')
        if not token:
            raise SigorAuthenticationError('Não foi possível obter token SIGOR. Verifique credenciais e unidade.')
        self._token = token
        return token

    def _post_lista(self, endpoint: str):
        if not self._token:
            self.get_token()
        return self.request('POST', endpoint, payload={})

    def retorna_lista_classe(self): return self._post_lista('/retornaListaClasse')
    def retorna_lista_unidade(self): return self._post_lista('/retornaListaUnidade')
    def retorna_lista_tratamento(self): return self._post_lista('/retornaListaTratamento')
    def retorna_lista_estado_fisico(self): return self._post_lista('/retornaListaEstadoFisico')
    def retorna_lista_acondicionamento(self): return self._post_lista('/retornaListaAcondicionamento')
    def retorna_lista_residuo(self): return self._post_lista('/retornaListaResiduo')
    def retorna_lista_classe_por_residuo(self, res_codigo_ibama): return self._post_lista(f'/retornaListaClassePorResiduo/{res_codigo_ibama}')
    def retorna_lista_acondicionamento_por_estado_fisico(self, tie_codigo): return self._post_lista(f'/retornaListaAcondicionamentoPorEstadoFisico/{tie_codigo}')
    def salvar_manifesto_lote(self, payload): return self.request('POST', '/salvarManifestoLote', payload=payload)
    def retorna_manifesto(self, man_numero): return self.request('GET', f'/retornaManifesto/{man_numero}')
    def download_manifesto(self, man_numero): return self.request('POST', f'/downloadManifesto/{man_numero}', payload={}, expect_pdf=True)
    def cancelar_manifesto(self, man_numero, justificativa): return self.request('POST', '/cancelarManifesto', payload={'manNumero': man_numero, 'justificativa': justificativa})
    def consultar_mtr_por_seu_codigo(self, seu_codigo): return self.request('GET', f'/retornaManifestoPorSeuCodigo/{seu_codigo}')
