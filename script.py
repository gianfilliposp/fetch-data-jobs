#!/usr/bin/env python3

import argparse
import csv
import html
import json
import re
import time
import requests
from supabase import create_client, Client
from postgrest.exceptions import APIError

# For Windows consoles that default to CP1252, force UTF-8 for stdout/stderr so
# emojis and other non-CP1252 characters don't raise UnicodeEncodeError.
# This tries the modern reconfigure() and falls back to wrapping stdout/stderr.
import sys
import io
import os
try:
    # Prefer setting UTF-8 mode if available
    os.environ.setdefault("PYTHONUTF8", "1")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    # Fallback for environments where reconfigure() isn't available
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

# ============================================================================
# CONSTANTES E CONFIGURAÇÕES
# ============================================================================

# Nome da tabela no Supabase
SUPABASE_TABLE_NAME = "base_catho_full"

# Configuração de lotes
BATCH_SIZE = 100  # Número de registros por arquivo CSV

# URLs
LIST_CANDIDATES_URL = "https://pandape.infojobs.com.br/company/CandidateCatho"
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

# CEP's de cada unidade - mapeamento para unidade_id (UUID)
# TODO: Atualizar com os UUIDs reais das unidades
CEPS_UNIDADES_MAP = {
    '01050-030': None,  # Escritorio - substituir por UUID
    '02989-110': None,  # ParadaTaipas - substituir por UUID
    '02801-000': None,  # Elisio - substituir por UUID
    '02932-080': None,  # EdgarFaco - substituir por UUID
    '02815-040': None,  # CT - substituir por UUID
    '02917-100': None   # PaulaFerreira - substituir por UUID
}

def cep_to_bigint(cep_str):
    """Converte CEP string (formato: 01050-030) para bigint (01050030)"""
    if not cep_str:
        return None
    # Remove dashes and convert to int
    cep_clean = cep_str.replace('-', '').strip()
    try:
        return int(cep_clean)
    except ValueError:
        return None

# Proxy (mesmo dos chips de RH)
PROXIES = {
    'http': 'http://nzjxauzp-BR-rotate:hrgb77jhvfya@p.webshare.io:80'
}

# Headers HTTP para requisição de lista de candidatos
HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Connection': 'keep-alive',
    'Referer': 'https://pandape.infojobs.com.br/Company/CandidateCatho/Detail/51400036',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
    'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
}

# Headers para requisição de detalhes completos
DETAIL_FULL_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cache-Control': 'max-age=0',
    'Connection': 'keep-alive',
    'Referer': 'https://pandape.infojobs.com.br/Company/CandidateCatho/Detail/84331741',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
    'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
}

