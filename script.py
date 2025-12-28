#!/usr/bin/env python3

import argparse
import csv
import html
import re
import time
import requests
from supabase import create_client, Client
from postgrest.exceptions import APIError

# ============================================================================
# CONSTANTES E CONFIGURAÇÕES
# ============================================================================

# Configuração de lotes
BATCH_SIZE = 100  # Número de registros por arquivo CSV

# URLs
LIST_CANDIDATES_URL = "https://pandape.infojobs.com.br/Company/CandidateCatho"
DETAIL_CANDIDATE_FULL_URL = "https://pandape.infojobs.com.br/Company/CandidateCatho/Detail"

# Configurações de paginação
PAGE_SIZE = 100
INITIAL_PAGE = 0
MAX_PAGE = 101

# Filtros de localização
LOCATION_FILTERS = {
    'IdsLocation2[0]': 64,
    'IdsLocation3[0]': 5211323
}

# CEP's de cada unidade
CEPS_UNIDADES_MAP = {
    '01050-030': 'escritorio',  # Escritorio
    '02989-110': 'parada_taipas',  # ParadaTaipas
    '02801-000': 'elisio',  # Elisio
    '02932-080': 'edgar_faco',  # EdgarFaco
    '02815-040': 'ct_taipas',  # CT
    '02917-100': 'paula_ferreira'   # PaulaFerreira
}

# Proxy (mesmo dos chips de RH)
PROXIES = {
    'http': 'http://nzjxauzp-BR-rotate:hrgb77jhvfya@p.webshare.io:80'
}

# Headers HTTP
HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,/;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cache-Control': 'max-age=0',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
    'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
}

# Headers para requisição de detalhes completos
DETAIL_FULL_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,/;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Connection': 'keep-alive',
    'Referer': 'https://pandape.infojobs.com.br/Company/CandidateCatho?ExperienceCtInProgress=None^&SalaryMin=20000^&HasEvaluationComments=None^&CandidateAssignmentType=None^&ReadCvStatus=None^&StudyingStatus=None^&PhotoFilterCt=None^&Order=1^&IsLast=False^&NegotiableSalary=False^&KeywordMatchType=AllWords^&KeywordSearchScopeType=AllFields^&Pagination[0]=1^&Pagination[1]=10',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0',
    'Priority': 'u=0, i',
}

