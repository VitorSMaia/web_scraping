"""
Coleta, registro acumulativo (`dados_coletados`) e sincronização com Google Sheets.

Este módulo reutiliza o fluxo de coleta do ``main.ScraperOrchestrator`` e acrescenta:
persistência de log local (append-only) e atualização seletiva em planilha online.

Variáveis de ambiente úteis
---------------------------
``GOOGLE_SERVICE_ACCOUNT_FILE``
    Caminho absoluto ou relativo para o JSON da conta de serviço Google.
    Se omitido, tenta ``credentials.json`` na raiz do projeto.

``CPFS``
    Lista de CPFs separados por vírgula (mesmo formato do ``main.py``).

``SPREADSHEET_URL`` / ``GOOGLE_SHEET_URL``
    URL completa da planilha para sincronização automática no ``__main__``.

``SHEET_WORKSHEET_TITLE``
    Nome da aba (worksheet). Padrão: primeira aba da planilha.
"""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, Optional, Sequence, Tuple

import gspread
from dotenv import load_dotenv
from google.auth.exceptions import GoogleAuthError
from google.oauth2.service_account import Credentials
from gspread.cell import Cell
from gspread.exceptions import APIError, SpreadsheetNotFound

from main import ScraperOrchestrator
from scraper.logger import Logger

# Escopos recomendados para gspread + Sheets API v4
_SCOPES: Tuple[str, ...] = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
)

_LOG_PADRAO = Path("resultados") / "dados_coletados.jsonl"

# Cabeçalhos alinhados ao ``DataExporter`` (planilhas geradas pelo projeto).
_INTERNAL_TO_SHEET_HEADER: dict[str, str] = {
    "nome": "NOME",
    "cpf": "CPF",
    "forma_ingresso_vinculos": "FORMA DE INGRESSO",
    "data_matricula": "DATA MATRÍCULA",
    "matricula": "MATRÍCULA",
    "email": "E-MAIL",
    "celular_financeiro": "CELULAR FINANCEIRO",
    "status_matricula": "STATUS",
    "rematricula_recente": "REMATRÍCULADO",
    "data_ultima_rematricula": "DATA REMATI",
    "horas_extensao": "HORAS DE EXTENSÃO",
    "qtde_horas_complementares": "QTDE DE HORAS COMPLEMENTARES",
    "email_financeiro": "EMAIL FINANCEIRO",
    "situacao_academica": "SITUAÇÃO ACADÊMICA",
    "disciplinas_20261": "DISCIPLINAS 2026.1",
    "metodo_processamento": "MÉTODO DE PROCESSAMENTO",
    "unidade_vinculos": "UNIDADE",
    "matriz_curricular": "MATRIZ CURRICULAR",
    "ano_ingresso": "ANO INGRESSO",
    "periodo_ingresso": "PERÍODO INGRESSO",
    "curso_vinculos": "CURSO VINCULOS",
    "situacao_vinculos": "SITUAÇÃO VINCULOS",
}


