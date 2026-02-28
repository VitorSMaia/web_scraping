import pandas as pd
from pathlib import Path
from datetime import datetime

class DataExporter:
    def __init__(self, dados_coletados, unidade='USJT', logger=None):
        self.dados = dados_coletados
        self.unidade = unidade
        self.logger = logger
        self.nomes_colunas = {
            0: 'DATA DE ATUALIZAÇÃO',               # data_atualizacao
            1: 'NOME',                              # nome
            2: 'CPF',                               # cpf
            3: 'UNIDADE',                           # unidade
            4: 'FORMA DE INGRESSO',                 # forma_ingresso_vinculos
            5: 'DATA MATRÍCULA',                    # data_matricula
            6: 'MATRÍCULA',                         # matricula
            7: 'E-MAIL',                            # email
            8: 'CELULAR FINANCEIRO',               # celular_financeiro
            9: 'STATUS',                           # status_matricula
            10: 'REMATRÍCULADO',                    # rematricula_recente
            11: 'DATA REMATI',                      # data_ultima_rematricula
            12: 'HORAS DE EXTENSÃO',                # horas_extensao
            13: 'QTDE DE HORAS COMPLEMENTARES',     # qtde_horas_complementares
            14: 'EMAIL FINANCEIRO',                 # email_financeiro
            15: 'SITUAÇÃO ACADÊMICA',               # situacao_academica
            16: 'MÉTODO DE PROCESSAMENTO'           # metodo_processamento
        }

    def _preparar_dados_reordenados(self):
        df = pd.DataFrame(self.dados)
        dados_reordenados = []
        
        # Adiciona linha de cabeçalho
        linha_cabecalho = {i: self.nomes_colunas[i] for i in range(17)}
        dados_reordenados.append(linha_cabecalho)
        
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        # Adiciona dados seguindo o mapeamento de posições
        for _, row in df.iterrows():
            linha = {
                0: agora,
                1: str(row.get('nome', '')),
                2: str(row.get('cpf', '')),
                3: self.unidade, 
                4: str(row.get('forma_ingresso_vinculos', '')),
                5: str(row.get('data_matricula_conf', row.get('data_matricula', ''))),
                6: str(row.get('matricula', '')),
                7: str(row.get('email', '')),
                8: str(row.get('celular_financeiro', '')),
                9: str(row.get('status_matricula', '')),
                10: str(row.get('rematricula_recente', '')),
                11: str(row.get('data_ultima_rematricula', '')),
                12: str(row.get('horas_extensao', '')),
                13: str(row.get('qtde_horas_complementares', '')),
                14: str(row.get('email_financeiro', '')),
                15: str(row.get('situacao_academica', '')),
                16: str(row.get('metodo_processamento', ''))
            }
            dados_reordenados.append(linha)
        
        return pd.DataFrame(dados_reordenados)

    def salvar_csv(self, nome_arquivo="alunos_coletados.csv"):
        try:
            caminho = Path("resultados") / nome_arquivo
            df_final = self._preparar_dados_reordenados()
            df_final.to_csv(caminho, index=False, header=False, encoding='utf-8')
            if self.logger:
                self.logger.log(f"✓ Arquivo CSV salvo: {caminho}")
            return str(caminho)
        except Exception as e:
            if self.logger:
                self.logger.log(f"✗ Erro ao salvar CSV: {e}")
            return None

    def salvar_excel(self, nome_arquivo="alunos_coletados.xlsx"):
        try:
            caminho = Path("resultados") / nome_arquivo
            df_final = self._preparar_dados_reordenados()
            df_final.to_excel(caminho, index=False, header=False)
            if self.logger:
                self.logger.log(f"✓ Arquivo Excel salvo: {caminho}")
            return str(caminho)
        except Exception as e:
            if self.logger:
                self.logger.log(f"✗ Erro ao salvar Excel: {e}")
            return None