# Cookies de autenticação (atualizados do curl)
COOKIES = {
    'ATSCultureCookie': 'c%3Dpt-BR%7Cuic%3Dpt-BR',
    '_pprv': 'eyJjb25zZW50Ijp7IjAiOnsibW9kZSI6ImVzc2VudGlhbCJ9LCIxIjp7Im1vZGUiOiJvcHQtaW4ifSwiMiI6eyJtb2RlIjoib3B0LWluIn0sIjMiOnsibW9kZSI6Im9wdC1pbiJ9LCI0Ijp7Im1vZGUiOiJvcHQtaW4ifSwiNSI6eyJtb2RlIjoib3B0LWluIn0sIjYiOnsibW9kZSI6Im9wdC1pbiJ9LCI3Ijp7Im1vZGUiOiJvcHQtaW4ifX0sInB1cnBvc2VzIjpudWxsLCJfdCI6Im16MzE1YTkwfG1qZW03c3gwIn0%3D',
    '_pcid': '%7B%22browserId%22%3A%22mjem7sx0gwlona2l%22%2C%22_t%22%3A%22mz315a96%7Cmjem7sx6%22%7D',
    '_pctx': '%7Bu%7DN4IgrgzgpgThIC4B2YA2qA05owMoBcBDfSREQpAeyRCwgEt8oBJAE0RXSwH18yBbAF4BmAIwBWQgE4AbAB9%2BAKyj8A7BAAeMkAF8gA',
    '_fbp': 'fb.2.1766254317175.98851263216901824',
    '_gcl_au': '1.1.45085364.1766254317.886775703.1766427521.1766427521',
    '_ga_BLEQGRBWCW': 'GS2.1.s1766601580$o8$g1$t1766601586$j54$l0$h0',
    '_ga': 'GA1.1.1424810733.1766254317',
    'didomi_token': 'eyJ1c2VyX2lkIjoiMTliM2NmNjEtMGU5ZC02MTU1LWEzY2MtNThiNzUxOWVjZGNiIiwiY3JlYXRlZCI6IjIwMjUtMTItMjBUMTg6MTE6NTcuODAxWiIsInVwZGF0ZWQiOiIyMDI1LTEyLTIwVDE4OjEyOjAwLjQyMloiLCJ2ZW5kb3JzIjp7ImVuYWJsZWQiOlsiZ29vZ2xlIiwiYzptaWNyb3NvZnQtUHpoYWhENjciLCJjOmdvb2dsZWFuYS00VFhuSmlnUiIsImM6cGlhbm9oeWJyLVIzVktDMnI0Il19LCJwdXJwb3NlcyI6eyJlbmFibGVkIjpbImF1ZGllbmNlbS1oSnhhZUdyUiJdfSwidmVuZG9yc19saSI6eyJlbmFibGVkIjpbImdvb2dsZSJdfSwidmVyc2lvbiI6Mn0=',
    'euconsent-v2': 'CQcuwYAQcuwYAAHABBENCJFgALFAAELAAAKIF5wAQF5gXnABAXmAAAAA.digACFgAAAAA',
    'usunico': '20/12/2025:15-016127334',
    '.AspNetCore.Antiforgery.MzFEACH9dlA': 'CfDJ8K1c-0FgE-xEjdbme_UswhluPiZAGhfZ-WOFpzUVvDvYYA7DF0w5NK8mlp-nfXEzPVg8unYUOAIWt43woV_FkIhB7H9cT8WrZElj13eVmG_M_seqwGx51OzFIFJP7fLMCrQ2hK_euH-cMNDQkNomJTk',
    'ats-webui': 'CfDJ8K1c-0FgE-xEjdbme_Uswhmg65A1Gp4rFii7ttnFecVBnkcEuZyEFpePbV-lFFrDaCF8vBhCSUIk9vxJo7BQdlvFSHysNqZHKlRIZIW46g7DlYs3G9KGuMG9f26sgAfR85DSQjuTAtHFxl71b2IVZgg5yQNT9VjwB36f92u1trOv6ejSjKkp50Q06X7lTVWsIlPPuPPAgpGLml-tRUuiy_4XIVK116HP4iLjOS4pDwPNgfVCEI3HPJhxMwGsHnlBPjHTJj450JRlcMTmsM5s6joJBJHGCd4Fvo3BYu8X07GBLn_EnVnrlc_RM3c5D5Z9wQRserUDYmsWPZDYrZBYIBV7lsihtn2-WIFD4Eh6DzeQp7KDaAYLfVhMZH7DcF9Yygy3XwqQmSemO1ukA3h0qcAE22HuX3ePsBvk-07k27ECfPFDTTGMnD8F3DybJer0s1opgMCSVFlUZxKYEgLSmpE4SwFf0YawJVkBYf-JmbTPaker6-KW1BdJAgDCwDUWmu1Fk5bRgwwL9MTGmKFXVKeBV6EjgGOVEEZ9TxAzx90MpYaEliHVhrNOpyROMD23vwPmM7uWnY6mOhFrQn_OgAslwOrJ8NsuvgJqYEveGNeEy485-PJ5ONvMIm2gCW29BjrjRb9FBfhjBaihi_XQYLiAS_RC9thjHPsYszB00WvA8zI2EO7wnf8BZ5uv0VDodMGU45ddIcIwvDxdDhj42b8mz0V68-yl98GcGnhUq_k5Pu0P9dLxI75fIsP4VExMlgL8vrqYJKhTC3OmJ71AWs2GiGCooQx7Bj_fwOuWHRe46PnR8EbgGf_2QlMOHw6vWDHOAy7xiCBPnm4OhavSvETx3qHAFNiDH9Zr6dxVTWBeOwhXxGeaPno-WNEel17NYfp0geKVqZmtJ446ip4k8qnKz6HYjogz6vbPmhBvxzdTRcAFZ-5QaxOxagr1iU1mV6pqB6WJdVMZ-FzEP3jne00-Ys0pg4NciRf4vcT542ATt0wJIzzlTiXk9M_yha8eXGjZ2FVq8H_p9sulBaI7E0eg06jNzkQf0pgvWdEbZZTOOq7Q5dug17fF5oWCRJWmmR9li9I_T1ioVv56wDT0hgr3DiiPIZX0IyUGQxiBD8JfCofgz-WXPpNmUAevkSvAybQO7kIqdZiZOkY3uZPlAyTjMYIX0B-frl70QZkvF0LLPQORZRJN1W6yiSzCIKo0guGK30Bgd3evb3levB4bGCoHtg7ooS0nllTZgm0CJypqdfyfJOBxjRQfGgDR_SN9dzq0NStlc0zP1Rbzw4WjFBlLCLq-tZzJztAy0IKqGoObNDtPuIVLKC-mijsKx_8ZYh_KsyR_AgLti3B0m0tXIpt75fF3Nmj4fRlclFAkM86UxyZykUkqQOYRRec7v5-WZwGWqPQjOgHi0S8td5gAtAxbYuMXO1yBWNM66eLW6dIgPSc7yKtBLYPFkRPUVwclDf1galcsIQpqkNGErGAAfKQoS7CbDtP141iSdyuDEteKjb3IM4jvRYIbCdBfK_03W-TGUvtuQsSInsCycSY7US-Rdw53FcOtSD5nJSVkDexhuTLyVWb5hqomqLJXpvvjP3ImnFv3fcZT7Q5MnCdGdMIgiN397EdiiWedpO-VczRtRsRbSJmFSGxRoYEgN4ycYVz50uZf_KFZ0fMFIZJRiWnTV4HbsnKJeDTQegfWl1Zv0sle-CoPVwM0tkxBHDYb4-h2757H-ppRXIZx-nHKBwsKJslz1r-zNYbbKKAgxO9lot2TlSIOIh5wLFVpSDYHW8VsPGh4wev-bXKiATEJRhwYGcRgoysdRfYCBjAD4ZLZRBbABSQliZ9vOvwhsUSCzZVkZvSmgSY995RoDZ-pXxV8SIdZ9zkpxgWRmhoZDQTGALrpF5Tubc1B0ak4WPnc0D8hO5J-qmV4DPc1S_WJcDDkY8dKC9T5kBmpxnmxVvFYMDcOYV99xsJNWyatAj9a1n76DaHrZj0Y8TKEWy84tWEzlhC45DayWMTBAJ7xPJ4JW8AY0HWj6v07Fc6y0mbMWpup8cXfyZZowbBrroUNSaE5xVvl-U6vRByDXunmws7fVDQEoFuztvRUKitXDE7pkGqBHyAy9Amnxs6HYlnwP6CeG2blah9CF4hOlQlv3tRUIWYgUc6ygUgA80pD9MtYsx40mrTUUAYuz466TC6UpyoPt_dyOY3_IjOPx1TMMLYsi-Fy7NFe4xzELDTmKAPdMz24iUc-NLubgXrF3a99Dc2KdGs-hdYTJPEpK7SVc0d0AwejgXDBX0YfdLrntYpz5B9OL6xA7o4DLBPJgXaeAD4y4dfYK6CqdAAYCni1VTSzv1fvgOC0G8_pAM9aAeayFGYzUX5kI10YwVVN2Nat3NN76Ab_XA4mMgyvgXf9D7EFDJutKVxyc4WGOG-QQ73pXdvf2ws_jgklbLmfWDHSK7ZyBi72tMgsHD6Lc6j_EpmjBm_JvvuCxYlcwI5SoV9D915sWb996mgF96MeVfrVZEQak1x7_iXJK6bsAM1Othf-iyE69KVFK8DKob73YcHLDPvz1HSt0StlpJulpicx0gU_r5q8Gmd8U13J1FrPelKAll2fsVpUd8qFqrhgnKghi9GrYtALI-dkE8xJLoPSdK4Vy5ZN2VFIqlSyyXLbD1JEbtKcSNvhl5iw09SrU-G6Ix-uTEvlIEoEcNZgIwfxRg6ANQs6nLYUgfiXgrbcpOj2tfzHQwQ375oUnwBME4d68wY16QqCqz0VKggA043ypiOyPCz2paSZowLw-z3sTv4Si_ASTnNkh2ze5xjMiIJHXwQ5m3Uj1p5rvkuvy6kS5RvF7eZbL2NynrgWyXqupj1CL4mRhrjRyC4vD8e3I12UxJoei-YfjbXw3hgEzghwD5APwybZiZgbYVS_GSGlGiJYzk_6MDglHz4Mqz18CQV5TpQT4IT_WyAVat8_s1X-Lb_vr6npbXO46IrfgFDMP1Y3SZ4AFrB81dkcY5QkQndUeI13GpWUE64pSrszfCqePNg7KiVum8oSL-hAglYVS2yM-9atoiwW4_zMRp0NZt1GFftl5x9gZXJrs3AqjBYVBvjWTj-aa93G5cvfiBFOEdtL1wIKaWNAZ-yhPhzehFVDoDFDuzoYokP1wbOQ6BAt5eMK4P9IcT7UkB3csobqA80hK7ubeK6WqR-U1Ma0xW1F3F2kbwBw7w2SJWIV5rPWA27dELBlVRxSeMqgkTNv1oDbU1NhL1xc_TexNPbKea-NGObUElnFWND3-U4U325ouz8FHqypeURXxUoXKBVgjsWHn6QGCamPYD8qKHz6ok70MXa5raly7J5CV6OcX9AhM53IfJ61eCF1dKVVEUdwS5gP9Csja7ry0pS7jJ8k5trXPUvjfjGlfqzBWJdNekvYDBjTu4WhIZkUFCyzgGf7mFWPFlfM68T1YBLos2dC7l8X4W6sey4DByw0mGyzhDWakD0Rh5Chf9tlCiETKQah5eqhFq4gqpKR4u9yCnfAJApsYEaOY228FsJpC0W-v_hJXSfYzKtPQgFu14-Yq7jgyi6V501mmznGCaC9Cv5K9XAoJY9-L12onqfd-A5DP8XAaVtbsja1IxJMsEmyKOBcPHAcI0z4q1aAPFHn3l8_IDZQ0w',
    '.AspNetCore.Mvc.CookieTempDataProvider': 'CfDJ8K1c-0FgE-xEjdbme_Uswhl8MmfUuak5bqWmz6Bwuzx0Z1hFVp-8lgmt8OrXNZXZvHC7DX1PxvYQqQ5eJJ7Ay3k-lAfeN7-0p5d6fnCg7mQxnUAavG8uPgFLrbShruAMcTiHLwAj5_WSkxJVcUdP68Y',
}