def _normalizar_texto_busca(s: str) -> str:
    """Remove acentos, espaços extras e padroniza maiúsculas para comparação de cabeçalhos."""
    s = str(s).strip().upper()
    s = "".join(
        c
        for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(s.split())


def _somente_digitos(s: str) -> str:
    return re.sub(r"\D", "", str(s))


def _celula_considerada_vazia(valor: Any) -> bool:
    if valor is None:
        return True
    t = str(valor).strip()
    if not t:
        return True
    if t.lower() in ("nan", "none", "null"):
        return True
    return False


def extrair_id_planilha(url: str) -> str:
    """
    Extrai o identificador da planilha a partir da URL do Google Sheets.

    :param url: URL no formato ``https://docs.google.com/spreadsheets/d/<ID>/...``
    :return: Identificador da planilha.
    :raises ValueError: Se a URL for inválida ou não contiver o ID.
    """
    if not url or not str(url).strip():
        raise ValueError("URL da planilha não pode ser vazia.")
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", str(url))
    if not m:
        raise ValueError(
            "URL inválida: não foi possível localizar o ID (padrão /spreadsheets/d/<ID>/)."
        )
    return m.group(1)


def obter_caminho_credenciais_google() -> Path:
    """
    Resolve o caminho do JSON da conta de serviço.

    Ordem: ``GOOGLE_SERVICE_ACCOUNT_FILE`` → ``GOOGLE_APPLICATION_CREDENTIALS`` → ``credentials.json``.

    :return: Caminho do arquivo de credenciais.
    :raises FileNotFoundError: Se nenhum arquivo válido for encontrado.
    """
    candidatos = [
        os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"),
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        str(Path.cwd() / "credentials.json"),
    ]
    for c in candidatos:
        if not c:
            continue
        p = Path(c).expanduser()
        if p.is_file():
            return p
    raise FileNotFoundError(
        "Credenciais Google não encontradas. Defina GOOGLE_SERVICE_ACCOUNT_FILE "
        "ou coloque credentials.json na raiz do projeto."
    )


def criar_cliente_gspread() -> gspread.Client:
    """
    Autentica e retorna um cliente gspread (conta de serviço).

    :return: Cliente autorizado.
    :raises FileNotFoundError: Se o arquivo de credenciais não existir.
    :raises GoogleAuthError: Se a autenticação falhar.
    """
    path = obter_caminho_credenciais_google()
    try:
        creds = Credentials.from_service_account_file(str(path), scopes=_SCOPES)
        return gspread.authorize(creds)
    except GoogleAuthError:
        raise
    except Exception as e:  # noqa: BLE001 — repacota mensagem para o chamador
        raise GoogleAuthError(f"Falha ao carregar credenciais em {path}: {e}") from e


def validar_registro_para_planilha(registro: Mapping[str, Any]) -> Tuple[bool, list[str]]:
    """
    Valida um dicionário de dados coletados antes de enviar à planilha.

    :param registro: Mapa com chaves internas (ex.: ``cpf``, ``nome``).
    :return: Tupla ``(ok, erros)`` onde ``erros`` é a lista de mensagens.
    """
    erros: list[str] = []
    if not isinstance(registro, Mapping):
        return False, ["Registro deve ser um mapeamento (dict-like)."]
    cpf = registro.get("cpf")
    digitos = _somente_digitos(cpf or "")
    if not digitos:
        erros.append("Campo 'cpf' ausente ou inválido.")
    elif len(digitos) < 10 or len(digitos) > 11:
        erros.append(
            f"CPF com quantidade de dígitos inesperada ({len(digitos)}); esperado 10 ou 11 dígitos."
        )
    for chave, valor in registro.items():
        if valor is None:
            continue
        s = str(valor)
        if s.startswith("="):
            erros.append(f"Valor suspeito (fórmula?) em '{chave}' foi rejeitado.")
            break
    return (len(erros) == 0), erros


def montar_valores_por_cabecalho(
    registro: Mapping[str, Any],
    unidade_sistema: str,
    data_atualizacao: Optional[str] = None,
) -> dict[str, str]:
    """
    Converte o registro interno em valores indexados pelo **cabeçalho** da planilha.

    Replica a lógica de ``DataExporter`` para ``DATA MATRÍCULA`` (confirmação com fallback).

    :param registro: Dados do aluno (mesmo formato produzido pelo scraper).
    :param unidade_sistema: Sigla da unidade (ex.: ``USJT``).
    :param data_atualizacao: Se ``None``, usa data/hora atual no formato ``%d/%m/%Y %H:%M:%S``.
    :return: Dicionário ``{cabeçalho_planilha: valor_str}``.
    """
    agora = data_atualizacao or datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    dm_conf = str(registro.get("data_matricula_conf") or "").strip()
    dm = str(registro.get("data_matricula") or "").strip()
    data_matricula_final = dm_conf or dm

    out: dict[str, str] = {
        "DATA DE ATUALIZAÇÃO": agora,
        "NOME": str(registro.get("nome") or ""),
        "CPF": str(registro.get("cpf") or ""),
        "UNIDADE": str(unidade_sistema or "").strip().upper() or str(registro.get("unidade_vinculos") or ""),
        "FORMA DE INGRESSO": str(registro.get("forma_ingresso_vinculos") or ""),
        "DATA MATRÍCULA": data_matricula_final,
        "MATRÍCULA": str(registro.get("matricula") or ""),
        "E-MAIL": str(registro.get("email") or ""),
        "CELULAR FINANCEIRO": str(registro.get("celular_financeiro") or ""),
        "STATUS": str(registro.get("status_matricula") or ""),
        "REMATRÍCULADO": str(registro.get("rematricula_recente") or ""),
        "DATA REMATI": str(registro.get("data_ultima_rematricula") or ""),
        "HORAS DE EXTENSÃO": str(registro.get("horas_extensao") or ""),
        "QTDE DE HORAS COMPLEMENTARES": str(registro.get("qtde_horas_complementares") or ""),
        "EMAIL FINANCEIRO": str(registro.get("email_financeiro") or ""),
        "SITUAÇÃO ACADÊMICA": str(registro.get("situacao_academica") or ""),
        "DISCIPLINAS 2026.1": str(registro.get("disciplinas_20261") or ""),
        "MÉTODO DE PROCESSAMENTO": str(registro.get("metodo_processamento") or ""),
    }
    # Campos extras do modelo base (se existirem na planilha com estes nomes)
    extras = (
        "matriz_curricular",
        "ano_ingresso",
        "periodo_ingresso",
        "unidade_vinculos",
        "curso_vinculos",
        "situacao_vinculos",
    )
    for k in extras:
        label = _INTERNAL_TO_SHEET_HEADER.get(k)
        if label and registro.get(k):
            out.setdefault(label, str(registro.get(k) or ""))
    return {k: (v if v is not None else "") for k, v in out.items()}


def registrar_entradas_log_acumulativo(
    registros: Sequence[Mapping[str, Any]],
    logger: Optional[Logger] = None,
    caminho_arquivo: Path | str = _LOG_PADRAO,
    registro_em: Optional[datetime] = None,
) -> Path:
    """
    Acrescenta cada registro ao arquivo de log **sem apagar** entradas anteriores.

    Formato: JSON Lines (uma linha JSON por entrada), cada objeto contém
    ``registro_em`` (ISO 8601) e ``dados`` (objeto com os campos coletados).

    :param registros: Sequência de mapas de dados coletados.
    :param logger: Logger do projeto; se informado, mensagens são registradas.
    :param caminho_arquivo: Destino do arquivo JSONL.
    :param registro_em: Instantâneo único do lote; padrão: ``datetime.now()``.
    :return: Caminho absoluto do arquivo utilizado.
    """
    path = Path(caminho_arquivo)
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = registro_em or datetime.now()
    ts_iso = ts.isoformat(timespec="seconds")
    n = 0
    with path.open("a", encoding="utf-8") as f:
        for dados in registros:
            linha = {"registro_em": ts_iso, "dados": dict(dados)}
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
            n += 1
    msg = f"Log acumulativo: {n} entrada(s) gravadas em {path.resolve()}"
    if logger:
        logger.log(msg)
    else:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}")
    return path.resolve()


