import os
import time
import re
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import urljoin

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from scraper.logger import Logger
from scraper.driver import WebDriverFactory
from scraper.parsers import AcademicParser
from scraper.exporter import DataExporter

class ScraperOrchestrator:
    def __init__(self):
        load_dotenv()
        self.logger = Logger()
        
        self.system_choice = os.getenv('SYSTEM_CHOICE', 'USJT').upper()
        
        if self.system_choice == "UAM":
            self.url_sistema = os.getenv('URL_SISTEMA_UAM', 'https://polosuam.ead.br').rstrip('/')
            self.usuario = os.getenv('USUARIO_UAM', '')
            self.senha = os.getenv('SENHA_UAM', '')
            self.logger.log("SISTEMA SELECIONADO: UAM")
        else:
            self.url_sistema = os.getenv('URL_SISTEMA', 'https://polossjt.ead.br').rstrip('/')
            self.usuario = os.getenv('USUARIO', '')
            self.senha = os.getenv('SENHA', '')
            self.logger.log("SISTEMA SELECIONADO: USJT")
            
        self.driver = None
        self.dados_coletados = []

    def login(self):
        login_url = f"{self.url_sistema}/administracao/paginaInicial.php"
        self.logger.log(f"Acessando página de login: {login_url}")
        self.driver.get(login_url)
        
        try:
            # Tenta encontrar o campo de login (Pode variar entre usu_login ou login)
            self.logger.log("Preenchendo credenciais...")
            
            user_field = None
            for uid in ["usu_login", "login"]:
                try:
                    user_field = WebDriverWait(self.driver, 10).until(
                        EC.visibility_of_element_located((By.ID, uid))
                    )
                    break
                except: continue
            
            if not user_field:
                raise Exception("Não foi possível encontrar o campo de usuário")

            pass_field = None
            for pid in ["usu_senha", "senha_ls"]:
                try:
                    pass_field = self.driver.find_element(By.ID, pid)
                    break
                except: continue
            
            btn_login = None
            for bid in ["btn_entrar", "btnLogin"]:
                try:
                    btn_login = self.driver.find_element(By.ID, bid)
                    break
                except: continue

            user_field.clear()
            user_field.send_keys(self.usuario)
            pass_field.clear()
            pass_field.send_keys(self.senha)
            btn_login.click()

            # Espera carregar a página inicial (pode ser saudacao_usuario ou apenas a URL)
            self.logger.log("Aguardando carregamento pós-login...")
            time.sleep(3)
            self.logger.log("✓ Login realizado com sucesso")
            return True
        except Exception as e:
            self.logger.log(f"✗ Erro no login: {e}")
            return False

    def _obter_dicionario_base(self, cpf, metodo):
        """Retorna dicionário com todos os campos possíveis inicializados"""
        return {
            'cpf': cpf,
            'nome': '',
            'matricula': '',
            'status_matricula': '',
            'email': '',
            'unidade_vinculos': '',
            'curso_vinculos': '',
            'situacao_vinculos': '',
            'forma_ingresso_vinculos': '',
            'data_matricula': '',
            'ano_ingresso': '',
            'periodo_ingresso': '',
            'matriz_curricular': '',
            'rematricula_recente': 'NÃO',
            'data_ultima_rematricula': '',
            'horas_extensao': '0',
            'qtde_horas_complementares': '0',
            'email_financeiro': '',
            'celular_financeiro': '',
            'situacao_academica': '',
            'data_matricula_conf': '',
            'disciplinas_20261': '',
            'metodo_processamento': metodo
        }

    def processar_cpfs_completo(self, cpfs):
        """Processamento completo: Acadêmico + Financeiro"""
        self.driver = WebDriverFactory.criar_driver("chrome")
        try:
            if not self.login():
                return

            for i, cpf in enumerate(cpfs, 1):
                self.logger.log(f"\n[{i}/{len(cpfs)}] PROCESSANDO COMPLETO CPF: {cpf}")
                dados_aluno = self._obter_dicionario_base(cpf, "COMPLETO")

                # 1. Fluxo Acadêmico (Ficha + Histórico)
                if self._buscar_ficha_academica(cpf):
                    dados_aluno.update(AcademicParser.extrair_dados_pessoais(self.driver.page_source))
                    dados_aluno.update(AcademicParser.extrair_vinculos_academicos(self.driver.page_source))
                    dados_aluno['disciplinas_20261'] = AcademicParser.extrair_disciplinas_20261(self.driver.page_source)

                    if self._ir_para_historico():
                        dados_aluno.update(AcademicParser.extrair_dados_historico(self.driver.page_source))
                    
                    # Extrair disciplinas 2026.1 (disponíveis tanto na Ficha quanto no Histórico)
                
                # 2. Fluxo Financeiro (Email, Celular, Situação, Data Confirmação)
                dados_fin = self._processar_financeiro_individual(cpf)
                
                for k, v in dados_fin.items():
                    if k == 'disciplinas_20261_fallback':
                        if v and not dados_aluno.get('disciplinas_20261'):
                            dados_aluno['disciplinas_20261'] = v
                    elif v:
                        if k in ['email_financeiro', 'celular_financeiro', 'situacao_academica', 'data_matricula_conf']:
                            dados_aluno[k] = v
                        elif not dados_aluno.get(k):
                            dados_aluno[k] = v
                            
                self.dados_coletados.append(dados_aluno)
                self.logger.log(f"✓ Aluno concluído: {dados_aluno.get('nome', 'N/A')}")

            self._finalizar()

        finally:
            if self.driver:
                self.driver.quit()

    def processar_apenas_financeiro(self, cpfs):
        """Processamento otimizado: Apenas dados financeiros"""
        self.driver = WebDriverFactory.criar_driver("chrome")
        try:
            if not self.login():
                return

            for i, cpf in enumerate(cpfs, 1):
                self.logger.log(f"\n[{i}/{len(cpfs)}] FINANCEIRO CPF: {cpf}")
                dados_aluno = self._obter_dicionario_base(cpf, "FINANCEIRO")
                
                dados_fin = self._processar_financeiro_individual(cpf)
                dados_aluno.update(dados_fin)
                
                self.dados_coletados.append(dados_aluno)

            self._finalizar()

        finally:
            if self.driver:
                self.driver.quit()

    def _buscar_ficha_academica(self, cpf):
        try:
            self.driver.get(urljoin(self.url_sistema, "/registro_controle_academico/fichaAcademica.php"))
            input_cpf = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "pess_cpf"))
            )
            input_cpf.clear()
            input_cpf.send_keys(cpf)
            self.driver.find_element(By.ID, "btn_filtrar").click()
            
            btn_visualizar = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "btn_visualizar#0"))
            )
            btn_visualizar.click()
            return True
        except Exception as e:
            self.logger.log(f"✗ Erro ao buscar ficha acadêmica para {cpf}: {e}")
            return False

    def _ir_para_historico(self):
        try:
            btn_historico = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[value='Histórico Acadêmico']"))
            )
            btn_historico.click()
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "tabela_relatorio"))
            )
            return True
        except Exception as e:
            self.logger.log(f"✗ Erro ao ir para histórico: {e}")
            return False

    def _processar_financeiro_individual(self, cpf):
        try:
            url_financeiro = urljoin(self.url_sistema, "/financeiro/fichaFinanceira.php")
            self.logger.log(f"Acessando ficha financeira: {url_financeiro}")
            self.driver.get(url_financeiro)
            time.sleep(2)
            
            self.logger.log(f"Buscando aluno na financeira: {cpf}")
            input_cpf = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.ID, "pess_cpf"))
            )
            input_cpf.clear()
            input_cpf.send_keys(cpf)
            time.sleep(1)
            
            btn_filtrar = self.driver.find_element(By.ID, "btn_filtrar")
            btn_filtrar.click()
            time.sleep(2)
            
            btn_editar = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.ID, "btn_editar#0"))
            )
            btn_editar.click()
            time.sleep(2)

            btn_ficha = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input.BUTTON[value="Ficha Acadêmica"]'))
            )
            
            onclick = btn_ficha.get_attribute('onclick')
            match = re.search(r"window\.open\('([^']+)'", onclick)
            if not match:
                match = re.search(r'window\.open\("([^"]+)"', onclick)
            
            if match:
                url_final = urljoin(self.driver.current_url, match.group(1))
                self.logger.log(f"Acessando URL da ficha diretamente: {url_final}")
                self.driver.get(url_final)
                time.sleep(2)
                
                # Esperar carregar a tabela na ficha
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "tabela_relatorio"))
                )
                
                html_source = self.driver.page_source
                dados_fin = AcademicParser.extrair_dados_financeiros(html_source)
                
                # Tenta extrair disciplinas_20261 e dados acadêmicos usando o HTML da Ficha acessada via Financeiro
                dados_fin['disciplinas_20261_fallback'] = AcademicParser.extrair_disciplinas_20261(html_source)
                
                acad_fallback = AcademicParser.extrair_dados_pessoais(html_source)
                acad_fallback.update(AcademicParser.extrair_vinculos_academicos(html_source))
                
                for k, v in acad_fallback.items():
                    if v:
                        dados_fin[k] = v
                
                return dados_fin
        except Exception as e:
            self.logger.log(f"✗ Erro no fluxo financeiro para {cpf}: {e}")
        
        return {
            'email_financeiro': '', 
            'celular_financeiro': '',
            'situacao_academica': '',
            'data_matricula_conf': ''
        }

    def _finalizar(self):
        exporter = DataExporter(self.dados_coletados, self.system_choice, self.logger)
        exporter.salvar_csv()
        exporter.salvar_excel()
        self.logger.log("\n✓ PROCESSAMENTO CONCLUÍDO!")

if __name__ == "__main__":
    orchestrator = ScraperOrchestrator()
    
    # Exemplo de uso baseado no .env
    cpfs_str = os.getenv('CPFS', '')
    if cpfs_str:
        cpfs = [c.strip() for c in cpfs_str.split(',')]
        orchestrator.processar_cpfs_completo(cpfs)
        # orchestrator.processar_apenas_financeiro(cpfs)
    else:
        print("❌ Nenhum CPF encontrado no .env")