# Padrões de regex para extração de dados
REGEX_PATTERNS = {
    'candidate_id': r'(?:id="candidate-|data-id=")(\d+)',
    'name': r'<div id="divCandidateName"[^>]*>.*?<div class="font-4xl fw-600 lh-120 text-capitalize-first">([^<]+)</div>',
    'job': r'<div[^>]*class="[^"]*mb-05[^"]*font-2lg[^"]*"[^>]*>([^<]+)</div>',
    'phone': r'<input[^>]*type="hidden"[^>]*id="hdnPhone"[^>]*name="Phone"[^>]*value="([^"]+)"',
    'email': r'<i class="icon icon-paperplane"></i>.*?<span>([^<]+)</span>',
    'salary': r'Pretensão salarial\s*:.*?<span class="[^"]*c-drk[^"]*">([^<]+)</span>',
    'address': r'<i class="icon icon-location-pin-2-o"></i>.*?<span>([^<]+)</span>',
    'age_marital': r'<div class="c-md">\s*([^<]+)\s+de\s+(\d+)\s+Anos\s+\(Nasceu[^)]+\)',
    'working_hours': r'<div id="WorkingHours"[^>]*>.*?<div class="col-9">\s*<div>([^<]+)</div>',
    'contract_type': r'<div id="ContractWorkType"[^>]*>.*?<div class="col-9">\s*<div>([^<]+)</div>',
    'gender_marital': r'<div class="match-personal-data[^"]*">.*?<div class="c-md">\s*([^<]+?)(?:\s+de\s+\d+\s+Anos)?\s*</div>',
    'birth_date': r'<div class="match-personal-data[^"]*">.*?\(Nasceu\s+([^)]+)\)'
}