def carregar_log_acumulativo(caminho_arquivo: Path | str = _LOG_PADRAO) -> list[dict[str, Any]]:
    """
    Lê todas as linhas do log JSONL.

    :param caminho_arquivo: Arquivo gerado por ``registrar_entradas_log_acumulativo``.
    :return: Lista de objetos ``{"registro_em": str, "dados": dict}``.
    """
    path = Path(caminho_arquivo)
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _indice_coluna_por_nome(
    cabecalhos: Sequence[str], nome_coluna_busca: str
) -> int:
    alvo = _normalizar_texto_busca(nome_coluna_busca)
    for i, nome in enumerate(cabecalhos):
        if _normalizar_texto_busca(nome) == alvo:
            return i
    raise ValueError(
        f"Coluna de busca '{nome_coluna_busca}' não encontrada entre os cabeçalhos da planilha."
    )


def _localizar_linha_por_valor(
    linhas: Sequence[Sequence[str]],
    indice_coluna: int,
    valor_busca: str,
) -> Optional[int]:
    """Retorna índice 0-based da linha de dados (exclui cabeçalho) ou ``None``."""
    if not linhas:
        return None
    vb = str(valor_busca).strip()
    vb_digitos = _somente_digitos(vb)
    # Identificadores numéricos (CPF etc.): comparar só dígitos quando a busca tiver 10+ dígitos
    usar_so_digitos = len(vb_digitos) >= 10
    for r in range(1, len(linhas)):
        row = linhas[r]
        if indice_coluna >= len(row):
            continue
        cell = row[indice_coluna]
        if usar_so_digitos:
            ok = _somente_digitos(cell) == vb_digitos
        else:
            ok = str(cell).strip().lower() == vb.lower()
        if ok:
            return r
    return None


