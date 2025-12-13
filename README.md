# 📚 Web Scraper - Sistema Acadêmico EAD

## 🎯 Descrição

Ferramenta automatizada para coleta de dados acadêmicos de alunos em sistemas de Educação a Distância (EAD). O scraper extrai informações detalhadas de fichas acadêmicas e históricos utilizando Selenium e BeautifulSoup, gerando relatórios em CSV e Excel.

## ✨ Características

- 🔐 **Autenticação automática** no sistema acadêmico
- 📋 **Extração de múltiplos dados**: matrícula, CPF, curso, notas, carga horária, status, etc.
- 📊 **Exportação em CSV e Excel** com formatação organizada
- 🔄 **Processamento em lote** de múltiplos CPFs
- 🐛 **Modo Debug detalhado** para diagnóstico de problemas
- ⚙️ **Configuração via `.env`** para segurança das credenciais
- 📝 **Logs completos** de todas as operações
- ⚡ **Tratamento robusto de erros** com linhas em branco para CPFs não encontrados

## 🚀 Funcionalidades

### Dados Coletados
- **Dados Pessoais**: Nome, CPF, RG, Email, Celular, Data de Nascimento
- **Acadêmicos**: Matrícula, Curso, Currículo, Forma de Ingresso
- **Status**: Situação, Rematriculado, Última Rematrícula
- **Carga Horária**: Exigida, Contabilizada, Extensão, Complementares
- **Unidade/Polo**: Informações da unidade de atendimento

### Fontes de Dados
- 📄 **Ficha Acadêmica**: Dados pessoais e vínculos acadêmicos
- 📚 **Histórico Acadêmico**: Disciplinas, extensão e componentes complementares

## 📦 Pré-requisitos

```bash
Python 3.8+
Chrome/Firefox/Brave Browser
```

## 🛠️ Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/web-scraper-ead.git
cd web-scraper-ead

# 2. Crie ambiente virtual
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# 3. Instale dependências
pip install -r requirements.txt
```

## ⚙️ Configuração

Crie um arquivo `.env` na raiz do projeto:

```env
URL_SISTEMA=https://polossjt.ead.br/administracao/paginaInicial.php
USUARIO=seu_usuario
SENHA=sua_senha
CPFS=33995218806,12345678901,98765432109
```

## 🚀 Uso

```bash
python3 index.py
```

## 📊 Saída

Os arquivos gerados em `resultados/`:
- `alunos_coletados.csv` - Dados em CSV
- `alunos_coletados.xlsx` - Dados em Excel (22 colunas organizadas)
- `scraping_log.txt` - Log detalhado de execução

## 🐛 Debug

Para ativar modo debug detalhado:

```python
scraper.debug = True
```

Mostrará passo a passo:
- Busca de elementos HTML
- Extração de dados
- Erros com stack trace completo

## 📋 Estrutura de Saída Excel

| 0 | 1 | 2 | 3 | 4 | 5 | ... | 16 | 17 |
|---|---|---|---|---|---|-----|----|----|
| | | UNIDADE | FORMA DE INGRESSO | DATA MATRÍCULA | MATRÍCULA | ... | HORAS EXTENSÃO | QTDE HORAS COMPLEMENTARES |

## ⚠️ Tratamento de Erros

Quando um CPF não é encontrado ou gera erro:
- Uma linha vazia é adicionada ao Excel
- O scraper continua processando os demais CPFs
- Log detalhado do erro é registrado

## 🔒 Segurança

- Credenciais armazenadas em `.env` (não commitadas)
- Adicione `.env` ao `.gitignore`
- Suporta múltiplos navegadores (Chrome, Firefox, Brave)

## 🤝 Contribuindo

Sugestões e melhorias são bem-vindas!

## 📄 Licença

MIT License

## 📧 Contato

Para dúvidas ou sugestões, abra uma [issue](https://github.com/seu-usuario/web-scraper-ead/issues)

---

**Nota**: Certifique-se de ter as credenciais corretas e permissão de acesso ao sistema antes de usar.
