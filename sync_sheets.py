import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import time
from datetime import datetime
import os
from dotenv import load_dotenv

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
        "SITUAÇÃO ACADÊMICA": {"coluna_online": 26, "sobrescrever": True}, 
    }
    
    # 2. Configurações de Acesso
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
    except Exception as e:
        print(f"❌ Erro ao carregar credentials.json: {e}")
        return

    # 3. Abrir a Planilha
    spreadsheet_id = "13XnsZ2he2JUhb78DN5S33rOFhy3Kbz1Q388WL3S_63A"
    try:
        sh = client.open_by_key(spreadsheet_id)
        worksheet = sh.worksheet("Planilha1")
    except Exception as e:
        print(f"❌ Erro ao abrir planilha ou aba: {e}")
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