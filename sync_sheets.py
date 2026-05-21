import json
import os
import time
from datetime import datetime
from pathlib import Path

import gspread
import pandas as pd
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

_SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
)


def _criar_cliente_gspread():
    """
    Carrega credenciais de conta de serviço (JSON com \"type\": \"service_account\").

    Ordem: GOOGLE_SERVICE_ACCOUNT_FILE, GOOGLE_APPLICATION_CREDENTIALS,
    credentials.json na raiz do projeto.
    """
    candidatos = [
        os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"),
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        str(Path.cwd() / "credentials.json"),
    ]
    path = None
    for c in candidatos:
        if not c:
            continue
        p = Path(c).expanduser()
        if p.is_file():
            path = p
            break
    if path is None:
        raise FileNotFoundError(
            "Nenhum arquivo de credenciais encontrado. Coloque credentials.json na raiz "
            "ou defina GOOGLE_SERVICE_ACCOUNT_FILE / GOOGLE_APPLICATION_CREDENTIALS."
        )
    with path.open(encoding="utf-8") as f:
        info = json.load(f)
    tipo = info.get("type")
    if tipo != "service_account":
        raise ValueError(
            f"O arquivo {path} não é JSON de conta de serviço (campo type={tipo!r}, "
            f"esperado 'service_account'). No Google Cloud: IAM e administração > Contas "
            f"de serviço > sua conta > Chaves > Adicionar chave > JSON. "
            f"Não use o download de 'ID do cliente OAuth' (installed/web)."
        )
    creds = Credentials.from_service_account_file(str(path), scopes=_SCOPES)
    return gspread.authorize(creds)


def _mensagem_excecao(exc: BaseException) -> str:
    """
    Texto legível da exceção. O gspread às vezes faz ``raise PermissionError from APIError``
    sem mensagem na exceção externa; nesse caso usa-se ``__cause__``.
    """
    principal = str(exc).strip()
    if principal:
        return f"{type(exc).__name__}: {principal}"
    causa = getattr(exc, "__cause__", None)
    if causa is not None:
        ctexto = str(causa).strip()
        if ctexto:
            return f"{type(exc).__name__} (detalhe: {type(causa).__name__}): {ctexto}"
        return f"{type(exc).__name__} (detalhe: {type(causa).__name__}): {causa!r}"
    return f"{type(exc).__name__} (sem mensagem)"


def _texto_excecao_cadeia(exc: BaseException) -> str:
    """Concatena str() da exceção e das causas, para buscas em mensagens de ajuda."""
    partes: list[str] = []
    cur: BaseException | None = exc
    while cur is not None and len(partes) < 6:
        partes.append(str(cur))
        cur = getattr(cur, "__cause__", None)
    return " ".join(partes).lower()


def _imprimir_erro_acesso_planilha(exc: BaseException) -> None:
    print(f"❌ Erro ao abrir planilha ou aba: {_mensagem_excecao(exc)}")
    texto = _texto_excecao_cadeia(exc)
    if "invalid_grant" in texto and (
        "iat" in texto or "exp" in texto or "timeframe" in texto or "jwt" in texto
    ):
        print(
            "\n   Causa provável: relógio do sistema fora do horário aceito pelo Google "
            "(token JWT com iat/exp inválidos).\n"
            "   Verifique: timedatectl status  (ideal: \"System clock synchronized: yes\")\n"
            "   Se \"timedatectl set-ntp true\" responder \"NTP not supported\", instale um "
            "cliente NTP, por exemplo:\n"
            "     sudo apt update && sudo apt install -y chrony && sudo systemctl enable --now chrony.service\n"
            "     chronyc tracking   # deve mostrar \"Leap status: Normal\" após alguns segundos\n"
            "   Alternativa: ajuste manualmente data e hora nas configurações do sistema "
            "(painel de data/hora).\n"
        )
    if "403" in texto and (
        "has not been used" in texto
        or "disabled" in texto
        or "sheets.googleapis.com" in texto
    ):
        print(
            "\n   A Google Sheets API está desativada (ou ainda não propagou) no projeto "
            "da conta de serviço. Ative em:\n"
            "   https://console.cloud.google.com/apis/library/sheets.googleapis.com\n"
            "   (selecione o mesmo projeto em que a conta de serviço foi criada), depois "
            "aguarde alguns minutos e tente de novo.\n"
        )
    if "404" in texto or "requested entity was not found" in texto:
        print(
            "\n   Verifique se o ID da planilha está correto e se a planilha foi "
            "compartilhada com o e-mail da conta de serviço (campo client_email no JSON).\n"
        )


