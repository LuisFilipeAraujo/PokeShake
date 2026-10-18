"""Peças comuns aos testes.

Os testes rodam contra o Qt de verdade (janelas, timers, event loop), mas nunca
contra o mouse da máquina: a entrada é roteirizada pela mesma costura que o dry
run usa. O único teste que mexe no dispositivo de verdade é opt-in, em
test_pointer.py.
"""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtCore import QPointF                    # noqa: E402
from PyQt6.QtWidgets import QApplication            # noqa: E402

from pokeshake import config as cfg                 # noqa: E402
from pokeshake import sprites                       # noqa: E402
from pokeshake.catch import CatchMode, Wild         # noqa: E402
from pokeshake.dryrun import EntradaVirtual         # noqa: E402
from pokeshake.pointer import Pointer               # noqa: E402
from pokeshake.pokedex import Pokedex                # noqa: E402


@pytest.fixture(scope="session")
def app():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def processa(app):
    """Gira o event loop por alguns segundos."""
    def _processa(segundos):
        fim = time.perf_counter() + segundos
        while time.perf_counter() < fim:
            app.processEvents()
            time.sleep(0.004)
    return _processa


@pytest.fixture
def espera(app):
    """Gira o event loop até a condição valer, ou até estourar o limite."""
    def _espera(condicao, limite=20.0):
        fim = time.perf_counter() + limite
        while time.perf_counter() < fim:
            if condicao():
                return True
            app.processEvents()
            time.sleep(0.01)
        return bool(condicao())
    return _espera


@pytest.fixture
def entrada(app):
    """Cursor e botão roteirizados no lugar do dispositivo."""
    virtual = EntradaVirtual()
    virtual.instalar()
    yield virtual
    virtual.restaurar()


@pytest.fixture
def pointer(app, entrada):
    p = Pointer()
    yield p
    p.timer.stop()


@pytest.fixture
def pokedex(tmp_path):
    """Pokédex isolada: nenhum teste pode mexer no progresso real do usuário."""
    return Pokedex(caminho=tmp_path / "pokedex.json")


@pytest.fixture
def catch(app, pointer, pokedex):
    """Modo caçada ligado, mas sem aparições sorteadas: cada teste monta a cena."""
    modo = CatchMode(pointer, pokedex)
    # o start() solta um Pokémon sorteado; o download chega depois e cairia no
    # meio da cena de outro teste, então a aparição inicial é neutralizada
    modo.solta_pokemon = lambda: None
    modo.start()
    del modo.solta_pokemon
    modo.frame.stop()                       # quem dá os passos é o teste
    modo.spawn.stop()
    modo.silencio_ate = time.monotonic() + 3600
    modo.wilds.clear()
    yield modo
    modo.stop()


@pytest.fixture
def simula(app):
    """Roda a simulação do modo caçada quadro a quadro."""
    def _simula(modo, segundos, ate=None):
        estados = []
        fim = time.perf_counter() + segundos
        while time.perf_counter() < fim:
            modo.step()
            app.processEvents()
            for bola in modo.voando:
                if not estados or estados[-1] != bola.estado:
                    estados.append(bola.estado)
            if ate is not None and ate():
                break
            time.sleep(0.008)
        return estados
    return _simula


@pytest.fixture
def rapido(monkeypatch):
    """Encurta as animações, para a suíte não passar a vida esperando."""
    monkeypatch.setattr(cfg, "SUCK_S", 0.05)
    monkeypatch.setattr(cfg, "WOBBLE_S", 0.05)
    monkeypatch.setattr(cfg, "CELEBRATE_S", 0.1)


@pytest.fixture(scope="session")
def pikachu():
    data, is_gif = sprites.fetch_pokemon(25)
    if not data:
        pytest.skip("sem rede e sem cache para baixar o sprite")
    return data, is_gif


@pytest.fixture(scope="session")
def pokebola():
    data = sprites.fetch_ball("poke-ball")
    if not data:
        pytest.skip("sem rede e sem cache para baixar a pokébola")
    return data


@pytest.fixture
def poke(app, entrada, tmp_path, monkeypatch):
    """App inteiro, com a Pokédex em arquivo descartável."""
    from pokeshake import app as modulo_app
    monkeypatch.setattr(modulo_app, "Pokedex",
                        lambda: Pokedex(caminho=tmp_path / "pokedex.json"))
    instancia = modulo_app.PokeShake(app)
    yield instancia
    instancia.cleanup()
    instancia.pokedex_panel.close()
    instancia.menu.close()
    instancia.tray.hide()


@pytest.fixture
def arremesso_certeiro(pointer, pikachu, pokebola, simula):
    """Planta um alvo, põe a bola na mão e acerta: captura garantida."""
    def _arremesso(modo, pid=25):
        data, is_gif = pikachu
        alvo = Wild(pid, sprites.Sprite(data, is_gif, target_h=cfg.WILD_HEIGHT),
                    QPointF(900, 400))
        modo.wilds.append(alvo)
        modo.ball = None
        modo._nasce_bola("poke-ball", pokebola)
        modo.ball.pos = QPointF(300, 400)
        modo.ball.escala = 1.0
        modo.carregando = True
        modo.pressionado_em = modo._cursor()
        pointer.velocity = lambda: (1400.0, -60.0)
        modo._soltou(None)
        return simula(modo, 6.0, ate=lambda: modo.capturados > 0)
    return _arremesso
