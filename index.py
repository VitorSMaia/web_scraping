import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
from datetime import datetime
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv


class WebScraperSistema:
    """
    Classe para fazer web scraping em sistemas acadêmicos
    Busca informações de alunos por CPF e preenche tabela
    """

    # Carrega o arquivo .env
    load_dotenv()
    
    def __init__(self, url_sistema, usuario, senha):
        """
        Inicializa o scraper
        
        Args:
            url_sistema: URL base do sistema
            usuario: Usuário para login
            senha: Senha para login
        """
        self.url_sistema = url_sistema
        self.usuario = usuario
        self.senha = senha
        self.driver = None
        self.dados_coletados = []
        self.log_arquivo = "scraping_log.txt"
        self.debug = True  # Modo debug ativado
        
        self._criar_pasta_resultados()
    
    def _criar_pasta_resultados(self):
        """Cria pasta para salvar resultados"""
        Path("resultados").mkdir(exist_ok=True)
    
    def _log(self, mensagem):
        """Registra mensagem no log e console"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg_formatada = f"[{timestamp}] {mensagem}"
        print(msg_formatada)
        
        with open(f"resultados/{self.log_arquivo}", "a", encoding="utf-8") as f:
            f.write(msg_formatada + "\n")
    
    def inicializar_selenium(self, navegador="chrome"):
        """
        Inicializa o Selenium WebDriver
        
        Args:
            navegador: "firefox", "brave" ou "chrome"
        """
        try:
            self._log(f"Inicializando Selenium com {navegador.upper()}...")
            
            if navegador.lower() == "firefox":
                options = webdriver.FirefoxOptions()
                options.add_argument("--width=1920")
                options.add_argument("--height=1080")
                self.driver = webdriver.Firefox(options=options)
                
            elif navegador.lower() == "brave":
                options = webdriver.ChromeOptions()
                options.binary_location = "/usr/bin/brave-browser"
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("user-agent=Mozilla/5.0")
                self.driver = webdriver.Chrome(options=options)
                
            elif navegador.lower() == "chrome":
                options = webdriver.ChromeOptions()
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("user-agent=Mozilla/5.0")
                self.driver = webdriver.Chrome(options=options)
            
            self._log(f"✓ Selenium inicializado com sucesso ({navegador})")
            return True
        except Exception as e:
            self._log(f"✗ Erro ao inicializar Selenium: {e}")
            return False
    
    def login_selenium(self):
        """Faz login usando Selenium"""
        try:
            self._log(f"Acessando página de login: {self.url_sistema}")
            
            self.driver.get(self.url_sistema)
            time.sleep(2)
            
            self._log("Preenchendo credenciais...")
            
            # Campo de usuário
            campo_usuario = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "login"))
            )
            campo_usuario.send_keys(self.usuario)
            
            # Campo de senha
            campo_senha = self.driver.find_element(By.ID, "senha_ls")
            campo_senha.send_keys(self.senha)
            
            # Botão de login
            botao_login = self.driver.find_element(By.ID, "btnLogin")
            botao_login.click()
            
            time.sleep(3)
            
            self._log("✓ Login realizado com sucesso")
            return True
                
        except Exception as e:
            self._log(f"✗ Erro durante login: {e}")
            return False
    
    def acessar_ficha_academica(self):
        """Acessa a página de ficha acadêmica"""
        try:
            url_ficha = os.getenv('URL_SISTEMA', 'https://polossjt.ead.br') + "/registro_controle_academico/fichaAcademica.php"
            self._log(f"Acessando ficha acadêmica: {url_ficha}")
            
            self.driver.get(url_ficha)
            time.sleep(2)
            
            self._log("✓ Ficha acadêmica carregada")
            return True
        except Exception as e:
            self._log(f"✗ Erro ao acessar ficha acadêmica: {e}")
            return False
    
    def buscar_aluno_por_cpf(self, cpf):
        """Busca aluno por CPF na ficha acadêmica"""
        try:
            self._log(f"Buscando aluno: {cpf}")
            
            # Preencher campo CPF
            campo_cpf = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "pess_cpf"))
            )
            campo_cpf.clear()
            campo_cpf.send_keys(cpf)
            
            time.sleep(1)
            
            # Clicar botão filtrar
            botao_filtrar = self.driver.find_element(By.ID, "btn_filtrar")
            botao_filtrar.click()

            time.sleep(2)

            botao_visualizar = self.driver.find_element(By.ID, "btn_visualizar#0")
            botao_visualizar.click()
            
            time.sleep(2)
            
            self._log(f"✓ Busca realizada para CPF: {cpf}")
            return True
        except Exception as e:
            self._log(f"✗ Erro ao buscar CPF {cpf}: {e}")
            if self.debug:
                import traceback
                self._log(f"[DEBUG] Traceback: {traceback.format_exc()}")
            
            # Adiciona linha vazia no Excel quando cair no catch
            linha_vazia = {i: '' for i in range(22)}
            self.dados_coletados.append(linha_vazia)
            self._log(f"[INFO] Linha vazia adicionada para CPF com erro: {cpf}")
            
            return False
    
    def extrair_dados_ficha_academica(self):
        """Extrai dados adicionais da Ficha Acadêmica/Dados Pessoais do aluno."""
        try:
            from bs4 import BeautifulSoup
            
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            dados = {}
            
            self._log("Extraindo dados da Ficha Acadêmica...")
            
            # 1. Extrair Dados Pessoais
            dados_pessoais = self._extrair_dados_pessoais(soup)
            dados.update(dados_pessoais)
            if self.debug:
                self._log(f"[DEBUG] Após dados pessoais: {len(dados)} campos")
            
            # 2. Extrair Vínculos Acadêmicos da Ficha
            dados_vinculos_ficha = self._extrair_vinculos_academicos_ficha(soup)
            dados.update(dados_vinculos_ficha)
            if self.debug:
                self._log(f"[DEBUG] Após vínculos ficha: {len(dados)} campos")
                self._log(f"[DEBUG] Dados até aqui: unidade='{dados.get('unidade')}', forma_ingresso='{dados.get('forma_ingresso')}', data_matricula='{dados.get('data_matricula')}'")

            # 3. Extrair Confirmação de Matrícula (para status e rematrícula)
            dados_confirmacao = self._extrair_vinculos_academicos(soup)
            
            # Mesclar dados da confirmação, mas não sobrescrever unidade se já existe
            for chave, valor in dados_confirmacao.items():
                # Se a chave for 'data_matricula_confirmacao', usa apenas se 'data_matricula' estiver vazio
                if chave == 'data_matricula_confirmacao':
                    if not dados.get('data_matricula'):
                        dados['data_matricula'] = valor
                else:
                    # Para outras chaves, atualiza normalmente
                    if chave not in dados or not dados[chave]:
                        dados[chave] = valor
            
            if self.debug:
                self._log(f"[DEBUG] Após confirmação matrícula: {len(dados)} campos")
                self._log(f"[DEBUG] Dados finais ficha: {dados}")
         
            self._log(f"✓ Ficha Acadêmica extraída. Matrícula: {dados.get('matricula')}")
            
            return dados
        
        except Exception as e:
            self._log(f"✗ Erro ao extrair Ficha Acadêmica: {e}")
            if self.debug:
                import traceback
                self._log(f"[DEBUG] Traceback: {traceback.format_exc()}")
            return {}

    def _extrair_dados_pessoais(self, soup):
        """Extrai dados pessoais da primeira tabela."""
        dados_pessoais = {}
        
        if self.debug:
            self._log("[DEBUG] Iniciando extração de dados pessoais...")
        
        # Encontrar a tabela que contém os dados pessoais
        tabela_pessoal = soup.find('form', {'id': 'form'})
        
        if not tabela_pessoal:
            if self.debug:
                self._log("[DEBUG] ✗ Form com id='form' não encontrado")
            return dados_pessoais
        
        if self.debug:
            self._log("[DEBUG] ✓ Form encontrado")
        
        mapeamento = {
            'Matrícula:': 'matricula',
            'Nome:': 'nome',
            'Data Nasc:': 'data_nasc',
            'Sexo:': 'sexo',
            'CPF:': 'cpf',
            'RG:': 'rg',
            'E-mail:': 'email',
            'Celular:': 'celular',
            'Forma de Ingresso:': 'forma_ingresso',
            'Carga Horária Exigida:': 'carga_horaria_exigida',
            'Carga Horária Contabilizada:': 'carga_horaria_contabilizada',
            'Curso:': 'curso',
            'Currículo:': 'curriculo',
            'Situação:': 'situacao'
        }
        
        # Procura por todas as linhas com classe rotulo/descricao
        linhas = tabela_pessoal.find_all('tr')
        if self.debug:
            self._log(f"[DEBUG] Total de <tr> encontradas: {len(linhas)}")
        
        contador_campos = 0
        for idx, linha in enumerate(linhas):
            celulas_rotulo = linha.find_all('td', class_='rotulo')
            celulas_descricao = linha.find_all('td', class_='descricao')
            
            if self.debug and (celulas_rotulo or celulas_descricao):
                self._log(f"[DEBUG] Linha {idx}: {len(celulas_rotulo)} rótulos, {len(celulas_descricao)} descrições")
            
            # Processa pares de rótulo e descrição
            for rotulo_td, descricao_td in zip(celulas_rotulo, celulas_descricao):
                # Extrai o texto do rótulo (pode estar em span)
                rotulo_span = rotulo_td.find('span')
                rotulo_texto = rotulo_span.text.strip() if rotulo_span else rotulo_td.text.strip()
                
                # Extrai o texto da descrição
                descricao_span = descricao_td.find('span')
                if descricao_span:
                    descricao_texto = descricao_span.text.strip()
                else:
                    descricao_texto = descricao_td.text.strip()
                
                # Remove quebras de linha
                rotulo_texto = rotulo_texto.replace('\n', '').replace('\r', '')
                descricao_texto = descricao_texto.replace('\n', '').replace('\r', '')

                if rotulo_texto in mapeamento:
                    chave = mapeamento[rotulo_texto]
                    # O CPF vem com formatação, remove os pontos/hifens se houver
                    if chave in ['cpf', 'matricula', 'rg']:
                        dados_pessoais[chave] = descricao_texto.replace('.', '').replace('-', '').replace('/', '')
                    else:
                        dados_pessoais[chave] = descricao_texto
                    
                    if self.debug:
                        self._log(f"[DEBUG] ✓ {rotulo_texto} => {descricao_texto}")
                    
                    contador_campos += 1
        
        if self.debug:
            self._log(f"[DEBUG] Total de campos extraídos: {contador_campos}")
            self._log(f"[DEBUG] Dados pessoais: {dados_pessoais}")
        
        return dados_pessoais

    def _extrair_vinculos_academicos_ficha(self, soup):
        """Extrai dados de Vínculos Acadêmicos da ficha acadêmica."""
        dados_vinculos = {
            'unidade': '',
            'forma_ingresso_vinculos': '',
            'data_matricula': ''
        }
        
        try:
            if self.debug:
                self._log("[DEBUG] Iniciando extração de vínculos acadêmicos...")
            
            # Encontrar a tabela de Vínculos Acadêmicos
            tabelas = soup.find_all('table', {'class': 'tabela_relatorio'})
            if self.debug:
                self._log(f"[DEBUG] Total de tabelas encontradas: {len(tabelas)}")
            
            for idx, tabela in enumerate(tabelas):
                # Verifica se é a tabela de Vínculos Acadêmicos
                titulo_th = tabela.find('th', {'class': 'titulo_tabela'})
                if titulo_th:
                    titulo_texto = titulo_th.text.strip()
                    if self.debug:
                        self._log(f"[DEBUG] Tabela {idx}: '{titulo_texto}'")
                    
                    if 'Vínculos Acadêmicos' in titulo_texto:
                        if self.debug:
                            self._log("[DEBUG] ✓ Tabela de Vínculos Acadêmicos encontrada!")
                        
                        # Encontra a primeira linha de dados
                        linhas = tabela.find_all('tr')
                        if self.debug:
                            self._log(f"[DEBUG] Total de <tr> na tabela: {len(linhas)}")
                        
                        for linha_idx, linha in enumerate(linhas):
                            primeira_celula = linha.find('td', {'class': 'celula_lista1'})
                            if primeira_celula:
                                if self.debug:
                                    self._log(f"[DEBUG] Linha de dados encontrada no índice {linha_idx}")
                                
                                celulas = linha.find_all('td', {'class': 'celula_lista1'})
                                if self.debug:
                                    self._log(f"[DEBUG] Total de células: {len(celulas)}")
                                
                                if len(celulas) >= 9:
                                    # Polo/Unidade (índice 4)
                                    unidade_span = celulas[4].find('span')
                                    if unidade_span:
                                        dados_vinculos['unidade'] = unidade_span.text.strip()
                                        if self.debug:
                                            self._log(f"[DEBUG] Unidade (célula 4): {dados_vinculos['unidade']}")
                                    
                                    # Ingresso/Data Matrícula (índice 7)
                                    # ingresso_span = celulas[7].find('span')
                                    # if ingresso_span:
                                    #     data_ingresso = ingresso_span.text.strip()
                                    #     dados_vinculos['data_matricula'] = data_ingresso.split()[0] if data_ingresso else ''
                                    #     if self.debug:
                                    #         self._log(f"[DEBUG] Data Matrícula (célula 7): {dados_vinculos['data_matricula']}")
                                    
                                    # Forma de Ingresso (índice 8)
                                    forma_ingresso_span = celulas[8].find('span')
                                    if forma_ingresso_span:
                                        dados_vinculos['forma_ingresso_vinculos'] = forma_ingresso_span.text.strip()
                                        if self.debug:
                                            self._log(f"[DEBUG] Forma Ingresso (célula 8): {dados_vinculos['forma_ingresso_vinculos']}")
                                
                                break
                        
                        break
            
            if self.debug:
                self._log(f"[DEBUG] Dados de vínculos extraídos: {dados_vinculos}")
            
            return dados_vinculos
            
        except Exception as e:
            self._log(f"✗ Erro ao extrair vínculos acadêmicos da ficha: {e}")
            if self.debug:
                import traceback
                self._log(f"[DEBUG] Traceback: {traceback.format_exc()}")
            return dados_vinculos
    
    def _extrair_vinculos_academicos(self, soup):
        """Extrai os dados de Matrícula (ingresso) e a Rematrícula MAIS RECENTE."""
    
        # 1. Encontra o span com o texto desejado.
        span_titulo = soup.find('span', string=lambda t: t and 'Dados de Confirmação de Matrícula' in t)
        
        dados_confirmacao = {
            'data_matricula_confirmacao': '',
            'status_matricula': 'Ativo',
            'rematricula_recente': 'Não',
            'data_ultima_rematricula': ''
        }

        if span_titulo:
            try:
                # 2. Localiza o <th> (pai direto do span) e, em seguida, a tabela completa.
                titulo_tabela_th = span_titulo.find_parent('th')
                tabela_confirmacao = titulo_tabela_th.find_parent('table')
                
                if tabela_confirmacao:
                    linhas_dados = tabela_confirmacao.find_all('tr')[2:]
                    
                    todas_confirmacoes = []

                    for linha in linhas_dados: 
                        celulas = linha.find_all('td')
                        
                        if len(celulas) >= 6:
                            data_hora_processamento = celulas[1].text.strip()
                            tipo_evento = celulas[4].text.strip()
                            data_hora_confirmacao_str = celulas[5].text.strip()
                            
                            registro = {
                                'data_hora_processamento': data_hora_processamento,
                                'tipo_evento': tipo_evento,
                                'data_hora_confirmacao': data_hora_confirmacao_str
                            }
                            
                            todas_confirmacoes.append(registro)

                    # 4. Processamento dos dados
                    if todas_confirmacoes:
                        
                        # 4.1. Filtrar e encontrar a Matrícula (geralmente o ingresso)
                        matricula_records = [r for r in todas_confirmacoes if r['tipo_evento'] == 'Matrícula']
                        if matricula_records:
                            # Extrair apenas a data (formato: DD/MM/AAAA HH:MM:SS -> DD/MM/AAAA)
                            data_completa = matricula_records[0]['data_hora_confirmacao']
                            data_matricula_confirmacao = data_completa.split(' ')[0] if data_completa else ''
                            dados_confirmacao['data_matricula_confirmacao'] = data_matricula_confirmacao
                            
                        # 4.2. Filtrar apenas as Rematrículas
                        rematricula_records = [r for r in todas_confirmacoes if r['tipo_evento'] == 'Rematrícula']
                        
                        if rematricula_records:
                            
                            def parse_data_confirmacao(data_str):
                                """Converte a string de data (dd/mm/aaaa HH:MM:SS) em objeto datetime."""
                                try:
                                    return datetime.strptime(data_str, '%d/%m/%Y %H:%M:%S')
                                except ValueError:
                                    return datetime(1900, 1, 1)

                            # Encontra a Rematrícula mais recente usando a chave de ordenação
                            rematricula_recente = max(
                                rematricula_records, 
                                key=lambda r: parse_data_confirmacao(r['data_hora_confirmacao'])
                            )
                            
                            # Atualizar status
                            dados_confirmacao['rematricula_recente'] = 'Sim'
                            data_completa_rematricula = rematricula_recente['data_hora_confirmacao']
                            data_rematricula = data_completa_rematricula.split(' ')[0] if data_completa_rematricula else ''
                            dados_confirmacao['data_ultima_rematricula'] = data_rematricula
                            
            except Exception as e:
                self._log(f"✗ Erro ao extrair dados de confirmação de matrícula: {e}")
                
        return dados_confirmacao
    
    def acessar_historico_academico(self):
        """Acessa a página de histórico acadêmico"""
        try:
            url_historico = os.getenv('URL_SISTEMA', 'https://polossjt.ead.br') + "/registro_controle_academico/consultaHistoricoOficial.php"
            self._log(f"Acessando histórico acadêmico: {url_historico}")
            
            self.driver.get(url_historico)
            time.sleep(2)
            
            self._log("✓ Histórico acadêmico carregado")
            return True
        except Exception as e:
            self._log(f"✗ Erro ao acessar histórico acadêmico: {e}")
            return False
    
    def buscar_aluno_no_historico(self, cpf):
        """Busca aluno no histórico acadêmico"""
        try:
            self._log(f"Buscando aluno no histórico: {cpf}")
            
            # Preencher campo CPF
            campo_cpf = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "pess_cpf"))
            )
            campo_cpf.clear()
            campo_cpf.send_keys(cpf)
            
            time.sleep(1)
            
            # Clicar botão filtrar
            botao_filtrar = self.driver.find_element(By.ID, "btn_filtrar")
            botao_filtrar.click()
            
            time.sleep(2)

            botao_visualizar = self.driver.find_element(By.ID, "btn_visualizar#0")
            botao_visualizar.click()

            time.sleep(2)
            
            self._log(f"✓ Aluno encontrado no histórico: {cpf}")
            return True
        except Exception as e:
            self._log(f"✗ Erro ao buscar no histórico: {e}")
            if self.debug:
                import traceback
                self._log(f"[DEBUG] Traceback: {traceback.format_exc()}")
            return False
    
    def extrair_dados_historico(self):
        """Extrai dados adicionais do histórico acadêmico, focando em Extensão e Componentes Complementares."""
        try:
            from bs4 import BeautifulSoup

            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            dados_finais = {
                'unidade': '',
                'horas_extensao': '0',
                'qtde_horas_complementares': '0',
                'documentos_pendentes': 'Não verificado'
            }

            self._log("Extraindo dados do histórico acadêmico...")

            tabela_historico = soup.find('table', {'id': 'tb-historico'})
            if not tabela_historico:
                self._log("✗ Erro: Tabela 'tb-historico' não encontrada.")
                return dados_finais

            secao_atual = None
            linhas = tabela_historico.find_all('tr')

            for linha in linhas:
                celulas = linha.find_all('td')
                
                # Identificar o título da seção
                if celulas and 'titulo_tabela' in celulas[0].get('class', []):
                    span_titulo = celulas[0].find('span')
                    if span_titulo:
                        titulo = span_titulo.text.strip()
                        if 'COMPLEMENTARES' in titulo:
                            secao_atual = 'COMPLEMENTARES'
                        elif 'EXTENSÃO' in titulo:
                            secao_atual = 'EXTENSÃO'
                        else:
                            secao_atual = None
                    continue

                # Pula linhas de cabeçalho de coluna
                if linha.find('td', {'class': 'coluna_titulo'}):
                    continue

                # 1. Processar linha de dados na seção EXTENSÃO
                if secao_atual == 'EXTENSÃO' and celulas and 'celula_lista1' in celulas[0].get('class', []):
                    
                    if len(celulas) >= 8:
                        try:
                            ch_extensao = celulas[2].text.strip()
                            dados_finais['horas_extensao'] = ch_extensao
                            self._log(f"✓ Horas de extensão extraídas: {ch_extensao}")

                        except IndexError:
                            pass

                # 2. Processar linha de dados na seção Componentes Complementares
                elif secao_atual == 'COMPLEMENTARES' and celulas and 'celula_lista2' in celulas[0].get('class', []):
                    
                    if len(celulas) >= 8:
                        try:
                            ch_aprovada = celulas[3].text.strip()
                            dados_finais['qtde_horas_complementares'] = ch_aprovada
                            self._log(f"✓ Horas complementares extraídas: {ch_aprovada}")
                            
                        except IndexError:
                            pass

            return dados_finais

        except Exception as e:
            self._log(f"✗ Erro ao extrair histórico: {e}")
            return {'unidade': '', 'horas_extensao': '0', 'qtde_horas_complementares': '0', 'documentos_pendentes': 'Não verificado'}
    
    def processar_cpfs(self, lista_cpfs, navegador="chrome"):
        """Processa lista de CPFs em múltiplas páginas"""
        self._log(f"\n{'='*70}")
        self._log(f"INICIANDO PROCESSAMENTO DE {len(lista_cpfs)} CPFs")
        self._log(f"{'='*70}\n")
        
        if not self.inicializar_selenium(navegador):
            return False
        
        if not self.login_selenium():
            self.driver.quit()
            return False
        
        for i, cpf in enumerate(lista_cpfs, 1):
            self._log(f"\n{'─'*70}")
            self._log(f"[{i}/{len(lista_cpfs)}] PROCESSANDO CPF: {cpf}")
            self._log(f"{'─'*70}")
            
            dados_completos = {}
            
            # ========== ETAPA 1: Buscar na Ficha Acadêmica ==========
            self._log(f"\n[ETAPA 1/2] Acessando ficha acadêmica...")
            
            if not self.acessar_ficha_academica():
                self.driver.quit()
                return False
            
            if self.buscar_aluno_por_cpf(cpf):
                dados_ficha = self.extrair_dados_ficha_academica()
                
                if dados_ficha and dados_ficha.get('nome'):
                    dados_completos.update(dados_ficha)
                    self._log(f"✓ Dados da ficha obtidos: {dados_ficha.get('nome')}")
                else:
                    self._log(f"✗ Nenhum dado encontrado na ficha para CPF: {cpf}")
                    time.sleep(1)
                    continue
            else:
                self._log(f"✗ Erro ao buscar na ficha acadêmica")
                time.sleep(1)
                continue
            
            time.sleep(1)
            
            # ========== ETAPA 2: Buscar no Histórico Acadêmico ==========
            self._log(f"\n[ETAPA 2/2] Acessando histórico acadêmico...")
            
            if self.acessar_historico_academico():
                if self.buscar_aluno_no_historico(cpf):
                    dados_historico = self.extrair_dados_historico()
                    dados_completos.update(dados_historico)
                    self._log(f"✓ Dados do histórico obtidos")
                else:
                    self._log(f"⚠ Erro ao buscar no histórico")
            else:
                self._log(f"⚠ Erro ao acessar histórico")
            
            # ========== ADICIONAR DADOS COMPLETOS ==========
            if dados_completos:
                if self.debug:
                    self._log(f"[DEBUG] Dados completos antes de adicionar: {dados_completos}")
                    self._log(f"[DEBUG] Chaves presentes: {list(dados_completos.keys())}")
                
                self.dados_coletados.append(dados_completos)
                self._log(f"\n✓ ALUNO COMPLETO ADICIONADO: {dados_completos.get('nome')}")
                
                if self.debug:
                    self._log(f"[DEBUG] Total de alunos coletados até agora: {len(self.dados_coletados)}")
            else:
                if self.debug:
                    self._log(f"[DEBUG] ✗ dados_completos está vazio ou None")
            
            time.sleep(1)
        
        self.driver.quit()
        self._log(f"\n{'='*70}")
        self._log(f"✓ PROCESSAMENTO CONCLUÍDO!")
        self._log(f"{'='*70}\n")
        return True
    
    def salvar_csv(self, nome_arquivo="alunos_coletados.csv"):
        """Salva dados em CSV com colunas organizadas"""
        try:
            caminho = f"resultados/{nome_arquivo}"
            df = pd.DataFrame(self.dados_coletados)
            
            # Mapeamento de nomes das colunas (0-21)
            nomes_colunas = {
                0: '',                                  # vazio
                1: '',                                  # vazio
                2: 'UNIDADE',                           # unidade
                3: 'FORMA DE INGRESSO',                 # forma_ingresso_vinculos
                4: 'DATA MATRÍCULA',                    # data_matricula
                5: 'MATRÍCULA',                         # matricula
                6: '',                                  # vazio
                7: '',                                  # vazio
                8: '',                                  # vazio
                9: '',                                  # vazio
                10: '',                                 # vazio
                11: '',                                 # vazio
                12: 'STATUS',                           # status_matricula
                13: 'REMATRÍCULADO',                    # rematricula_recente
                14: 'DATA REMATI',                      # data_ultima_rematricula
                15: '',                                 # vazio
                16: 'HORAS DE EXTENSÃO',                # horas_extensao
                17: 'QTDE DE HORAS COMPLEMENTARES',     # qtde_horas_complementares
                18: '',                                 # vazio
                19: '',                                 # vazio
                20: '',                                 # vazio
                21: ''                                  # vazio
            }
            
            dados_reordenados = []
            
            # Adiciona linha de cabeçalho
            linha_cabecalho = {i: nomes_colunas[i] for i in range(22)}
            dados_reordenados.append(linha_cabecalho)
            
            # Adiciona dados
            for _, row in df.iterrows():
                linha = {}
                
                # Posição 0: vazio
                linha[0] = ''
                # Posição 1: vazio
                linha[1] = ''
                # Posição 2: unidade
                linha[2] = 'USJT'
                # Posição 3: forma_ingresso_vinculos
                linha[3] = row.get('forma_ingresso_vinculos', '')
                # Posição 4: data_matricula
                linha[4] = row.get('data_matricula', '')
                # Posição 5: matricula
                linha[5] = row.get('matricula', '')
                # Posição 6: vazio
                linha[6] = ''
                # Posição 7: vazio
                linha[7] = ''
                # Posição 8: vazio
                linha[8] = ''
                # Posição 9: vazio
                linha[9] = ''
                # Posição 10: vazio
                linha[10] = ''
                # Posição 11: vazio
                linha[11] = ''
                # Posição 12: status_matricula
                linha[12] = row.get('status_matricula', '')
                # Posição 13: rematricula_recente
                linha[13] = row.get('rematricula_recente', '')
                # Posição 14: vazio
                linha[14] = row.get('data_ultima_rematricula','')
                # Posição 15: vazio
                linha[15] = ''
                # Posição 16: horas_extensao
                linha[16] = row.get('horas_extensao', '')
                # Posição 17: qtde_horas_complementares
                linha[17] = row.get('qtde_horas_complementares', '')
                # Posição 18: vazio
                linha[18] = ''
                # Posição 19: vazio
                linha[19] = ''
                # Posição 20: vazio
                linha[20] = ''
                # Posição 21: vazio
                linha[21] = ''
                
                dados_reordenados.append(linha)
            
            df_final = pd.DataFrame(dados_reordenados)
            df_final.to_csv(caminho, index=False, header=False, encoding='utf-8')
            self._log(f"✓ Arquivo CSV salvo: {caminho}")
            return caminho
        except Exception as e:
            self._log(f"✗ Erro ao salvar CSV: {e}")
            return None
    
    def salvar_excel(self, nome_arquivo="alunos_coletados.xlsx"):
        """Salva dados em Excel com colunas organizadas"""
        try:
            caminho = f"resultados/{nome_arquivo}"
            df = pd.DataFrame(self.dados_coletados)
            
            # Mapeamento de nomes das colunas (0-21)
            nomes_colunas = {
                0: '',                                  # vazio
                1: '',                                  # vazio
                2: 'UNIDADE',                           # unidade
                3: 'FORMA DE INGRESSO',                 # forma_ingresso_vinculos
                4: 'DATA MATRÍCULA',                    # data_matricula
                5: 'MATRÍCULA',                         # matricula
                6: '',                                  # vazio
                7: '',                                  # vazio
                8: '',                                  # vazio
                9: '',                                  # vazio
                10: '',                                 # vazio
                11: '',                                 # vazio
                12: 'STATUS',                           # status_matricula
                13: 'REMATRÍCULADO',                    # rematricula_recente
                14: '',                                 # vazio
                15: '',                                 # vazio
                16: 'HORAS DE EXTENSÃO',                # horas_extensao
                17: 'QTDE DE HORAS COMPLEMENTARES',     # qtde_horas_complementares
                18: '',                                 # vazio
                19: '',                                 # vazio
                20: '',                                 # vazio
                21: ''                                  # vazio
            }
            
            dados_reordenados = []
            
            # Adiciona linha de cabeçalho
            linha_cabecalho = {i: nomes_colunas[i] for i in range(22)}
            dados_reordenados.append(linha_cabecalho)
            
            # Adiciona dados
            for _, row in df.iterrows():
                linha = {}
                
                # Posição 0: vazio
                linha[0] = ''
                # Posição 1: vazio
                linha[1] = ''
                # Posição 2: unidade
                linha[2] = 'USJT'
                # Posição 3: forma_ingresso_vinculos
                linha[3] = row.get('forma_ingresso_vinculos', '')
                # Posição 4: data_matricula
                linha[4] = row.get('data_matricula', '')
                # Posição 5: matricula
                linha[5] = row.get('matricula', '')
                # Posição 6: vazio
                linha[6] = ''
                # Posição 7: vazio
                linha[7] = ''
                # Posição 8: vazio
                linha[8] = ''
                # Posição 9: vazio
                linha[9] = ''
                # Posição 10: vazio
                linha[10] = ''
                # Posição 11: vazio
                linha[11] = ''
                # Posição 12: status_matricula
                linha[12] = row.get('status_matricula', '')
                # Posição 13: rematricula_recente
                linha[13] = row.get('rematricula_recente', '')
                # Posição 14: vazio
                linha[14] = row.get('data_ultima_rematricula','')
                # Posição 15: vazio
                linha[15] = ''
                # Posição 16: horas_extensao
                linha[16] = row.get('horas_extensao', '')
                # Posição 17: qtde_horas_complementares
                linha[17] = row.get('qtde_horas_complementares', '')
                # Posição 18: vazio
                linha[18] = ''
                # Posição 19: vazio
                linha[19] = ''
                # Posição 20: vazio
                linha[20] = ''
                # Posição 21: vazio
                linha[21] = ''
                
                dados_reordenados.append(linha)
            
            df_final = pd.DataFrame(dados_reordenados)
            df_final.to_excel(caminho, index=False, header=False)
            self._log(f"✓ Arquivo Excel salvo: {caminho}")
            return caminho
        except Exception as e:
            self._log(f"✗ Erro ao salvar Excel: {e}")
            return None
    
    def exibir_resumo(self):
        """Exibe resumo dos dados coletados"""
        self._log(f"\n{'='*70}")
        self._log(f"RESUMO FINAL")
        self._log(f"{'='*70}")
        self._log(f"Total de alunos coletados: {len(self.dados_coletados)}")
        
        if self.dados_coletados:
            df = pd.DataFrame(self.dados_coletados)
            self._log(f"\nPreview dos dados:\n{df.to_string()}")
        
        self._log(f"{'='*70}\n")


# ============= EXEMPLO DE USO =============

if __name__ == "__main__":
    

    
    # Obtém as variáveis de ambiente
    URL_SISTEMA = os.getenv('URL_SISTEMA', 'https://polossjt.ead.br') + "/administracao/paginaInicial.php"
    USUARIO = os.getenv('USUARIO', '')
    SENHA = os.getenv('SENHA', '')
    CPFS_STR = os.getenv('CPFS', '')
    
    # Verifica se as credenciais foram carregadas
    if not USUARIO or not SENHA:
        print("❌ ERRO: USUARIO e SENHA não foram configurados no arquivo .env")
        print("\nCrie um arquivo .env na pasta do projeto com o seguinte conteúdo:")
        print("""
            URL_SISTEMA=https://polossjt.ead.br/administracao/paginaInicial.php
            USUARIO=seu_usuario
            SENHA=sua_senha
            CPFS=33995218806,12345678901,98765432109
        """)
        exit(1)
    
    # Converte a string de CPFs em lista
    if CPFS_STR:
        CPFS = [cpf.strip() for cpf in CPFS_STR.split(',')]
    else:
        print("❌ ERRO: Nenhum CPF foi configurado no arquivo .env")
        print("Configure a variável CPFS como: CPFS=cpf1,cpf2,cpf3")
        exit(1)
    
    print(f"✓ Configurações carregadas do .env")
    print(f"  URL: {URL_SISTEMA}")
    print(f"  Usuário: {USUARIO}")
    print(f"  Total de CPFs: {len(CPFS)}")
    print(f"  CPFs: {', '.join(CPFS)}\n")
    
    
    # Criar scraper
    scraper = WebScraperSistema(URL_SISTEMA, USUARIO, SENHA)
    
    # Processar CPFs
    scraper.processar_cpfs(CPFS, navegador="chrome")
    
    # Salvar resultados
    scraper.salvar_csv()
    scraper.salvar_excel()
    scraper.exibir_resumo()