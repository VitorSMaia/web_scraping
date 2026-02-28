import os
from pathlib import Path
from datetime import datetime

class Logger:
    def __init__(self, log_arquivo="scraping_log.txt"):
        self.pasta_resultados = Path("resultados")
        self.pasta_resultados.mkdir(exist_ok=True)
        self.caminho_log = self.pasta_resultados / log_arquivo

    def log(self, mensagem, exibir=True):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg_formatada = f"[{timestamp}] {mensagem}"
        if exibir:
            print(msg_formatada)
        try:
            with open(self.caminho_log, "a", encoding="utf-8") as f:
                f.write(msg_formatada + "\n")
        except Exception as e:
            print(f"❌ Erro ao escrever no log: {e}")