def sincronizar_registro_na_planilha(
    spreadsheet_url: str,
    nome_coluna_busca: str,
    valor_busca: str,
    registro: Mapping[str, Any],
    unidade_sistema: str,
    logger: Optional[Logger] = None,
    worksheet_title: Optional[str] = None,
    cliente: Optional[gspread.Client] = None,
) -> dict[str, Any]:
    """
    Localiza uma linha pelo valor em ``nome_coluna_busca`` e preenche **apenas células vazias**.

    Não sobrescreve células que já contenham texto (após ``strip``).

    :param spreadsheet_url: URL completa da planilha Google.
    :param nome_coluna_busca: Nome do cabeçalho da coluna usada na busca (ex.: ``CPF``).
    :param valor_busca: Valor a localizar nessa coluna (ex.: CPF do aluno).
    :param registro: Dados coletados (formato interno do scraper).
    :param unidade_sistema: Sigla da unidade para coluna ``UNIDADE`` quando aplicável.
    :param logger: Logger opcional do projeto.
    :param worksheet_title: Nome da aba; se ``None``, usa a primeira aba.
    :param cliente: Cliente gspread reutilizável; se ``None``, autentica automaticamente.
    :return: Resumo ``{"atualizadas": int, "ignoradas": int, "linha_planilha": int | None, "avisos": [...]}``.
    """
    ok, erros = validar_registro_para_planilha(registro)
    if not ok:
        raise ValueError("Registro inválido: " + "; ".join(erros))

    vb = str(valor_busca).strip()
    if not vb:
        raise ValueError(
            "valor_busca vazio: informe o valor a localizar na coluna de busca (ex.: CPF sem máscara)."
        )

    valores = montar_valores_por_cabecalho(registro, unidade_sistema=unidade_sistema)

    def _log(msg: str) -> None:
        if logger:
            logger.log(msg)
        else:
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}")

    gc = cliente or criar_cliente_gspread()
    sheet_id = extrair_id_planilha(spreadsheet_url)
    try:
        sh = gc.open_by_key(sheet_id)
    except SpreadsheetNotFound as e:
        raise ConnectionError(
            "Planilha não encontrada ou sem permissão para a conta de serviço."
        ) from e
    except APIError as e:
        raise ConnectionError(f"Erro da API Google ao abrir a planilha: {e}") from e

    ws = sh.sheet1 if not worksheet_title else sh.worksheet(worksheet_title)

    try:
        dados = ws.get_all_values()
    except APIError as e:
        raise ConnectionError(f"Falha ao ler valores da aba '{ws.title}': {e}") from e

    if not dados:
        raise ValueError("A aba da planilha está vazia (sem cabeçalhos).")

    cabecalhos = [str(c).strip() for c in dados[0]]
    norm_to_col: dict[str, int] = {}
    for i, h in enumerate(cabecalhos):
        nh = _normalizar_texto_busca(h)
        if nh and nh not in norm_to_col:
            norm_to_col[nh] = i + 1
    try:
        idx_busca = _indice_coluna_por_nome(cabecalhos, nome_coluna_busca)
    except ValueError as e:
        raise ValueError(str(e)) from e

    linha_idx = _localizar_linha_por_valor(dados, idx_busca, valor_busca)
    if linha_idx is None:
        _log(f"Nenhuma linha com {nome_coluna_busca}={valor_busca!r} na aba '{ws.title}'.")
        return {
            "atualizadas": 0,
            "ignoradas": 0,
            "linha_planilha": None,
            "avisos": ["linha_nao_encontrada"],
        }

    # Índice 1-based para gspread
    row_num = linha_idx + 1

    celulas: list[Cell] = []
    atualizadas = 0
    ignoradas = 0
    avisos: list[str] = []

    for cabecalho, valor_novo in valores.items():
        col_num = norm_to_col.get(_normalizar_texto_busca(cabecalho))
        if not col_num:
            avisos.append(f"cabecalho_ausente:{cabecalho}")
            continue
        atual = dados[linha_idx][col_num - 1] if len(dados[linha_idx]) >= col_num else ""
        if not _celula_considerada_vazia(atual):
            ignoradas += 1
            continue
        if _celula_considerada_vazia(valor_novo):
            continue
        celulas.append(Cell(row=row_num, col=col_num, value=valor_novo))
        atualizadas += 1

    if celulas:
        try:
            ws.update_cells(celulas, value_input_option="USER_ENTERED")
        except APIError as e:
            raise ConnectionError(f"Falha ao gravar células na planilha: {e}") from e

    _log(
        f"Planilha sincronizada (linha {row_num}): {atualizadas} célula(s) preenchida(s), "
        f"{ignoradas} já ocupada(s) preservada(s)."
    )
    return {
        "atualizadas": atualizadas,
        "ignoradas": ignoradas,
        "linha_planilha": row_num,
        "avisos": avisos,
    }