# Cookies de autenticação para requisição de lista (atualizados do novo curl)
# Baseado em DETAIL_COOKIES mas com valores do --cookie parameter que sobrescrevem
COOKIES = {
    '_pprv': 'eyJjb25zZW50Ijp7IjAiOnsibW9kZSI6ImVzc2VudGlhbCJ9LCIxIjp7Im1vZGUiOiJvcHQtaW4ifSwiMiI6eyJtb2RlIjoib3B0LWluIn0sIjMiOnsibW9kZSI6Im9wdC1pbiJ9LCI0Ijp7Im1vZGUiOiJvcHQtaW4ifSwiNSI6eyJtb2RlIjoib3B0LWluIn0sIjYiOnsibW9kZSI6Im9wdC1pbiJ9LCI3Ijp7Im1vZGUiOiJvcHQtaW4ifX0sInB1cnBvc2VzIjpudWxsLCJfdCI6Im1xcXZlM3ZxfG1iMmdnbWpxIn0%3D',
    '_pcid': '%7B%22browserId%22%3A%22mb2ggmjq1covlen4%22%2C%22_t%22%3A%22mqqve3vr%7Cmb2ggmjr%22%7D',
    '_pctx': '%7Bu%7DN4IgrgzgpgThIC4B2YA2qA05owMoBcBDfSREQpAeyRCwgEt8oBJAE0RXSwH18yBbAI6CAblADMIiAB9%2BAIwBMAcyX8AVvAC%2BQA',
    '_fbp': 'fb.2.1755524211764.90899100101412948',
    'didomi_token': 'eyJ1c2VyX2lkIjoiMTk4OWVhYzAtYTdhNy02ZDk0LTk3ODctNjVmNmI0YmMxODgzIiwiY3JlYXRlZCI6IjIwMjUtMDgtMTJUMTQ6MjU6MzEuNzcwWiIsInVwZGF0ZWQiOiIyMDI1LTA5LTI2VDEzOjI5OjQzLjA0NloiLCJ2ZW5kb3JzIjp7ImVuYWJsZWQiOlsiZ29vZ2xlIiwiYzpnb29nbGVhbmEtNFRYbkppZ1IiLCJjOnlhaG9vLWdlbWluaS1hbmQtZmx1cnJ5IiwiYzpwaWFub2h5YnItUjNWS0MycjQiLCJjOm1pY3Jvc29mdC1QemhhaEQ2NyJdfSwicHVycG9zZXMiOnsiZW5hYmxlZCI6WyJnZW9sb2NhdGlvbl9kYXRhIiwiZGV2aWNlX2NoYXJhY3RlcmlzdGljcyIsImF1ZGllbmNlbS1oSnhhZUdyUiJdfSwidmVuZG9yc19saSI6eyJlbmFibGVkIjpbImdvb2dsZSJdfSwidmVyc2lvbiI6MiwiYWMiOiJBRm1BQ0FGay5BRm1BQ0FGayJ9',
    'euconsent-v2': 'CQWCSgAQYWmsAAHABBENB9FsAP_AAEPgAAKIJ4QAwAaALzAngCeEAMAGgC8wJ4AAAAAA.f_gACHwAAAAA',
    '_ga': 'GA1.1.342535473.1755008733',
    '_ga_WTJXFBM2G9': 'GS2.1.s1760199278$o2$g0$t1760200038$j60$l0$h0',
    '_gcl_au': '1.1.161354091.1763134889.1684888494.1766968488.1766968488',
    'ATSCultureCookie': 'c%253Dpt-BR%257Cuic%253Dpt-BR',  # Double encoded from --cookie parameter
    'ats-webui': 'CfDJ8MR3o8p3D45MotJmfAmDYnie4OP53w9sMF67ICHV1N2t4X9tf0PKnqzQraKkywKnxHjRMakwrJZNvbmBnN3Rd8cyLSQi-m1go77GzV2xOXiZuTYyN2gKWVYZCeKB8h3F7ofxGt9trmkrm4-Scb7R6SAoOWy48TVjAIbrBXpb-XYCtJ3VL8Hu3R0HntQ2Ol24ehO_VPeL_9RXP_SuZggLZEAXVg4vwAssGZUkJTkFa-U9w6ce7A1j-MblIYfmkv1T_kbKLauL8ZSpwjw19XTDDR4duxMLT9pr-538pDBi5-fH4BvoAh7bseidvesVb-bHhJAw3qMMdRVc9Fe2GDh2lgHz_uCb2wcuMXM-9ENgLWnRcbjdbW40X6_Ev4xbLw3FpBx0WjEQe6p7yFcxlpTUtbyCM0jRp6BOCTXtBmdymy-xB9mA2cGK_vJhmwHd922KjDsU9PBJPvo_IHZqQwwvr-xMU1BX63AhGgS5QXOWsWcZFttZnOxTbLAkswihygRzH_TmL7OHqhJGAAYDbQhOuYwXV9XTMpuHxrcQD303oq6C4SfCQ78gMGd40AbbNhOquEo6DWhLMxczvy6Ik6sk6__yJXAatc-HT_4n1QiUEX-2s1zFlpy_cI6PChabf6H--edgKmBUzY_BGWZoR356O9c5sz62yjuCOTHm5BPLZVI3Svl3_jpa_sFGDlGNt1e0nQ4ZYVpskCCQcLWNT3_1XmfLhne6CV3CAvpJnaz5wc6YXvul9VIsXT4xFK-iyrfl0I001-dbuX2bmcecZFSkoauDohtGjDSNU1LxCFzeTAadU1PQjb8VkvqRT1qukycIeA5AiYHH-qoprPYa9yaNng5Kj3fKhBdtsTmyywj4obzvucGkqO-ohqVFi8rDHMjVAV-X1Kp4m5o8pa7nVixQy4UMWUOPSFZgnLXCT0JpLsj_miLPjw7UG2r4jcBjKEAvO2mVm8KnWMBV_56zg6rEmS_8ClCmef2MH-OqkTIpokTxIuNl0Rm0D-PlFJppjjsRQIlS0gd_I59LP1CTHyCH6QKcNT0Ezh0EubJqf5IQFBEAphWbjCjp7jpZFRj3fHSrIiHpJgBLrWR1ew4eJt9yZ0foyRdOJ2HuNjOWNMlIXa0Eadi-VhkRVCqNiXDtYw30yDZ67PtCQtk5qoJtNpxq9rGpivzsWvttgn-tyErFeR_i0HRqqonJMt3pMbqiDq8fWZNqccf1KAbTnQT9xGmcWrluLoT8neWWvALnwG_n9AqFazJJjqWt4vL35DVlKo36PWRFfoXsK_xHG71F2Az45tB2wNnwR70qthFkEAAmcwgOuQELFHKeQ4CvPrIdo_YudlEudYxHeWYQDXzCBbwU5D5_Y4rcSbKVcx6dnjUUJxvqToTmhauZsCrwJqRJ5FOwbObi0uyt2CyLlBRI8eV7PnqncXkLq3F98tLcRwh1nyR3PcM2DP2ADLCjEBGKVH_RBCLT_E7KEpKUJ5-Pm95x0pHqBz7_EPslSDwPE9yZ1nIxM4CXw6PFQ_Hryr1VOU4fBKs8Rtxj23B9HgTSa49SR1J8Y7xBwDSNPMZgyo2XuJXLECzbeXdQTQkWfoYMYer2IHBAfUPphxKWyLFuTUKIOSe_vbktyJen-j9VtMM3KjFR34IAxIgr2FyZw4dI5IitgeEaCT30n626-N96pL_nSvQ7fzw7xpsfdlGs4y6xEQL5Kk3sKpUFW2Ib_7CF4OLpL_CEvusZWhaGYD1Wdi0tl3LG7rH8e4fmWqMGBuCcsmGiSP5MDKnmHpPGyv2voRpJwb604GLreec6BsZW__6XWvCR0A3ZjcctvKs7AeQriv4G2P6ghwTTGJiMXShRVEH257Sd1WBDaJL-0KucgEjexxSMZWJhZ54hncd_4Ju8tixuuJ_V62ehSWftsR7Iqf9cIu0l98CZd2zXb7adfpZcqnxS8nuJif3yu4mSkhYcIoGRKWf5QiYmX-JTrTJXSFAPd7aMF5Qkz09iKLKPB_5LEztjNVAVOzTpOSVCC5bAZZVqh9rbqwhHaxuPhfrIaE0y3nEXHHVrhou58svlaFjcU5ek6b-achVTAJW6_7k24KYVXIs4wbrpf1s5lkSGKCOJgru89wmlS73jXnSkuLZCpGNum49tl9aAC9ULZWy5QeS01HWZ1RKl1OghPgiABLOLeua60EmUxZ86vIOQ-18fRkWVdrS4Zj-PcD_CXD_t2cbnNZ-Z6O-_Ri8AuM3_Ifo30Jfl9USd-alqu7u7ttwv9YwKsrTpcWTDbku3OYL8aDgoVAofSXMqAs8rny0xbDbytBpKbgmaUNXoIaxotafbxMlJNrFzK4tl8qi3f5qWcdKcW31tXGUD5ZHnE2xn_hX7ataVCWR0bOrvH7MGuyYT29Jk5fCx3BWDbEC13OKU6bx1DkHNAQzesPBdc-eQDE25rBBnuA4U225XYD_29yF9e7BP1P6SOds_NPFe0XcsnPtUr-evN4rLzSxcBA-5rU4-QMbDVv8OTxYm1dbceam-O_lCx0U0-iNAy9-9Xo3qs3xH0Gwc30jBOM4cA9EZn-YZg9ceS_YHQO2wHkqg_x3BfQjTNAVensiB_6DmMjsyczsA44YTo_0AgrXFTYmzgdfOikYOYzlQZij9KYU3nDpSxKABi3YVLqYZFClQ1nYy-SDdSNl_YjMF-_HTjPGKzr-vtZbXq1lz1s-QKqDtkLiVso-CMLZjmVVMz0CaLDQPEznNmQKlB20fUozKMbgClmefeki-Tpk3q4uO6uYAry_7KkUluWajUVbMUVXjiqfd_cnGgW3ClErPeBVmMa4uCRXVZPFgBLu-8zUJXw6fIgWpFVuJXoDHgrkVwnqVQaD_T3iqTxUV-WI1NAIpK2i_IdLLZlT0gdXQzoM51B98VfHpFPjpJbkflQxKKWrBshHibiqqOoUOKUduSoLdbFqPCuFLRvZ-JIp4hN6GQCMXbe_d07IRDL7ADa_CTAX5fEx3m2XHPK8lkxZFdJ_uuIs7-PdBqBAm1r-VpUXMEDFLljvgikrzA4gcDB-REpi_MjSV3a3KSTPIMSALghRrUd9RtIgvs99IIUm1K7-8RyCXkW5cZKUM6-Qm_kMzjSGLLGpE7l3ADvHDDtVPZ4OrJH512YiAlpPIhRERri4u_Xvu1l2FCanmCUl1Qhb84ouYCouLT8WblLR_yX4OS0-PeqIBs2fxIpsOxzLI7KieofNMdWtzpP19OxykscKPzuBtR4mrRoheOYNeh4UGviuGgP4mD5BXT48SKB8h97JZCiWIcxzYw-pjAGQi3GNxXAF_xm7U_BOiji9bjodeU9LAiX47YfPvuZ9NZwwpYwFsiohFtmy677ZCLOAk0qj1tq_86RMqnxOLqY2w1yyVHL0njmtUrX9LB2xnaN0UemaudynHoIrktKgceHBoajMCh_o0JBMYHN6DovWYUesu8GQR1lrzj-rwM02CTmw2RKPGMfEZbgQ8IbyH71U7-5Vvr_4tpE7qfieGnRC3w4c4j_r_OZWYM1W-zrk88PfPXkNPuGSikbETOFPrCH2BBPVMzWn95wXthlk6cmHW2Re12LAV3gXyK-rkGVDpgvLqfriq5FKiph6vOJeJ8hS5M9SphSNoE4UhLxgZkoEnaJ-D9Oelx64gf7WiDQ',
    '.AspNetCore.Antiforgery.MzFEACH9dlA': 'CfDJ8Lcw237uOeNBnFU_CjgCptvnLG9p8CGsvUMR_DlDzA0dUNvojWeAFxuK1l4oocr1xllTx1OV1zYZpG9dzVFg6iXXnsDzuws5m0bJls_T-Aybvz7mT5kg9yyGJ7lEts4TyHgCAZ5ZkQqMzV1WTWOywzc',  # From --cookie parameter
    '_ga_BLEQGRBWCW': 'GS2.1.s1769265842$o71$g1$t1769266453$j12$l0$h0',
}