# Valores padrão
DEFAULT_MESSAGE = "Não informado"

# ============================================================================
# FUNÇÕES DE UTILIDADE
# ============================================================================

def supabase_connection():
    url: str = "https://dtktqviwceofwtuxlojs.supabase.co"
    key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR0a3Rxdml3Y2VvZnd0dXhsb2pzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MDYyMDg1MSwiZXhwIjoyMDc2MTk2ODUxfQ.HxXErjJLJn5p_fMZ9-8wQWy1GpbDz9NgHWnNo5_KQcI"
    supabase: Client = create_client(url, key)
    return supabase

def decode_text(text):
    """Decodifica entidades HTML e escapes de JSON"""
    if not text:
        return ""
    text = text.replace('\\r\\n', ' ').replace('\\n', ' ')
    return html.unescape(text.strip())


def extract_salary(html_content):
    """Extrai o salário do HTML e retorna como inteiro (ou None se não informado)"""
    salary_match = re.search(REGEX_PATTERNS['salary'], html_content, re.DOTALL)
    
    if not salary_match:
        return None  # NULL para banco de dados
    
    salary_text = decode_text(salary_match.group(1).strip())
    
    # Parsear diferentes formatos de salário
    # "A partir de R$ 20.001" -> 20001
    # "Entre R$ X e R$ Y" -> X (primeiro valor)
    # "R$ X" -> X
    
    if "A partir de" in salary_text or "A partir" in salary_text:
        # Extrair valor numérico (pode ter vírgula ou ponto como separador de milhar)
        value_match = re.search(r'R\$\s*([\d.,]+)', salary_text)
        if value_match:
            try:
                return int(value_match.group(1).replace('.', '').replace(',', ''))
            except ValueError:
                return None
    elif "Entre" in salary_text:
        # Formato "Entre R$ X e R$ Y" - retorna o primeiro valor
        values = re.findall(r'R\$\s*([\d.,]+)', salary_text)
        if len(values) >= 1:
            try:
                return int(values[0].replace('.', '').replace(',', ''))
            except ValueError:
                return None
    else:
        # Formato simples "R$ X"
        value_match = re.search(r'R\$\s*([\d.,]+)', salary_text)
        if value_match:
            try:
                return int(value_match.group(1).replace('.', '').replace(',', ''))
            except ValueError:
                return None
    
    return None  # NULL para banco de dados