def _valor_de_busca_a_partir_do_registro(
    nome_coluna_busca: str, registro: Mapping[str, Any]
) -> str:
    """
    Obtém o valor usado na coluna de busca a partir do registro interno.

    :param nome_coluna_busca: Nome do cabeçalho na planilha (ex.: ``CPF``, ``MATRÍCULA``).
    :param registro: Dados coletados.
    :return: String de busca (CPF normalizado para dígitos quando aplicável).
    """
    rotulo = _normalizar_texto_busca(nome_coluna_busca)
    if rotulo == "CPF":
        return _somente_digitos(str(registro.get("cpf", "")))
    for chave_interna, titulo in _INTERNAL_TO_SHEET_HEADER.items():
        if _normalizar_texto_busca(titulo) == rotulo:
            return str(registro.get(chave_interna, "")).strip()
    chave_snake = nome_coluna_busca.strip().lower().replace(" ", "_")
    if chave_snake in registro:
        return str(registro[chave_snake]).strip()
    return str(registro.get(nome_coluna_busca, "")).strip()


def sincronizar_lote_na_planilha(
    spreadsheet_url: str,
    nome_coluna_busca: str,
    registros: Sequence[Mapping[str, Any]],
    unidade_sistema: str,
    logger: Optional[Logger] = None,
    worksheet_title: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Executa ``sincronizar_registro_na_planilha`` para cada registro, reutilizando uma única autenticação.

    :param spreadsheet_url: URL da planilha.
    :param nome_coluna_busca: Cabeçalho da coluna de correlação (ex.: ``CPF``).
    :param registros: Lista de dicionários de dados coletados.
    :param unidade_sistema: Sigla da unidade.
    :param logger: Logger opcional.
    :param worksheet_title: Nome da aba ou ``None`` para a primeira.
    :return: Lista com o resumo de cada registro, na mesma ordem.
    """
    gc = criar_cliente_gspread()
    resultados: list[dict[str, Any]] = []
    for r in registros:
        valor = _valor_de_busca_a_partir_do_registro(nome_coluna_busca, r)
        if not str(valor).strip():
            if logger:
                logger.log(
                    f"⏭️ Sincronização ignorada: valor de busca vazio para coluna {nome_coluna_busca!r}."
                )
            resultados.append(
                {
                    "atualizadas": 0,
                    "ignoradas": 0,
                    "linha_planilha": None,
                    "avisos": ["valor_busca_vazio"],
                }
            )
            continue
        res = sincronizar_registro_na_planilha(
            spreadsheet_url=spreadsheet_url,
            nome_coluna_busca=nome_coluna_busca,
            valor_busca=valor,
            registro=r,
            unidade_sistema=unidade_sistema,
            logger=logger,
            worksheet_title=worksheet_title,
            cliente=gc,
        )
        resultados.append(res)
    return resultados


@dataclass
class ColetaSincronizacaoPipeline:
    """
    Orquestra coleta (mesmo fluxo do ``main.py``), log acumulativo e opcional sync com Sheets.

    :ivar logger: Instância de ``Logger`` do projeto.
    :ivar dados_coletados: Lista preenchida após ``executar_coleta`` (espelha o orchestrator).
    :ivar ultimo_caminho_log: Caminho do último arquivo JSONL escrito.
    """

    logger: Logger = field(default_factory=Logger)
    dados_coletados: list[dict[str, Any]] = field(default_factory=list)
    ultimo_caminho_log: Optional[Path] = None

    def executar_coleta(
        self,
        cpfs: Sequence[str],
        modo: str = "completo",
    ) -> list[dict[str, Any]]:
        """
        Executa a coleta via ``ScraperOrchestrator`` (idêntico ao ``main.py``).

        :param cpfs: Lista de CPFs (strings com ou sem máscara).
        :param modo: ``\"completo\"`` chama ``processar_cpfs_completo``; qualquer outro valor usa ``processar_apenas_financeiro``.
        :return: Cópia da lista ``dados_coletados`` produzida pelo orchestrator.
        """
        orch = ScraperOrchestrator()
        # Garante que o orchestrator use o mesmo logger deste pipeline
        orch.logger = self.logger
        lista_cpfs = [str(c).strip() for c in cpfs if str(c).strip()]
        if modo.strip().lower() == "completo":
            orch.processar_cpfs_completo(lista_cpfs)
        else:
            orch.processar_apenas_financeiro(lista_cpfs)
        self.dados_coletados = list(orch.dados_coletados)
        return list(self.dados_coletados)

    def persistir_log_coleta(
        self,
        registros: Optional[Sequence[Mapping[str, Any]]] = None,
        caminho_arquivo: Path | str = _LOG_PADRAO,
    ) -> Path:
        """
        Grava registros no log acumulativo JSONL.

        :param registros: Se ``None``, usa ``self.dados_coletados``.
        :param caminho_arquivo: Destino do JSONL.
        :return: Caminho absoluto do arquivo.
        """
        seq = registros if registros is not None else self.dados_coletados
        self.ultimo_caminho_log = registrar_entradas_log_acumulativo(
            seq, logger=self.logger, caminho_arquivo=caminho_arquivo
        )
        return self.ultimo_caminho_log

    def sincronizar_com_planilha(
        self,
        spreadsheet_url: str,
        nome_coluna_busca: str,
        registros: Optional[Sequence[Mapping[str, Any]]] = None,
        worksheet_title: Optional[str] = None,
        unidade: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Atualiza a planilha para cada registro, preenchendo somente células vazias.

        :param spreadsheet_url: URL da planilha Google.
        :param nome_coluna_busca: Cabeçalho da coluna para localizar a linha.
        :param registros: Se ``None``, usa ``self.dados_coletados``.
        :param worksheet_title: Nome da aba ou ``None`` para a primeira.
        :param unidade: Sigla; se ``None``, lê ``SYSTEM_CHOICE`` do ambiente (como o ``main``).
        :return: Lista de resumos retornados por ``sincronizar_registro_na_planilha``.
        """
        uni = (unidade or os.getenv("SYSTEM_CHOICE", "USJT")).strip().upper()
        seq = registros if registros is not None else self.dados_coletados
        return sincronizar_lote_na_planilha(
            spreadsheet_url=spreadsheet_url,
            nome_coluna_busca=nome_coluna_busca,
            registros=seq,
            unidade_sistema=uni,
            logger=self.logger,
            worksheet_title=worksheet_title,
        )


def _configurar_logging_std() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


if __name__ == "__main__":
    load_dotenv()
    _configurar_logging_std()
    log_std = logging.getLogger("index")

    pipeline = ColetaSincronizacaoPipeline()
    cpfs_env = os.getenv("CPFS", "")
    if not cpfs_env.strip():
        log_std.error("Nenhum CPF encontrado na variável de ambiente CPFS.")
        raise SystemExit(1)

    cpfs = [c.strip() for c in cpfs_env.split(",") if c.strip()]
    modo = os.getenv("COLETA_MODO", "completo")

    try:
        pipeline.executar_coleta(cpfs, modo=modo)
    except Exception as e:  # noqa: BLE001
        pipeline.logger.log(f"✗ Falha na coleta: {e}")
        raise SystemExit(2) from e

    try:
        pipeline.persistir_log_coleta()
    except OSError as e:
        pipeline.logger.log(f"✗ Falha ao persistir log acumulativo: {e}")
        raise SystemExit(3) from e

    url_planilha = os.getenv("SPREADSHEET_URL") or os.getenv("GOOGLE_SHEET_URL", "")
    if url_planilha.strip():
        titulo_aba = os.getenv("SHEET_WORKSHEET_TITLE") or None
        col_busca = os.getenv("SHEET_COLUNA_BUSCA", "CPF")
        try:
            pipeline.sincronizar_com_planilha(
                spreadsheet_url=url_planilha.strip(),
                nome_coluna_busca=col_busca,
                worksheet_title=titulo_aba,
            )
        except (FileNotFoundError, GoogleAuthError, ConnectionError, ValueError) as e:
            pipeline.logger.log(f"✗ Sincronização com planilha abortada: {e}")
            raise SystemExit(4) from e
    else:
        pipeline.logger.log(
            "SPREADSHEET_URL/GOOGLE_SHEET_URL não definidos — pulando sincronização com Google Sheets."
        )
