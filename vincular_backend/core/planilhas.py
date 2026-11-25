"""Leitura, validação e geração de planilhas (sem dependência do Django)."""
import datetime as dt
import io
import re
import unicodedata

from openpyxl import Workbook, load_workbook

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

COLUNAS_CRIANCA = ["nome", "data_nascimento", "codigo_v", "responsavel", "telefone", "codigo_rm", "distrito"]
OBRIGATORIAS = ["nome", "data_nascimento", "codigo_v", "responsavel", "telefone"]

ALIASES = {
    "nome": "nome", "nome_da_crianca": "nome", "crianca": "nome",
    "data_nascimento": "data_nascimento", "data_de_nascimento": "data_nascimento",
    "nascimento": "data_nascimento", "dt_nascimento": "data_nascimento",
    "codigo_v": "codigo_v", "cod_v": "codigo_v", "codigo_vincular": "codigo_v",
    "responsavel": "responsavel", "nome_do_responsavel": "responsavel", "nome_responsavel": "responsavel",
    "telefone": "telefone", "telefone_para_contato": "telefone",
    "telefone_contato": "telefone", "contato": "telefone",
    "codigo_rm": "codigo_rm", "cod_rm": "codigo_rm", "rm": "codigo_rm",
    "distrito": "distrito",
}

FORMATOS_DATA = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y")


class ErroPlanilha(Exception):
    """Problema geral do arquivo (formato, cabeçalho ausente...)."""


def _normalizar(texto):
    ascii_ = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_.lower()).strip("_")


def _texto(valor):
    if valor is None:
        return None
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    texto = str(valor).strip()
    return texto or None


def _data(valor):
    if valor is None or valor == "":
        return None
    if isinstance(valor, dt.datetime):
        return valor.date()
    if isinstance(valor, dt.date):
        return valor
    texto = str(valor).strip()
    for formato in FORMATOS_DATA:
        try:
            return dt.datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    raise ValueError(f"data inválida: {texto!r}")


def ler_linhas(arquivo):
    """Retorna [(numero_da_linha, {coluna: valor_bruto})] a partir de um .xlsx."""
    try:
        planilha = load_workbook(arquivo, read_only=True, data_only=True)
    except Exception as exc:  # arquivo corrompido ou formato errado
        raise ErroPlanilha("Não foi possível ler o arquivo. Envie uma planilha .xlsx válida.") from exc

    linhas = planilha.active.iter_rows(values_only=True)
    cabecalho = None
    resultado = []
    for numero, valores in enumerate(linhas, start=1):
        if cabecalho is None:
            if not any(v not in (None, "") for v in valores):
                continue
            cabecalho = {}
            for indice, titulo in enumerate(valores):
                canonico = ALIASES.get(_normalizar(titulo)) if titulo is not None else None
                if canonico and canonico not in cabecalho.values():
                    cabecalho[indice] = canonico
            faltando = [c for c in OBRIGATORIAS if c not in cabecalho.values()]
            if faltando:
                raise ErroPlanilha("Colunas obrigatórias ausentes: " + ", ".join(faltando) + ".")
            continue
        registro = {coluna: valores[indice] if indice < len(valores) else None
                    for indice, coluna in cabecalho.items()}
        if all(v in (None, "") for v in registro.values()):
            continue
        resultado.append((numero, registro))
    if cabecalho is None:
        raise ErroPlanilha("A planilha está vazia.")
    return resultado


def validar_linhas(linhas, hoje=None):
    """Valida e normaliza. Retorna (registros, erros)."""
    hoje = hoje or dt.date.today()
    registros, erros, vistos = [], [], {}
    for numero, bruto in linhas:
        problemas = []
        item = {"linha": numero}
        for campo in ("nome", "codigo_v", "responsavel", "telefone", "codigo_rm", "distrito"):
            item[campo] = _texto(bruto.get(campo))
        try:
            item["data_nascimento"] = _data(bruto.get("data_nascimento"))
        except ValueError as exc:
            item["data_nascimento"] = None
            problemas.append(str(exc))
        for campo in OBRIGATORIAS:
            if item.get(campo) is None and not (campo == "data_nascimento" and problemas):
                problemas.append(f"campo obrigatório vazio: {campo}")
        if item["data_nascimento"] and item["data_nascimento"] > hoje:
            problemas.append("data de nascimento no futuro")
        codigo = item["codigo_v"]
        if codigo:
            if codigo in vistos:
                problemas.append(f"Código V repetido (já aparece na linha {vistos[codigo]})")
            else:
                vistos[codigo] = numero
        if problemas:
            erros.append({"linha": numero, "erro": "; ".join(problemas)})
        else:
            registros.append(item)
    return registros, erros


def gerar_xlsx(titulo, cabecalhos, linhas):
    planilha = Workbook()
    aba = planilha.active
    aba.title = titulo[:31]
    aba.append(cabecalhos)
    for linha in linhas:
        aba.append(list(linha))
    for coluna in aba.columns:
        largura = max((len(str(c.value)) for c in coluna if c.value is not None), default=8)
        aba.column_dimensions[coluna[0].column_letter].width = min(largura + 2, 50)
    aba.freeze_panes = "A2"
    saida = io.BytesIO()
    planilha.save(saida)
    return saida.getvalue()


def modelo_importacao_criancas():
    cabecalhos = ["nome", "data_nascimento", "codigo_v", "responsavel", "telefone", "codigo_rm", "distrito"]
    exemplo = ["Maria da Silva", dt.date(2016, 5, 20), "V0001", "Ana da Silva", "88999999999", "", ""]
    return gerar_xlsx("criancas", cabecalhos, [exemplo])