# Cookies para requisição de detalhes completos (atualizados do novo curl)
DETAIL_COOKIES = {
    '_pprv': 'eyJjb25zZW50Ijp7IjAiOnsibW9kZSI6ImVzc2VudGlhbCJ9LCIxIjp7Im1vZGUiOiJvcHQtaW4ifSwiMiI6eyJtb2RlIjoib3B0LWluIn0sIjMiOnsibW9kZSI6Im9wdC1pbiJ9LCI0Ijp7Im1vZGUiOiJvcHQtaW4ifSwiNSI6eyJtb2RlIjoib3B0LWluIn0sIjYiOnsibW9kZSI6Im9wdC1pbiJ9LCI3Ijp7Im1vZGUiOiJvcHQtaW4ifX0sInB1cnBvc2VzIjpudWxsLCJfdCI6Im1xcXZlM3ZxfG1iMmdnbWpxIn0%3D',
    '_pcid': '%7B%22browserId%22%3A%22mb2ggmjq1covlen4%22%2C%22_t%22%3A%22mqqve3vr%7Cmb2ggmjr%22%7D',
    '_pctx': '%7Bu%7DN4IgrgzgpgThIC4B2YA2qA05owMoBcBDfSREQpAeyRCwgEt8oBJAE0RXSwH18yBbAI6CAblADMIiAB9%2BAIwBMAcyX8AVvAC%2BQA',
    '_fbp': 'fb.2.1755524211764.90899100101412948',
    'didomi_token': 'eyJ1c2VyX2lkIjoiMTk4OWVhYzAtYTdhNy02ZDk0LTk3ODctNjVmNmI0YmMxODgzIiwiY3JlYXRlZCI6IjIwMjUtMDgtMTJUMTQ6MjU6MzEuNzcwWiIsInVwZGF0ZWQiOiIyMDI1LTA5LTI2VDEzOjI5OjQzLjA0NloiLCJ2ZW5kb3JzIjp7ImVuYWJsZWQiOlsiZ29vZ2xlIiwiYzpnb29nbGVhbmEtNFRYbkppZ1IiLCJjOnlhaG9vLWdlbWluaS1hbmQtZmx1cnJ5IiwiYzpwaWFub2h5YnItUjNWS0MycjQiLCJjOm1pY3Jvc29mdC1QemhhaEQ2NyJdfSwicHVycG9zZXMiOnsiZW5hYmxlZCI6WyJnZW9sb2NhdGlvbl9kYXRhIiwiZGV2aWNlX2NoYXJhY3RlcmlzdGljcyIsImF1ZGllbmNlbS1oSnhhZUdyUiJdfSwidmVuZG9yc19saSI6eyJlbmFibGVkIjpbImdvb2dsZSJdfSwidmVyc2lvbiI6MiwiYWMiOiJBRm1BQ0FGay5BRm1BQ0FGayJ9',
    'euconsent-v2': 'CQWCSgAQYWmsAAHABBENB9FsAP_AAEPgAAKIJ4QAwAaALzAngCeEAMAGgC8wJ4AAAAAA.f_gACHwAAAAA',
    '_ga': 'GA1.1.342535473.1755008733',
    '_ga_WTJXFBM2G9': 'GS2.1.s1760199278$o2$g0$t1760200038$j60$l0$h0',
    '_gcl_au': '1.1.161354091.1763134889.1684888494.1766968488.1766968488',
    'ATSCultureCookie': 'c%3Dpt-BR%7Cuic%3Dpt-BR',
    'ats-webui': 'CfDJ8MR3o8p3D45MotJmfAmDYnie4OP53w9sMF67ICHV1N2t4X9tf0PKnqzQraKkywKnxHjRMakwrJZNvbmBnN3Rd8cyLSQi-m1go77GzV2xOXiZuTYyN2gKWVYZCeKB8h3F7ofxGt9trmkrm4-Scb7R6SAoOWy48TVjAIbrBXpb-XYCtJ3VL8Hu3R0HntQ2Ol24ehO_VPeL_9RXP_SuZggLZEAXVg4vwAssGZUkJTkFa-U9w6ce7A1j-MblIYfmkv1T_kbKLauL8ZSpwjw19XTDDR4duxMLT9pr-538pDBi5-fH4BvoAh7bseidvesVb-bHhJAw3qMMdRVc9Fe2GDh2lgHz_uCb2wcuMXM-9ENgLWnRcbjdbW40X6_Ev4xbLw3FpBx0WjEQe6p7yFcxlpTUtbyCM0jRp6BOCTXtBmdymy-xB9mA2cGK_vJhmwHd922KjDsU9PBJPvo_IHZqQwwvr-xMU1BX63AhGgS5QXOWsWcZFttZnOxTbLAkswihygRzH_TmL7OHqhJGAAYDbQhOuYwXV9XTMpuHxrcQD303oq6C4SfCQ78gMGd40AbbNhOquEo6DWhLMxczvy6Ik6sk6__yJXAatc-HT_4n1QiUEX-2s1zFlpy_cI6PChabf6H--edgKmBUzY_BGWZoR356O9c5sz62yjuCOTHm5BPLZVI3Svl3_jpa_sFGDlGNt1e0nQ4ZYVpskCCQcLWNT3_1XmfLhne6CV3CAvpJnaz5wc6YXvul9VIsXT4xFK-iyrfl0I001-dbuX2bmcecZFSkoauDohtGjDSNU1LxCFzeTAadU1PQjb8VkvqRT1qukycIeA5AiYHH-qoprPYa9yaNng5Kj3fKhBdtsTmyywj4obzvucGkqO-ohqVFi8rDHMjVAV-X1Kp4m5o8pa7nVixQy4UMWUOPSFZgnLXCT0JpLsj_miLPjw7UG2r4jcBjKEAvO2mVm8KnWMBV_56zg6rEmS_8ClCmef2MH-OqkTIpokTxIuNl0Rm0D-PlFJppjjsRQIlS0gd_I59LP1CTHyCH6QKcNT0Ezh0EubJqf5IQFBEAphWbjCjp7jpZFRj3fHSrIiHpJgBLrWR1ew4eJt9yZ0foyRdOJ2HuNjOWNMlIXa0Eadi-VhkRVCqNiXDtYw30yDZ67PtCQtk5qoJtNpxq9rGpivzsWvttgn-tyErFeR_i0HRqqonJMt3pMbqiDq8fWZNqccf1KAbTnQT9xGmcWrluLoT8neWWvALnwG_n9AqFazJJjqWt4vL35DVlKo36PWRFfoXsK_xHG71F2Az45tB2wNnwR70qthFkEAAmcwgOuQELFHKeQ4CvPrIdo_YudlEudYxHeWYQDXzCBbwU5D5_Y4rcSbKVcx6dnjUUJxvqToTmhauZsCrwJqRJ5FOwbObi0uyt2CyLlBRI8eV7PnqncXkLq3F98tLcRwh1nyR3PcM2DP2ADLCjEBGKVH_RBCLT_E7KEpKUJ5-Pm95x0pHqBz7_EPslSDwPE9yZ1nIxM4CXw6PFQ_Hryr1VOU4fBKs8Rtxj23B9HgTSa49SR1J8Y7xBwDSNPMZgyo2XuJXLECzbeXdQTQkWfoYMYer2IHBAfUPphxKWyLFuTUKIOSe_vbktyJen-j9VtMM3KjFR34IAxIgr2FyZw4dI5IitgeEaCT30n626-N96pL_nSvQ7fzw7xpsfdlGs4y6xEQL5Kk3sKpUFW2Ib_7CF4OLpL_CEvusZWhaGYD1Wdi0tl3LG7rH8e4fmWqMGBuCcsmGiSP5MDKnmHpPGyv2voRpJwb604GLreec6BsZW__6XWvCR0A3ZjcctvKs7AeQriv4G2P6ghwTTGJiMXShRVEH257Sd1WBDaJL-0KucgEjexxSMZWJhZ54hncd_4Ju8tixuuJ_V62ehSWftsR7Iqf9cIu0l98CZd2zXb7adfpZcqnxS8nuJif3yu4mSkhYcIoGRKWf5QiYmX-JTrTJXSFAPd7aMF5Qkz09iKLKPB_5LEztjNVAVOzTpOSVCC5bAZZVqh9rbqwhHaxuPhfrIaE0y3nEXHHVrhou58svlaFjcU5ek6b-achVTAJW6_7k24KYVXIs4wbrpf1s5lkSGKCOJgru89wmlS73jXnSkuLZCpGNum49tl9aAC9ULZWy5QeS01HWZ1RKl1OghPgiABLOLeua60EmUxZ86vIOQ-18fRkWVdrS4Zj-PcD_CXD_t2cbnNZ-Z6O-_Ri8AuM3_Ifo30Jfl9USd-alqu7u7ttwv9YwKsrTpcWTDbku3OYL8aDgoVAofSXMqAs8rny0xbDbytBpKbgmaUNXoIaxotafbxMlJNrFzK4tl8qi3f5qWcdKcW31tXGUD5ZHnE2xn_hX7ataVCWR0bOrvH7MGuyYT29Jk5fCx3BWDbEC13OKU6bx1DkHNAQzesPBdc-eQDE25rBBnuA4U225XYD_29yF9e7BP1P6SOds_NPFe0XcsnPtUr-evN4rLzSxcBA-5rU4-QMbDVv8OTxYm1dbceam-O_lCx0U0-iNAy9-9Xo3qs3xH0Gwc30jBOM4cA9EZn-YZg9ceS_YHQO2wHkqg_x3BfQjTNAVensiB_6DmMjsyczsA44YTo_0AgrXFTYmzgdfOikYOYzlQZij9KYU3nDpSxKABi3YVLqYZFClQ1nYy-SDdSNl_YjMF-_HTjPGKzr-vtZbXq1lz1s-QKqDtkLiVso-CMLZjmVVMz0CaLDQPEznNmQKlB20fUozKMbgClmefeki-Tpk3q4uO6uYAry_7KkUluWajUVbMUVXjiqfd_cnGgW3ClErPeBVmMa4uCRXVZPFgBLu-8zUJXw6fIgWpFVuJXoDHgrkVwnqVQaD_T3iqTxUV-WI1NAIpK2i_IdLLZlT0gdXQzoM51B98VfHpFPjpJbkflQxKKWrBshHibiqqOoUOKUduSoLdbFqPCuFLRvZ-JIp4hN6GQCMXbe_d07IRDL7ADa_CTAX5fEx3m2XHPK8lkxZFdJ_uuIs7-PdBqBAm1r-VpUXMEDFLljvgikrzA4gcDB-REpi_MjSV3a3KSTPIMSALghRrUd9RtIgvs99IIUm1K7-8RyCXkW5cZKUM6-Qm_kMzjSGLLGpE7l3ADvHDDtVPZ4OrJH512YiAlpPIhRERri4u_Xvu1l2FCanmCUl1Qhb84ouYCouLT8WblLR_yX4OS0-PeqIBs2fxIpsOxzLI7KieofNMdWtzpP19OxykscKPzuBtR4mrRoheOYNeh4UGviuGgP4mD5BXT48SKB8h97JZCiWIcxzYw-pjAGQi3GNxXAF_xm7U_BOiji9bjodeU9LAiX47YfPvuZ9NZwwpYwFsiohFtmy677ZCLOAk0qj1tq_86RMqnxOLqY2w1yyVHL0njmtUrX9LB2xnaN0UemaudynHoIrktKgceHBoajMCh_o0JBMYHN6DovWYUesu8GQR1lrzj-rwM02CTmw2RKPGMfEZbgQ8IbyH71U7-5Vvr_4tpE7qfieGnRC3w4c4j_r_OZWYM1W-zrk88PfPXkNPuGSikbETOFPrCH2BBPVMzWn95wXthlk6cmHW2Re12LAV3gXyK-rkGVDpgvLqfriq5FKiph6vOJeJ8hS5M9SphSNoE4UhLxgZkoEnaJ-D9Oelx64gf7WiDQ',
    '.AspNetCore.Antiforgery.MzFEACH9dlA': 'CfDJ8Lcw237uOeNBnFU_CjgCptvnLG9p8CGsvUMR_DlDzA0dUNvojWeAFxuK1l4oocr1xllTx1OV1zYZpG9dzVFg6iXXnsDzuws5m0bJls_T-Aybvz7mT5kg9yyGJ7lEts4TyHgCAZ5ZkQqMzV1WTWOywzc',
    '_ga_BLEQGRBWCW': 'GS2.1.s1769265842$o71$g1$t1769267280$j7$l0$h0',
    '.AspNetCore.Mvc.CookieTempDataProvider': 'CfDJ8MR3o8p3D45MotJmfAmDYngCorSzxv8NTVkxF8Qt90NxF7Mr-MTh53mbDpv0R05R0QtPhM0dW4YcBTat6pqOEEGl5dVwmzmvJAkVN7slOxzKTSTmC00caEIItH-PYVb9-kEillvlzJrPhV-fwua1weY',
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
    'birth_date': r'<div class="match-personal-data[^"]*">.*?\(Nasceu\s+([^)]+)\)',
    'match_search_total': r'<span id="MatchSearchTotal">([^<]+)</span>'
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

def build_pagination_request_data(page_number, cep, age_min=None, age_max=None):
    """Constrói os dados da requisição para paginação"""
    data = {
        'Pagination[PageNumber]': page_number,
        'Pagination[PageSize]': PAGE_SIZE,
        'CEP': cep,
        'MaxDistance': MAX_DISTANCE,
        # **LOCATION_FILTERS
    }
    
    # Add age filters only if provided
    if age_min is not None:
        data['AgeMin'] = age_min
    if age_max is not None:
        data['AgeMax'] = age_max
    
    return data


def extract_match_search_total(html_content):
    """Extrai o número total de matches do HTML"""
    match = re.search(REGEX_PATTERNS['match_search_total'], html_content)
    if match:
        match_text = match.group(1).strip()
        # Remove dots used as thousands separators (e.g., "8.259" -> "8259")
        match_number = match_text.replace('.', '')
        try:
            return int(match_number)
        except ValueError:
            return None
    return None

def fetch_candidate_ids_from_page(page_number, cep, age_min=None, age_max=None):
    """Busca e retorna os IDs dos candidatos de uma página"""
    request_data = build_pagination_request_data(page_number, cep, age_min=age_min, age_max=age_max)
    
    start_time = time.time()
    response = requests.get(
        LIST_CANDIDATES_URL,
        headers=HEADERS,
        params=request_data,
        cookies=COOKIES,
#         proxies=PROXIES
    )
    elapsed_time = time.time() - start_time
    
    response.encoding = response.apparent_encoding or 'utf-8'
    candidate_ids = sorted(set(re.findall(REGEX_PATTERNS['candidate_id'], response.text)))
    
    print(f"  Requisição de lista: {elapsed_time:.2f}s")
    
    return candidate_ids, response.text


def fetch_candidate_full_details(candidate_id):
    """Busca os detalhes completos de um candidato (HTML completo)"""
    detail_url = f"{DETAIL_CANDIDATE_FULL_URL}/{candidate_id}"
    
    # Create headers with dynamic Referer based on candidate_id
    headers = DETAIL_FULL_HEADERS.copy()
    headers['Referer'] = f'https://pandape.infojobs.com.br/Company/CandidateCatho/Detail/{candidate_id}'
    
    start_time = time.time()
    response = requests.get(
        detail_url,
        headers=headers,
        cookies=DETAIL_COOKIES,
#         proxies=PROXIES
    )
    elapsed_time = time.time() - start_time
    
    response.encoding = response.apparent_encoding or 'utf-8'
    
    print(f"    Requisição de detalhes (ID {candidate_id}): {elapsed_time:.2f}s")
    
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

def insert_supabase(candidato_data, supabase_cc):
    # Para a nova tabela, não temos mais um ID de candidato como chave primária
    # A tabela usa id auto-gerado, então sempre fazemos INSERT
    # Se houver duplicatas baseadas em outros campos, podemos adicionar lógica aqui
    
    try:
        # Tenta o INSERT direto
        # A tabela tem id auto-gerado, então sempre inserimos novos registros
        return supabase_cc.table(SUPABASE_TABLE_NAME).insert(candidato_data).execute()

    except APIError as e:
        # Se houver erro (ex: constraint violation), apenas loga
        print(f"Erro ao inserir candidato: {e}", file=sys.stderr)
        # Para a nova estrutura, não temos mais update por ID de candidato
        # Se precisar de lógica de update, pode ser baseada em email, phone, ou outros campos únicos
        raise

def format_value_for_csv(value):
    """Formata valores para CSV: None vira string vazia, números mantêm formato"""
    if value is None:
        return ''  # String vazia para NULL no CSV (será convertido para NULL no banco)
    return str(value)  # Converte tudo para string para o CSV

def process_single_candidate(candidate_id, batch_number, record_count, supabase_cc, cep):
    """Processa um único candidato: busca dados e salva no CSV"""
    try:
        full_html = fetch_candidate_full_details(candidate_id)
        candidate_data = extract_candidate_data(candidate_id, full_html)

        # Formatar valores para o novo schema da tabela base_catho_full
        # Nota: 'id' é auto-gerado pela tabela, não incluímos aqui
        candidate_row = {
            'id': candidate_id,
            'name': candidate_data['name'] if candidate_data['name'] else None,
            'job': candidate_data['job'] if candidate_data['job'] else None,
            'phone': candidate_data['phone'] if candidate_data['phone'] else None,
            'email': candidate_data['email'] if candidate_data['email'] else None,
            'salary': candidate_data['salary'] if candidate_data['salary'] else None,  # Salário como número ou None
            'address': candidate_data['address'] if candidate_data['address'] else None,
            'gender': candidate_data['gender'] if candidate_data['gender'] else None,
            'gender_marital': candidate_data['marital_status'] if candidate_data['marital_status'] else None,
            'birth_date': candidate_data['birth_date'],  # Data no formato yyyy-mm-dd ou None
            'instancia': INSTANCIA,
            'cep': cep_to_bigint(cep)  # CEP como bigint (sem traços)
        }
        
        insert_supabase(candidate_row, supabase_cc)
        #save_candidate_to_csv(candidate_row, batch_number)
        #print(f"      ✓ Dados salvos: {candidate_data.get('name', 'N/A')}")
        return record_count + 1
    
    except Exception as e:
        print(f"      Erro ao processar candidato {candidate_id}: {e}")
        return record_count


def process_page(page_number, batch_number, record_count, supabase_cc, cep, age_min=None, age_max=None):
    """Processa uma página de candidatos"""
    print(f"\n{'='*50}")
    print(f"Processando página {page_number}...")
    print(f"{'='*50}")
    
    candidate_ids, resp = fetch_candidate_ids_from_page(page_number, cep, age_min=age_min, age_max=age_max)
    match_total = extract_match_search_total(resp)
    if match_total is not None:
        print(f"  Total de matches encontrados: {match_total}")
    
    if not candidate_ids:
        print(f"  Nenhum ID encontrado na página {page_number}. Encerrando...")
        # print("Resposta da página:", resp)
        return False, batch_number, record_count
    
    print(f"Encontrados {len(candidate_ids)} candidatos na página {page_number}")
    print(f"Lote atual: {batch_number} | Registros no lote: {record_count}/{BATCH_SIZE}")
    
    current_batch = batch_number
    current_count = record_count
    
    for idx, candidate_id in enumerate(candidate_ids, 1):
        # Se atingiu o tamanho do lote, criar novo arquivo
        if current_count >= BATCH_SIZE:
            current_batch += 1
            current_count = 0
            print(f"Lote atual: {current_batch} | Registros no lote: {current_count}/{BATCH_SIZE}")
        
        current_count = process_single_candidate(candidate_id, current_batch, current_count, supabase_cc, cep)
    
    print(f"\nPágina {page_number} concluída: {len(candidate_ids)} candidatos processados")
    print(f"Total no lote atual: {current_count}/{BATCH_SIZE}")
    
    return True, current_batch, current_count


def process_all_pages(cep, initial_page=None, max_page=None, age_min=None, age_max=None):
    """Processa todas as páginas de candidatos para um CEP específico"""
    # Usar valores padrão globais se não fornecidos
    if initial_page is None:
        initial_page = INITIAL_PAGE
    if max_page is None:
        max_page = MAX_PAGE
    
    print("\n" + "="*50)
    print("INICIANDO PROCESSAMENTO DE CANDIDATOS")
    print("="*50)
    print(f"Configurações:")
    print(f"   - CEP: {cep}")
    print(f"   - Páginas a processar: {initial_page} até {max_page}")
    print(f"   - Tamanho do lote: {BATCH_SIZE} registros por arquivo")
    if age_min is not None:
        print(f"   - Idade mínima: {age_min}")
    if age_max is not None:
        print(f"   - Idade máxima: {age_max}")
    print("="*50)
    
    # Inicializar primeiro arquivo
    batch_number = 1
    record_count = 0
    supabase_cc = supabase_connection()
    
    page_number = initial_page
    total_pages_processed = 0
    
    while page_number <= max_page:
        try:
            should_continue, batch_number, record_count = process_page(page_number, batch_number, record_count, supabase_cc, cep, age_min=age_min, age_max=age_max)
            if not should_continue:
                break
            
            total_pages_processed += 1
            
        except Exception as e:
            print(f"\nErro na página {page_number}: {e}")
            import traceback
            traceback.print_exc()
            break
        page_number += 1
    
    print("\n" + "="*50)
    print(f"PROCESSAMENTO CONCLUÍDO")
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
    parser = argparse.ArgumentParser(description="Scrape candidate data for a single CEP with all age ranges")
    parser.add_argument('--max-distance', type=int, required=True, help='Filtro MaxDistance (obrigatório)')
    parser.add_argument('--cep', type=str, required=True, help='CEP único (obrigatório)')
    parser.add_argument('--initial-page', type=int, default=INITIAL_PAGE, help=f'Página inicial para processar (padrão: {INITIAL_PAGE})')
    parser.add_argument('--max-page', type=int, default=MAX_PAGE, help=f'Página máxima para processar (padrão: {MAX_PAGE})')
    parser.add_argument("--instancia", required=True, help="Instancia para identificar a execução")
    parser.add_argument('--age-min', type=int, default=None, help='Idade mínima do candidato (opcional)')
    parser.add_argument('--age-max', type=int, default=None, help='Idade máxima do candidato (opcional)')
    parser.add_argument('--min-max-age-list', type=str, default=None, 
                       help='JSON list of age ranges, e.g., [{"min": 1, "max": 18}, {"min": 18, "max": 20}]')

    return parser.parse_args()

if __name__ == "__main__":
    args = parse_arguments()

    MAX_DISTANCE = args.max_distance
    INSTANCIA = args.instancia
    CEP = args.cep

    print("\n" + "="*70)
    print(f"PROCESSANDO CEP: {CEP}")
    print("="*70)

    # Parse age range list if provided
    age_ranges = None
    if args.min_max_age_list:
        try:
            age_ranges = json.loads(args.min_max_age_list)
            if not isinstance(age_ranges, list):
                print("Error: --min-max-age-list must be a JSON array", file=sys.stderr)
                sys.exit(1)
            # Validate each range
            for i, age_range in enumerate(age_ranges):
                if not isinstance(age_range, dict):
                    print(f"Error: Age range {i} must be a JSON object", file=sys.stderr)
                    sys.exit(1)
                if 'min' not in age_range or 'max' not in age_range:
                    print(f"Error: Age range {i} must have 'min' and 'max' keys", file=sys.stderr)
                    sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in --min-max-age-list: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.age_min is not None or args.age_max is not None:
        # Single age range from --age-min and --age-max
        age_ranges = [{'min': args.age_min, 'max': args.age_max}]

    total_start_time = time.time()
    cep_success = True
    
    # Process all age ranges for this CEP
    if age_ranges:
        print(f"Processando {len(age_ranges)} faixa(s) etária(s) para este CEP")
        for age_idx, age_range in enumerate(age_ranges, 1):
            age_min = age_range['min']
            age_max = age_range['max']
            print(f"\n--- Faixa etária {age_idx}/{len(age_ranges)}: {age_min}-{age_max} anos ---")
            
            try:
                start_time = time.time()
                total_batches = process_all_pages(
                    cep=CEP,
                    initial_page=args.initial_page, 
                    max_page=args.max_page,
                    age_min=age_min,
                    age_max=age_max
                )
                end_time = time.time()
                execution_time = end_time - start_time
                
                print(f"\n✓ CEP {CEP} (idade {age_min}-{age_max}) concluído em {execution_time:.2f}s")
                
            except KeyboardInterrupt:
                print(f"\n\nInterrompido pelo usuário durante CEP {CEP} (idade {age_min}-{age_max})")
                raise  # Re-raise to stop everything
            except Exception as e:
                print(f"\n✗ Erro ao processar CEP {CEP} (idade {age_min}-{age_max}): {e}", file=sys.stderr)
                import traceback
                traceback.print_exc()
                cep_success = False
                # Continue with next age range - don't skip remaining age ranges
                continue
        
        # Only mark CEP as processed after ALL age ranges are done
        if cep_success:
            print(f"\n✓✓ CEP {CEP} completamente processado (todas as {len(age_ranges)} faixas etárias concluídas)")
        else:
            print(f"\n⚠ CEP {CEP} processado com alguns erros (algumas faixas etárias falharam)")
    else:
        # No age ranges specified, process with no age filter
        try:
            start_time = time.time()
            total_batches = process_all_pages(
                cep=CEP,
                initial_page=args.initial_page, 
                max_page=args.max_page,
                age_min=None,
                age_max=None
            )
            end_time = time.time()
            execution_time = end_time - start_time
            
            print(f"\n✓ CEP {CEP} concluído em {execution_time:.2f}s")
            cep_success = True
            
        except KeyboardInterrupt:
            print(f"\n\nInterrompido pelo usuário durante CEP {CEP}")
            raise  # Re-raise to stop everything
        except Exception as e:
            print(f"\n✗ Erro ao processar CEP {CEP}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            cep_success = False
    
    total_end_time = time.time()
    total_execution_time = total_end_time - total_start_time
    
    print("\n" + "="*70)
    print(f"PROCESSAMENTO DO CEP {CEP} COMPLETO")
    print(f"Tempo total: {total_execution_time:.2f}s")
    if not cep_success:
        print("Alguns erros ocorreram durante o processamento")
    print("="*70)
    
    if not cep_success:
        sys.exit(1)
