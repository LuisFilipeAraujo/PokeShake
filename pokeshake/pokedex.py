"""Pokédex: o que já foi capturado, guardado em disco.

Sem isso o contador da caçada zerava a cada execução e capturar não tinha
consequência nenhuma.
"""
import json
import os
from datetime import datetime

from . import config as cfg

VERSAO = 1


class Pokedex:
    """Registro das capturas, em JSON ao lado do cache de sprites.

    Grava a cada captura: fechar o app no meio da sessão não pode custar o
    progresso, e são poucos bytes por vez.
    """

    def __init__(self, caminho=None):
        self.caminho = caminho or cfg.CACHE_DIR / "pokedex.json"
        self.capturas = self._carregar()

    # ---------------- leitura ----------------
    @property
    def especies(self) -> int:
        """Quantos Pokémon diferentes já foram capturados."""
        return len(self.capturas)

    @property
    def total(self) -> int:
        """Quantas capturas no total, contando repetidos."""
        return sum(c.get("vezes", 0) for c in self.capturas.values())

    def tem(self, pid: int) -> bool:
        return str(pid) in self.capturas

    def vezes(self, pid: int) -> int:
        return self.capturas.get(str(pid), {}).get("vezes", 0)

    def lista(self):
        """Capturas em ordem de Pokédex, para a tela de listagem."""
        itens = []
        for chave, dados in self.capturas.items():
            try:
                pid = int(chave)
            except ValueError:
                continue                      # linha estranha no arquivo: ignora
            itens.append({"pid": pid,
                          "nome": dados.get("nome") or f"Pokémon #{pid}",
                          "vezes": dados.get("vezes", 1),
                          "primeira": dados.get("primeira", ""),
                          "ultima": dados.get("ultima", "")})
        return sorted(itens, key=lambda i: i["pid"])

    # ---------------- escrita ----------------
    def registrar(self, pid: int, nome: str) -> bool:
        """Anota uma captura. Devolve True se a espécie é nova na Pokédex."""
        chave = str(pid)
        agora = datetime.now().isoformat(timespec="seconds")
        registro = self.capturas.get(chave)
        novo = registro is None
        if novo:
            self.capturas[chave] = {"nome": nome, "vezes": 1,
                                    "primeira": agora, "ultima": agora}
        else:
            registro["vezes"] = registro.get("vezes", 0) + 1
            registro["ultima"] = agora
            if nome and not nome.startswith("Pokémon #"):
                registro["nome"] = nome       # o nome real pode ter chegado depois
        self._salvar()
        return novo

    # ---------------- disco ----------------
    def _carregar(self) -> dict:
        if not self.caminho.exists():
            return {}
        try:
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
            capturas = dados.get("capturas", {})
            if not isinstance(capturas, dict):
                raise ValueError("formato inesperado")
            return {str(k): v for k, v in capturas.items() if isinstance(v, dict)}
        except (ValueError, OSError, AttributeError):
            # não apaga o que não consegui entender: guarda ao lado e começa
            # limpo, para um arquivo quebrado não derrubar o app
            try:
                os.replace(self.caminho, self.caminho.with_suffix(".json.quebrado"))
            except OSError:
                pass
            return {}

    def _salvar(self):
        """Escreve por arquivo temporário: queda no meio da gravação não pode
        deixar o progresso truncado."""
        dados = {"versao": VERSAO, "capturas": self.capturas}
        temporario = self.caminho.with_suffix(".json.tmp")
        try:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            temporario.write_text(json.dumps(dados, ensure_ascii=False),
                                  encoding="utf-8")
            os.replace(temporario, self.caminho)
        except OSError:
            pass                              # disco cheio não pode matar o jogo