# ============================================================================
# FUNÇÕES DE REQUISIÇÃO HTTP
# ============================================================================

def build_pagination_request_data(page_number):
    """Constrói os dados da requisição para paginação"""
    return {
        'Pagination[PageNumber]': page_number,
        'Pagination[PageSize]': PAGE_SIZE,
        'CEP': CEP,
        'MaxDistance': MAX_DISTANCE,
        **LOCATION_FILTERS
    }


def fetch_candidate_ids_from_page(page_number):
    """Busca e retorna os IDs dos candidatos de uma página"""
    request_data = build_pagination_request_data(page_number)
    
    response = requests.get(
        LIST_CANDIDATES_URL,
        headers=HEADERS,
        params=request_data,
        cookies=COOKIES,
        proxies=PROXIES
    )
    response.encoding = response.apparent_encoding or 'utf-8'
    candidate_ids = sorted(set(re.findall(REGEX_PATTERNS['candidate_id'], response.text)))
    return candidate_ids


def fetch_candidate_full_details(candidate_id):
    """Busca os detalhes completos de um candidato (HTML completo)"""
    detail_url = f"{DETAIL_CANDIDATE_FULL_URL}/{candidate_id}"
    
    response = requests.get(
        detail_url,
        headers=DETAIL_FULL_HEADERS,
        cookies=COOKIES,
        proxies=PROXIES
    )
    response.encoding = response.apparent_encoding or 'utf-8'
    return response.text


# ============================================================================
# FUNÇÕES DE EXTRAÇÃO DE DADOS
# ============================================================================

