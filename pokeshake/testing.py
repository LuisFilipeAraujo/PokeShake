"""Dublês de apoio aos testes e ao dry run.

Mora dentro do pacote porque o dry run (`--dry-run`) é funcionalidade do app e
precisa deles, mas nada aqui é usado em operação normal.

O ponto de ter um lugar só: estes dublês imitam contratos externos — a `Session`
do requests, a leitura do mouse, a saída de áudio. Quando o contrato muda, como
quando o download passou a ler em pedaços com teto de tamanho, muda um arquivo
em vez de cinco módulos de teste.
"""
import json

from PyQt6.QtCore import QPoint

import requests

from . import config as cfg
from . import pointer as ptr


class RespostaFalsa:
    """Resposta do requests, no que o download usa de verdade.

    Serve de gerenciador de contexto e entrega o conteúdo em pedaços, como a
    resposta com `stream=True`.
    """

    def __init__(self, status=200, conteudo=b""):
        self.status_code = status
        self.ok = 200 <= status < 300
        self.content = conteudo

    def iter_content(self, tamanho=8192):
        for i in range(0, len(self.content), tamanho):
            yield self.content[i:i + tamanho]

    def json(self):
        return json.loads(self.content)

    def __enter__(self):
        return self

    def __exit__(self, *erro):
        return False


class SessaoFalsa:
    """`Session` do requests que responde por roteiro, sem tocar na rede.

    - `erro`: exceção levantada em toda chamada (rede fora)
    - `resposta`: a mesma resposta para qualquer URL
    - `por_url`: função url -> RespostaFalsa, para casos como "404 no GIF e PNG
      de verdade no mesmo Pokémon"
    """

    headers = {}

    def __init__(self, resposta=None, por_url=None, erro=None):
        self.resposta = resposta
        self.por_url = por_url
        self.erro = erro
        self.chamadas = 0
        self.urls = []

    def get(self, url="", *args, **kwargs):
        self.chamadas += 1
        self.urls.append(url)
        if self.erro is not None:
            raise self.erro
        if self.por_url is not None:
            return self.por_url(url)
        return self.resposta if self.resposta is not None else RespostaFalsa(200, b"")


def sessao_morta():
    """Sem rota para o host, como quem está sem rede."""
    return SessaoFalsa(erro=requests.ConnectionError("sem rota para o host"))


def sessao_com_status(status):
    return SessaoFalsa(resposta=RespostaFalsa(status, b""))


def sessao_com_conteudo(conteudo, status=200):
    return SessaoFalsa(resposta=RespostaFalsa(status, conteudo))


PNG_MINIMO = bytes.fromhex("89504e470d0a1a0a") + b"resto de um png"
OGG_MINIMO = b"OggS\x00\x02" + b"resto de um ogg"
HTML_DE_PORTAL = b"<html><body>Faca login para acessar a internet</body></html>"


class EntradaVirtual:
    """Cursor e botão roteirizados no lugar da leitura do dispositivo."""

    def __init__(self, pos=QPoint(400, 400)):
        self.pos = QPoint(pos)
        self.segurando = False
        self._cursor_real = None
        self._botao_real = None

    def instalar(self):
        self._cursor_real = ptr.ler_cursor
        self._botao_real = ptr.pressionado
        ptr.ler_cursor = lambda: QPoint(self.pos)
        ptr.pressionado = (lambda vk: self.segurando
                           if vk == ptr.VK[cfg.THROW_GESTURE] else False)

    def restaurar(self):
        if self._cursor_real is not None:
            ptr.ler_cursor = self._cursor_real
            ptr.pressionado = self._botao_real

    def mover(self, x, y):
        self.pos = QPoint(int(x), int(y))


class GritosMudos:
    """Registra em vez de tocar: o dry run roda dentro dos testes, e teste não
    pode fazer barulho na máquina de ninguém.

    Dublê fiel de propósito — liga, desliga e respeita o estado como o de
    verdade, senão não serviria para conferir o botão de som.
    """

    def __init__(self, volume=None, ligado=True, parent=None):
        self.tocados = []
        self.ligado = ligado

    def tocar(self, pid):
        if self.ligado:
            self.tocados.append(pid)

    def alternar(self):
        self.ligado = not self.ligado
        return self.ligado
