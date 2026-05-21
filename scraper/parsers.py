from bs4 import BeautifulSoup
import re
from typing import Optional, Tuple

class AcademicParser:
    @staticmethod
    def extrair_dados_pessoais(html):
        soup = BeautifulSoup(html, 'html.parser')
        dados = {}
        
        # Mapeamento de rótulos para campos
        mapeamento = {
            'Matrícula:': 'matricula',
            'Nome:': 'nome',
            'CPF:': 'cpf',
            'Situação:': 'status_matricula',
            'E-mail:': 'email'
        }

        # Busca todas as <td> com classe 'rotulo'
        for td_rotulo in soup.find_all('td', class_='rotulo'):
            texto_rotulo = td_rotulo.get_text(strip=True)
            if texto_rotulo in mapeamento:
                campo = mapeamento[texto_rotulo]
                td_valor = td_rotulo.find_next_sibling('td', class_='descricao')
                if td_valor:
                    dados[campo] = td_valor.get_text(strip=True)
        
        return dados

    @staticmethod
    def extrair_vinculos_academicos(html):
        soup = BeautifulSoup(html, 'html.parser')
        dados = {}
        
        tabela = soup.find('table', class_='tabela_relatorio')
        if not tabela:
            return dados

        # Busca a linha com classe 'celula_lista1'
        tr_dados = tabela.find('tr', class_='celula_lista1')
        if tr_dados:
            celulas = tr_dados.find_all('td')
            if len(celulas) >= 8:
                dados['unidade_vinculos'] = celulas[0].get_text(strip=True)
                dados['curso_vinculos'] = celulas[1].get_text(strip=True)
                dados['situacao_vinculos'] = celulas[2].get_text(strip=True)
                dados['forma_ingresso_vinculos'] = celulas[3].get_text(strip=True)
                dados['data_matricula'] = celulas[4].get_text(strip=True)
                dados['ano_ingresso'] = celulas[5].get_text(strip=True)
                dados['periodo_ingresso'] = celulas[6].get_text(strip=True)
                dados['matriz_curricular'] = celulas[7].get_text(strip=True)

        return dados

    @staticmethod
    def extrair_dados_historico(html):
        soup = BeautifulSoup(html, 'html.parser')
        dados = {
            'rematricula_recente': 'NÃO',
            'data_ultima_rematricula': '',
            'horas_extensao': '0',
            'qtde_horas_complementares': '0'
        }

        # 1. Verificar Rematrícula (baseado na data de confirmação)
        resumo_confirmacao = soup.find('th', string=re.compile(r'Resumo da Confirmação', re.I))
        if resumo_confirmacao:
            tabela = resumo_confirmacao.find_parent('table')
            if tabela:
                # Busca por data no formato DD/MM/YYYY HH:MM:SS
                data_match = re.search(r'(\d{2}/\d{2}/\d{4})', tabela.get_text())
                if data_match:
                    data_str = data_match.group(1)
                    dados['data_ultima_rematricula'] = data_str
                    # Se tiver data de confirmação, consideramos como rematriculado
                    dados['rematricula_recente'] = 'SIM'

        # 2. Horas de Extensão e Complementares
        # Busca todas as <td> com classe 'rotulo'
        for td_rotulo in soup.find_all('td', class_='rotulo'):
            texto = td_rotulo.get_text(strip=True)
            if 'Horas de Extensão' in texto:
                td_valor = td_rotulo.find_next_sibling('td', class_='descricao')
                if td_valor:
                    dados['horas_extensao'] = td_valor.get_text(strip=True)
            elif 'Complementares' in texto and 'Qtde' in texto:
                td_valor = td_rotulo.find_next_sibling('td', class_='descricao')
                if td_valor:
                    dados['qtde_horas_complementares'] = td_valor.get_text(strip=True)

        return dados

    @staticmethod
    def extrair_dados_financeiros(html):
        soup = BeautifulSoup(html, 'html.parser')
        dados = {
            'email_financeiro': '', 
            'celular_financeiro': '',
            'situacao_academica': '',
            'data_matricula_conf': ''
        }
        
        # 1. Extrair email e celular
        # Estratégia: Usar o formulário específico pela Action e pegar a 8ª TR (índice 7)
        form_dados = soup.find('form', action=lambda a: a and 'fichaAcademica.php' in a)
        if form_dados:
            linhas = form_dados.find_all('tr')
            if len(linhas) >= 8:
                tr_celular = linhas[7] # 8ª linha (0-indexed)
                celulas = tr_celular.find_all('td')
                if len(celulas) >= 2:
                    dados['celular_financeiro'] = celulas[1].get_text(strip=True)
                
        # Mantém busca flexível para E-mail caso mude de posição
        for td_rotulo in soup.find_all('td', class_='rotulo'):
            texto_rotulo = td_rotulo.get_text(strip=True)
            if 'E-mail' in texto_rotulo:
                td_valor = td_rotulo.find_next_sibling('td', class_='descricao')
                if td_valor:
                    dados['email_financeiro'] = td_valor.get_text(strip=True)
                    break

        # 2. Extrair Situação
        tabela_vinculos = None
        for tabela in soup.find_all('table', class_='tabela_relatorio'):
            th_titulo = tabela.find('th', class_='titulo_tabela')
            if th_titulo and 'Vínculos Acadêmicos' in th_titulo.text:
                tabela_vinculos = tabela
                break
        
        if tabela_vinculos:
            linha_dados = tabela_vinculos.find('tr', class_='celula_lista1')
            if not linha_dados:
                for tr in tabela_vinculos.find_all('tr'):
                    if tr.find('td', class_='celula_lista1'):
                        linha_dados = tr
                        break
            
            if linha_dados:
                celulas = linha_dados.find_all('td')
                if len(celulas) >= 11:
                    col_situacao = celulas[10]
                    span_situacao = col_situacao.find('span')
                    dados['situacao_academica'] = span_situacao.text.strip() if span_situacao else col_situacao.text.strip()
        
        # 3. Extrair Data de Matrícula (Confirmação)
        tabela_conf = None
        for tabela in soup.find_all('table', class_='tabela_relatorio'):
            th_titulo = tabela.find('th', class_='titulo_tabela')
            if th_titulo and 'Dados de Confirmação de Matrícula' in th_titulo.text:
                tabela_conf = tabela
                break
        
        if tabela_conf:
            # Procurar em todas as linhas a que contém "Matrícula" na 5ª coluna
            for tr in tabela_conf.find_all('tr'):
                celulas = tr.find_all('td')
                if len(celulas) >= 6:
                    tipo_movimentacao = celulas[4].get_text(strip=True)
                    if tipo_movimentacao == "Matrícula":
                        data_hora_conf = celulas[5].get_text(strip=True)
                        # Extrair apenas a data (DD/MM/YYYY)
                        match_data = re.search(r'(\d{2}/\d{2}/\d{4})', data_hora_conf)
                        if match_data:
                            dados['data_matricula_conf'] = match_data.group(1)
                            break

        return dados

    @staticmethod
    def _limpar_nome_disciplina_20261(disciplina_raw: str) -> str:
        if not disciplina_raw:
            return ""
        limpo = re.sub(r"^[A-Z0-9]+\s*-\s*", "", disciplina_raw).strip()
        limpo = re.sub(r"\s*-\s*Curr\..*$", "", limpo, flags=re.IGNORECASE).strip()
        if limpo:
            limpo = re.sub(r"\s*-\s*$", "", limpo).strip()
        return limpo

    @staticmethod
    def _indices_colunas_disciplina_status(tr) -> Optional[Tuple[int, int]]:
        """
        Na linha de cabeçalho, resolve índices das colunas Disciplina e Status.
        Layout legado (poucas colunas): disciplina índice 3, status última coluna.
        """
        tds = tr.find_all("td", recursive=False)
        n = len(tds)
        if n < 4:
            return None
        labels = [
            re.sub(r"\s+", " ", td.get_text(" ", strip=True)).strip() for td in tds
        ]
        idx_status = None
        for j in range(n - 1, -1, -1):
            if labels[j] == "Status":
                idx_status = j
                break
        if idx_status is None:
            idx_status = n - 1
        idx_disciplina = None
        for j, lab in enumerate(labels):
            if "Disciplina" in lab:
                idx_disciplina = j
                break
        if idx_disciplina is None:
            idx_disciplina = 3
        return idx_disciplina, idx_status

    @staticmethod
    def _linha_parece_cabecalho_tabela_notas(tr) -> bool:
        """Evita confundir linha de dados com cabeçalho (ex.: tabela 2026.2 com 12 colunas)."""
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 4:
            return False
        classes0 = tds[0].get("class") or []
        if "coluna_titulo" in classes0:
            return True
        t0 = tds[0].get_text(strip=True)
        t1 = tds[1].get_text(strip=True) if len(tds) > 1 else ""
        if t0 in ("Sem.", "Semestre") and t1 == "Curso":
            return True
        joined = " ".join(td.get_text(" ", strip=True) for td in tds)
        return "Disciplina" in joined and "Status" in joined

    @staticmethod
    def _extrair_disciplinas_de_tabela_notas(tabela) -> str:
        status_aceitos = frozenset({"Matriculado", "Aprovado*"})
        disciplinas: list[str] = []

        alvo = tabela.find("tbody") or tabela
        rows = alvo.find_all("tr", recursive=False)

        idx_disciplina: int | None = None
        idx_status: int | None = None

        for tr in rows:
            tds = tr.find_all("td", recursive=False)
            if len(tds) == 1:
                colspan = int(tds[0].get("colspan", 1) or 1)
                if colspan >= 6:
                    continue

            if idx_disciplina is None:
                if AcademicParser._linha_parece_cabecalho_tabela_notas(tr):
                    pair = AcademicParser._indices_colunas_disciplina_status(tr)
                    if pair:
                        idx_disciplina, idx_status = pair
                continue

            if len(tds) <= max(idx_disciplina, idx_status):
                continue

            status_texto = tds[idx_status].get_text(strip=True)
            if status_texto not in status_aceitos:
                continue

            disciplina_raw = tds[idx_disciplina].get_text(strip=True)
            limpo = AcademicParser._limpar_nome_disciplina_20261(disciplina_raw)
            if limpo:
                disciplinas.append(limpo)

        return " - ".join(disciplinas)

    @staticmethod
    def extrair_disciplinas_20261(html):
        """
        Extrai disciplinas do período letivo (ex.: 2026.1 / 2026.2) com status
        ``Matriculado`` ou ``Aprovado*``.

        Procura, nesta ordem, tabelas ``id="tab_2026120"`` (layout atual com notas /
        12 colunas) e ``id="tab_2026110"`` (layout anterior). Só considera ``<tr>``
        filhos diretos do ``<tbody>`` da tabela principal, para não ler linhas de
        tabelas internas (ex.: totais de créditos).
        """
        soup = BeautifulSoup(html, "html.parser")
        for table_id in ("tab_2026120", "tab_2026110"):
            tabela = soup.find("table", id=table_id)
            if not tabela:
                continue
            texto = AcademicParser._extrair_disciplinas_de_tabela_notas(tabela)
            if texto:
                return texto
        return ""