def extract_name_from_html(full_html):
    """Extrai o nome do candidato do HTML completo"""
    name_match = re.search(REGEX_PATTERNS['name'], full_html, re.DOTALL)
    if name_match:
        return decode_text(name_match.group(1))
    return ""
    

def extract_job_from_html(full_html):
    """Extrai o cargo do candidato do HTML completo"""
    job_match = re.search(REGEX_PATTERNS['job'], full_html)
    return decode_text(job_match.group(1)) if job_match else ""


def extract_phone_from_html(full_html):
    """Extrai o telefone do candidato do HTML completo"""
    phone_match = re.search(REGEX_PATTERNS['phone'], full_html)
    return decode_text(phone_match.group(1)) if phone_match else ""


def extract_email_from_html(full_html):
    """Extrai o email do candidato do HTML completo"""
    email_match = re.search(REGEX_PATTERNS['email'], full_html, re.DOTALL)
    return decode_text(email_match.group(1)) if email_match else ""


def extract_address_from_json(full_html):
    """Extrai o endereço do candidato do HTML completo"""
    address_match = re.search(REGEX_PATTERNS['address'], full_html, re.DOTALL)
    return decode_text(address_match.group(1)) if address_match else DEFAULT_MESSAGE


def extract_working_hours(full_html):
    """Extrai a jornada de trabalho do HTML completo"""
    working_hours_match = re.search(REGEX_PATTERNS['working_hours'], full_html, re.DOTALL)
    return decode_text(working_hours_match.group(1)) if working_hours_match else DEFAULT_MESSAGE


def extract_contract_type(full_html):
    """Extrai o tipo de contrato do HTML completo"""
    contract_type_match = re.search(REGEX_PATTERNS['contract_type'], full_html, re.DOTALL)
    return decode_text(contract_type_match.group(1)) if contract_type_match else DEFAULT_MESSAGE


def extract_gender(full_html):
    """Extrai o sexo do candidato do HTML completo"""
    gender_match = re.search(REGEX_PATTERNS['gender_marital'], full_html, re.DOTALL)
    if gender_match:
        text = decode_text(gender_match.group(1))
        # Extract gender from "Homem casado" or "Mulher solteira" etc
        if 'homem' in text.lower() or 'masculino' in text.lower():
            return 'Masculino'
        elif 'mulher' in text.lower() or 'feminino' in text.lower():
            return 'Feminino'
    return DEFAULT_MESSAGE


def extract_marital_status(full_html):
    """Extrai o estado civil do candidato do HTML completo"""
    marital_match = re.search(REGEX_PATTERNS['gender_marital'], full_html, re.DOTALL)
    if marital_match:
        text = decode_text(marital_match.group(1))
        # Extract marital status from "Homem casado" or "Mulher solteira" etc
        marital_keywords = {
            'casado': 'Casado',
            'casada': 'Casada',
            'solteiro': 'Solteiro',
            'solteira': 'Solteira',
            'divorciado': 'Divorciado',
            'divorciada': 'Divorciada',
            'viúvo': 'Viúvo',
            'viúva': 'Viúva',
            'viuvo': 'Viúvo',
            'viuva': 'Viúva'
        }
        text_lower = text.lower()
        for keyword, status in marital_keywords.items():
            if keyword in text_lower:
                return status
    return DEFAULT_MESSAGE

def extract_birth_date(full_html):
    """Extrai a data de nascimento do candidato do HTML completo e formata como yyyy-mm-dd (formato ISO para banco de dados)"""
    birth_date_match = re.search(REGEX_PATTERNS['birth_date'], full_html, re.DOTALL)
    
    if not birth_date_match:
        return None  # NULL para banco de dados
    
    date_text = decode_text(birth_date_match.group(1))
    
    # Mapeamento de meses em português para números
    months_pt = {
        'janeiro': 1, 'fevereiro': 2, 'março': 3, 'marco': 3,
        'abril': 4, 'maio': 5, 'junho': 6,
        'julho': 7, 'agosto': 8, 'setembro': 9,
        'outubro': 10, 'novembro': 11, 'dezembro': 12
    }
    
    try:
        # Parsear a data no formato "1 maio de 1998"
        # Regex para extrair dia, mês e ano
        date_pattern = r'(\d+)\s+(\w+)\s+de\s+(\d{4})'
        match = re.search(date_pattern, date_text.lower())
        
        if match:
            day = int(match.group(1))
            month_name = match.group(2).lower()
            year = int(match.group(3))
            
            if month_name in months_pt:
                month = months_pt[month_name]
                # Formatar como yyyy-mm-dd (formato ISO para banco de dados)
                formatted_date = f"{year}-{month:02d}-{day:02d}"
                return formatted_date
    except (ValueError, AttributeError):
        pass
    
    return None  # NULL para banco de dados