def sincronizar_com_google_sheets():
    load_dotenv()
    
    print("🚀 Iniciando sincronização com Google Sheets...")
    
    # 1. MAPEAMENTO DE COLUNAS - Fácil de estender
    # "nome_coluna_csv": {"coluna_online": número_coluna, "sobrescrever": booleano}
    mapa_colunas = {
        "DATA DE ATUALIZAÇÃO": {"coluna_online": 1, "sobrescrever": True},
        "DATA MATRÍCULA": {"coluna_online": 7, "sobrescrever": False},
        "CELULAR": {"coluna_online": 12, "sobrescrever": False},
        "E-MAIL": {"coluna_online": 13, "sobrescrever": False},
        "SITUAÇÃO ACADÊMICA": {"coluna_online": 26, "sobrescrever": False},
        "DISCIPLINAS 2026.1": {"coluna_online": 16, "sobrescrever": True},
    }
    
    # 2. Configurações de Acesso (conta de serviço — google-auth + gspread)
    try:
        client = _criar_cliente_gspread()
    except (FileNotFoundError, ValueError, OSError) as e:
        print(f"❌ Erro ao carregar credenciais Google: {e}")
        return

    # 3. Abrir a Planilha
    spreadsheet_id = "1fxp2MWn1JakeiTuyoyadCen0JPFCrgBslj_-K-EZzo8"
    try:
        sh = client.open_by_key(spreadsheet_id)
        worksheet = sh.worksheet("CAMILA")
    except Exception as e:
        _imprimir_erro_acesso_planilha(e)
        return

    # 4. Ler o CSV gerado
    csv_path = "resultados/alunos_coletados.csv"
    if not os.path.exists(csv_path):
        print(f"❌ Arquivo {csv_path} não encontrado. Rode o scraper primeiro.")
        return
    
    df_coletado = pd.read_csv(csv_path)
    
    # 5. Obter todos os dados atuais da Planilha Online
    dados_online = worksheet.get_all_values()
    
    if not dados_online:
        print("❌ Planilha online está vazia.")
        return

    # --- INSERÇÃO AUTOMÁTICA DA COLUNA A ---
    header = dados_online[0]
    if header[0] != "DATA DE ATUALIZAÇÃO":
        print("⚠️ Coluna 'DATA DE ATUALIZAÇÃO' não encontrada na Coluna A. Inserindo...")
        worksheet.insert_cols([['DATA DE ATUALIZAÇÃO']], 1)
        # Recarregar dados após alteração estrutural
        dados_online = worksheet.get_all_values()
        header = dados_online[0]
        print("✅ Coluna A inserida com sucesso.")

    # 6. Detectar índice do CPF dinamicamente (Baseado no cabeçalho)
    indice_cpf = -1
    for i, col in enumerate(header):
        if str(col).strip().upper() == "CPF":
            indice_cpf = i
            break
    
    if indice_cpf == -1:
        print("❌ Não foi possível encontrar a coluna 'CPF' na planilha online.")
        return
    
    print(f"🔍 Coluna CPF detectada no índice: {indice_cpf} (Coluna {chr(65 + indice_cpf)})")

    # 7. Mapear dinamicamente os índices das outras colunas pelo nome
    indices_online_efetivos = {}
    for coluna_csv, config in mapa_colunas.items():
        encontrou = False
        for i, col_name in enumerate(header):
            if str(col_name).strip().upper() == str(coluna_csv).strip().upper():
                indices_online_efetivos[coluna_csv] = i + 1
                encontrou = True
                break
        
        if not encontrou:
            # Fallback para o índice fixo (ajustado se houve inserção)
            indices_online_efetivos[coluna_csv] = config["coluna_online"]
            print(f"⚠️ Coluna '{coluna_csv}' não encontrada pelo nome. Usando índice padrão: {indices_online_efetivos[coluna_csv]}")
        else:
            print(f"📍 Coluna '{coluna_csv}' mapeada para índice: {indices_online_efetivos[coluna_csv]}")

    # 8. Criar mapeamento de linhas por CPF
    mapeamento_linhas = {}
    for i, linha in enumerate(dados_online):
        if len(linha) > indice_cpf:
            cpf_limpo = str(linha[indice_cpf]).strip().replace('.', '').replace('-', '').replace('/', '')
            if cpf_limpo:
                mapeamento_linhas[cpf_limpo] = i + 1 
    
    # 9. Processar cada linha do CSV
    print(f"📊 Total de registros para processar: {len(df_coletado)}")
    
    sucesso = 0

    for _, row in df_coletado.iterrows():
        cpf_csv = str(row.get('CPF', '')).strip().replace('.', '').replace('-', '').replace('/', '')
        
        if not cpf_csv: 
            continue
        
        if cpf_csv in mapeamento_linhas:
            linha_alvo = mapeamento_linhas[cpf_csv]
            
            try:
                # Atualizar cada coluna conforme o mapeamento detectado
                for coluna_csv, config in mapa_colunas.items():
                    if coluna_csv in row:
                        valor_novo = str(row[coluna_csv]).strip() if pd.notna(row[coluna_csv]) else ""
                        
                        if not valor_novo or valor_novo.lower() == 'nan':
                            continue
                        
                        coluna_online = indices_online_efetivos[coluna_csv]
                        sobrescrever = config["sobrescrever"]
                        
                        # Verificar valor atual na planilha online
                        valor_atual = ""
                        if len(dados_online[linha_alvo - 1]) >= coluna_online:
                            valor_atual = str(dados_online[linha_alvo - 1][coluna_online - 1]).strip()
                        
                        # Aplicar regra de proteção
                        if not valor_atual or sobrescrever:
                            if valor_atual != valor_novo:
                                worksheet.update_cell(linha_alvo, coluna_online, valor_novo)
                                print(f"✅ Linha {linha_alvo}, Coluna {coluna_online} atualizada: {valor_novo}")
                                time.sleep(0.5)
                        else:
                            print(f"⏭️ Linha {linha_alvo}, Coluna {coluna_online}: Célula já preenchida ({valor_atual}), ignorada")
                
                print(f"✅ Registro processado: {cpf_csv}")
                sucesso += 1
                time.sleep(2.0)
                
            except Exception as e:
                print(f"⚠️ Erro ao atualizar registro {cpf_csv}: {e}")
        else:
            print(f"❓ CPF {cpf_csv} não encontrado na Planilha Online.")

    print(f"\n✨ Sincronização concluída! {sucesso} registros processados.")

if __name__ == "__main__":
    sincronizar_com_google_sheets()