def extract_candidate_data(candidate_id, full_html):
    """Extrai todos os dados de um candidato do HTML completo"""
    return {
        'id': candidate_id,
        'name': extract_name_from_html(full_html),
        'job': extract_job_from_html(full_html),
        'phone': extract_phone_from_html(full_html),
        'email': extract_email_from_html(full_html),
        'salary': extract_salary(full_html) if extract_salary(full_html) else 0,
        'address': extract_address_from_json(full_html),
        'working_hours': extract_working_hours(full_html),
        'contract_type': extract_contract_type(full_html),
        'gender': extract_gender(full_html),
        'marital_status': extract_marital_status(full_html),
        'birth_date': extract_birth_date(full_html) if extract_birth_date(full_html) else None
    }


# ============================================================================
# FUNÇÕES DE PROCESSAMENTO
# ============================================================================

def insert_supabase(candidato_data, nome_unidade, supabase_cc):
    candidato_id = candidato_data.get('id')

    try:
        # 1. Tenta o INSERT direto
        print(f"Tentando inserir ID {candidato_id}...")
        return supabase_cc.table("base_catho").insert(candidato_data).execute()

    except APIError as e:
        # 2. Se o erro for de chave duplicada (geralmente código 23505 no Postgres)
        # O supabase-py lança APIError quando o banco retorna erro.
        print(f"Conflito para o ID {candidato_id}. Executando update")
        
        supabase_cc \
            .table("base_catho") \
            .update({nome_unidade: MAX_DISTANCE}) \
            .eq("id", candidato_id) \
            .or_(f"{nome_unidade}.gt.{MAX_DISTANCE},{nome_unidade}.is.null") \
            .execute()

def format_value_for_csv(value):
    """Formata valores para CSV: None vira string vazia, números mantêm formato"""
    if value is None:
        return ''  # String vazia para NULL no CSV (será convertido para NULL no banco)
    return str(value)  # Converte tudo para string para o CSV

def process_single_candidate(candidate_id, batch_number, record_count, supabase_cc):
    """Processa um único candidato: busca dados e salva no CSV"""
    try:
        full_html = fetch_candidate_full_details(candidate_id)
        candidate_data = extract_candidate_data(candidate_id, full_html)

        # Formatar valores para CSV (None vira string vazia, números como string)
        candidate_row = {
            'id': format_value_for_csv(int(candidate_data['id']) if candidate_data['id'] else None),  # ID como número
            'name': format_value_for_csv(candidate_data['name']),
            'job': format_value_for_csv(candidate_data['job']),
            'phone': format_value_for_csv(candidate_data['phone']),
            'email': format_value_for_csv(candidate_data['email']),
            'salary': format_value_for_csv(candidate_data['salary']),  # Salário como número (None vira string vazia)
            'address': format_value_for_csv(candidate_data['address']),
            'gender': format_value_for_csv(candidate_data['gender']),
            'gender_marital': format_value_for_csv(candidate_data['marital_status']),
            'birth_date': candidate_data['birth_date'],  # Data no formato yyyy-mm-dd
            CEPS_UNIDADES_MAP.get(CEP): MAX_DISTANCE
        }
        
        insert_supabase(candidate_row, CEPS_UNIDADES_MAP.get(CEP), supabase_cc)
        #save_candidate_to_csv(candidate_row, batch_number)
        #print(f"      ✓ Dados salvos: {candidate_data.get('name', 'N/A')}")
        return record_count + 1
    
    except Exception as e:
        print(f"      ❌ Erro ao processar candidato {candidate_id}: {e}")
        return record_count


def process_page(page_number, batch_number, record_count, supabase_cc):
    """Processa uma página de candidatos"""
    print(f"\n{'='*50}")
    print(f"Processando página {page_number}...")
    print(f"{'='*50}")
    
    candidate_ids = fetch_candidate_ids_from_page(page_number)
    
    if not candidate_ids:
        print(f"⚠️  Nenhum ID encontrado na página {page_number}. Encerrando...")
        return False, batch_number, record_count
    
    print(f"✓ Encontrados {len(candidate_ids)} candidatos na página {page_number}")
    print(f"📄 Lote atual: {batch_number} | Registros no lote: {record_count}/{BATCH_SIZE}")
    
    current_batch = batch_number
    current_count = record_count
    
    for idx, candidate_id in enumerate(candidate_ids, 1):
        # Se atingiu o tamanho do lote, criar novo arquivo
        if current_count >= BATCH_SIZE:
            current_batch += 1
            current_count = 0
            print(f"📄 Lote atual: {current_batch} | Registros no lote: {current_count}/{BATCH_SIZE}")
        
        current_count = process_single_candidate(candidate_id, current_batch, current_count, supabase_cc)
    
    print(f"\n✓ Página {page_number} concluída: {len(candidate_ids)} candidatos processados")
    print(f"📊 Total no lote atual: {current_count}/{BATCH_SIZE}")
    
    return True, current_batch, current_count


def process_all_pages(initial_page=None, max_page=None):
    """Processa todas as páginas de candidatos"""
    # Usar valores padrão globais se não fornecidos
    if initial_page is None:
        initial_page = INITIAL_PAGE
    if max_page is None:
        max_page = MAX_PAGE
    
    print("\n" + "="*50)
    print("🚀 INICIANDO PROCESSAMENTO DE CANDIDATOS")
    print("="*50)
    print(f"📋 Configurações:")
    print(f"   - Páginas a processar: {initial_page + 1} até {max_page}")
    print(f"   - Tamanho do lote: {BATCH_SIZE} registros por arquivo")
    print("="*50)
    
    # Inicializar primeiro arquivo
    batch_number = 1
    record_count = 0
    supabase_cc = supabase_connection()
    
    page_number = initial_page
    total_pages_processed = 0
    
    while page_number < max_page:
        page_number += 1
        
        try:
            should_continue, batch_number, record_count = process_page(page_number, batch_number, record_count, supabase_cc)
            if not should_continue:
                break
            
            total_pages_processed += 1
            
        except Exception as e:
            print(f"\n❌ Erro na página {page_number}: {e}")
            import traceback
            traceback.print_exc()
            break
    
    print("\n" + "="*50)
    print(f"✅ PROCESSAMENTO CONCLUÍDO")
    print(f"   - Páginas processadas: {total_pages_processed}")
    print(f"   - Total de lotes criados: {batch_number}")
    print(f"   - Registros no último lote: {record_count}/{BATCH_SIZE}")
    print("="*50)
    
    return batch_number


# ============================================================================
# FUNÇÃO PRINCIPAL
# ============================================================================

def parse_arguments():
    """Insira MaxDistance e CEP (obrigatórios)"""
    parser = argparse.ArgumentParser(description="Scrape candidate data and save to CSV files")
    parser.add_argument('--max-distance', type=int, required=True, help='Filtro MaxDistance (obrigatório)')
    parser.add_argument('--cep', type=str, required=True, help='CEP (obrigatório)')
    parser.add_argument('--initial-page', type=int, default=INITIAL_PAGE, help=f'Página inicial para processar (padrão: {INITIAL_PAGE})')
    parser.add_argument('--max-page', type=int, default=MAX_PAGE, help=f'Página máxima para processar (padrão: {MAX_PAGE})')
    
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_arguments()

    # Override global defaults with CLI values
    MAX_DISTANCE = args.max_distance
    CEP = args.cep

    start_time = time.time()
    total_batches = process_all_pages(initial_page=args.initial_page, max_page=args.max_page)
    end_time = time.time()
    execution_time = end_time - start_time