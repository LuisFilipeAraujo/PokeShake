"""Grito do Pokémon: download, roteamento, silêncio e o ruído do backend.

A suíte não toca som: o que precisa de reprodução de verdade roda com o volume
em zero, que ainda exercita o caminho inteiro do player.
"""
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
import requests

from pokeshake import config as cfg
from pokeshake import sprites
from pokeshake.som import RUIDO_DO_BACKEND, Gritos

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def grito_pikachu():
    if not sprites.fetch_cry(25):
        pytest.skip("sem rede e sem cache para o grito")
    return sprites.arquivo_do_grito(25)


# ---------------- o que é áudio de verdade ----------------

@pytest.mark.parametrize("inicio", [
    b"OggS\x00\x02",                      # Ogg Vorbis, a maioria dos gritos
    bytes.fromhex("fffb94c4") + b"x",     # quadro de MP3 cru (o grito do #25)
    bytes.fromhex("fff39000") + b"x",     # outra variação de quadro de MP3
    b"ID3\x03lixo",                       # MP3 com tag
    b"RIFFxxxxWAVE",                      # WAV
])
def test_formatos_de_audio_aceitos(inicio):
    assert sprites._parece_audio(inicio)


@pytest.mark.parametrize("inicio", [
    b"<html><body>Faca login</body></html>",
    b"",
    b"\x89PNG\r\n",                       # imagem não é grito
])
def test_conteudo_que_nao_e_audio_e_recusado(inicio):
    assert not sprites._parece_audio(inicio)


def test_grito_vem_em_ogg_ou_mp3(grito_pikachu):
    """A extensão é .ogg, mas o conteúdo varia: quem decide é o conteúdo."""
    inicio = grito_pikachu.read_bytes()[:4]
    assert sprites._parece_audio(inicio), inicio.hex()


# ---------------- download sem assustar ----------------

def test_falha_no_grito_nao_vira_aviso_na_tela(cache_vazio, monkeypatch):
    """O som é enfeite: dizer "não consegui baixar" por causa dele assustaria
    sem motivo, e o jogo continua inteiro."""
    class SessaoMorta:
        headers = {}

        def get(self, *a, **k):
            raise requests.ConnectionError("sem rota")

    monkeypatch.setattr(sprites, "_session", SessaoMorta())
    assert sprites.fetch_cry(25) is None
    assert not sprites.falhas.recente(), "falha de grito não pode acender o HUD"


def test_portal_cativo_nao_entra_no_cache_de_audio(cache_vazio, monkeypatch):
    class SessaoPortal:
        headers = {}

        def get(self, *a, **k):
            class R:
                status_code = 200
                ok = True
                content = b"<html>login</html>"
            return R()

    monkeypatch.setattr(sprites, "_session", SessaoPortal())
    assert sprites.fetch_cry(25) is None
    assert sprites.arquivo_do_grito(25) is None


def test_grito_fica_em_cache(cache_vazio, monkeypatch):
    class SessaoComAudio:
        headers = {}

        def get(self, *a, **k):
            class R:
                status_code = 200
                ok = True
                content = b"OggS\x00\x02 conteudo"
            return R()

    monkeypatch.setattr(sprites, "_session", SessaoComAudio())
    assert sprites.fetch_cry(25)
    assert sprites.arquivo_do_grito(25) == cache_vazio / "cry-25.ogg"


def test_sem_cache_nao_ha_arquivo(cache_vazio):
    assert sprites.arquivo_do_grito(25) is None


# ---------------- roteamento, sem tocar nada ----------------

def test_mudo_nao_toca_nem_monta_player(app, monkeypatch):
    tocados = []
    gritos = Gritos(volume=0.0)
    monkeypatch.setattr(gritos, "_toca", lambda c: tocados.append(c))
    gritos.tocar(25)
    assert not tocados
    assert gritos.player is None, "mudo não pode nem inicializar o backend"


def test_grito_em_cache_toca_na_hora(app, grito_pikachu, monkeypatch):
    tocados = []
    gritos = Gritos(volume=0.0, ligado=True)
    monkeypatch.setattr(gritos, "_toca", lambda c: tocados.append(c))
    gritos.tocar(25)
    assert tocados == [grito_pikachu]


def test_sem_cache_baixa_e_toca_depois(app, cache_vazio, espera, monkeypatch):
    class SessaoComAudio:
        headers = {}

        def get(self, *a, **k):
            class R:
                status_code = 200
                ok = True
                content = b"OggS\x00\x02 conteudo"
            return R()

    monkeypatch.setattr(sprites, "_session", SessaoComAudio())
    tocados = []
    gritos = Gritos(volume=0.0, ligado=True)
    monkeypatch.setattr(gritos, "_toca", lambda c: tocados.append(c))
    gritos.tocar(25)
    assert espera(lambda: bool(tocados), limite=10)


def test_grito_atrasado_nao_toca_sozinho(app, grito_pikachu, monkeypatch):
    """Chegar depois da comemoração soaria como um grito solto na mesa."""
    tocados = []
    gritos = Gritos(volume=0.0, ligado=True)
    monkeypatch.setattr(gritos, "_toca", lambda c: tocados.append(c))
    gritos._tocar_baixado(25, time.monotonic() - cfg.CRY_ATRASO_MAX_S - 1)
    assert not tocados


def test_alternar_liga_e_desliga(app, grito_pikachu, monkeypatch):
    tocados = []
    gritos = Gritos(volume=0.0, ligado=True)
    monkeypatch.setattr(gritos, "_toca", lambda c: tocados.append(c))

    assert gritos.alternar() is False
    gritos.tocar(25)
    assert not tocados

    assert gritos.alternar() is True
    gritos.tocar(25)
    assert len(tocados) == 1


def test_volume_zero_comeca_mudo(app):
    assert Gritos(volume=0.0).ligado is False
    assert Gritos(volume=0.4).ligado is True


# ---------------- o player de verdade, em silêncio ----------------

@pytest.fixture
def audio_disponivel(app):
    from PyQt6.QtMultimedia import QMediaDevices
    if QMediaDevices.defaultAudioOutput().isNull():
        pytest.skip("máquina sem saída de áudio")


@pytest.mark.slow
def test_player_toca_o_arquivo_ate_o_fim(app, audio_disponivel, grito_pikachu,
                                         processa):
    """Volume zero ainda exercita decodificação e saída de áudio."""
    gritos = Gritos(volume=0.0, ligado=True)
    gritos.tocar(25)
    assert gritos.player is not None

    estados = []
    gritos.player.mediaStatusChanged.connect(lambda st: estados.append(st.name))
    fim = time.perf_counter() + 8
    while time.perf_counter() < fim and "EndOfMedia" not in estados:
        processa(0.05)
    assert gritos.player.error().name == "NoError", gritos.player.errorString()
    assert "EndOfMedia" in estados, estados


# ---------------- o ruído do backend ----------------

@pytest.mark.parametrize("linha", [
    b"[mp3float @ 000001FE7E4C4700] Could not update timestamps for skipped samples.\n",
    b"[vorbis @ 000001FE7E4C4700] Could not update timestamps for discarded samples.\n",
    b"[hevc_mf @ 0x7f] could not create MFT\n",
])
def test_reconhece_o_ruido_do_backend(linha):
    assert RUIDO_DO_BACKEND.match(linha)


@pytest.mark.parametrize("linha", [
    b"Traceback (most recent call last):\n",
    b'  File "pokeshake/catch.py", line 10, in step\n',
    b"RuntimeError: algo quebrou\n",
    b"PokeShake no ar - Modo Cacada.\n",
])
def test_nao_confunde_mensagem_de_verdade_com_ruido(linha):
    assert not RUIDO_DO_BACKEND.match(linha)


def test_filtro_descarta_ruido_e_preserva_o_resto():
    """Em processo separado: o filtro troca o descritor 2 do processo inteiro.

    Calar o descritor durante a reprodução seria mais simples, mas engoliria um
    traceback que caísse no mesmo instante — e isso mata o app em silêncio.
    """
    codigo = (
        "import os, time\n"
        "from pokeshake.som import filtrar_ruido_do_backend\n"
        "filtrar_ruido_do_backend()\n"
        "os.write(2, b'[mp3float @ 0x1] Could not update timestamps.\\n')\n"
        "os.write(2, b'MENSAGEM DE VERDADE\\n')\n"
        "raise RuntimeError('traceback de verdade')\n"
    )
    proc = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=60)
    assert "MENSAGEM DE VERDADE" in proc.stderr
    assert "traceback de verdade" in proc.stderr
    assert "mp3float" not in proc.stderr, proc.stderr


# ---------------- integração com a captura ----------------

def test_captura_pede_o_grito(catch, arremesso_certeiro, gritos, rapido):
    arremesso_certeiro(catch)
    assert gritos.tocados == [25]


def test_grito_e_baixado_junto_do_sprite(catch, espera, monkeypatch):
    """Pronto antes da captura: buscar na hora atrasaria o som da comemoração."""
    pedidos = []
    monkeypatch.setattr(sprites, "fetch_cry",
                        lambda pid: pedidos.append((pid, threading.current_thread())))
    catch.silencio_ate = 0.0
    catch.solta_pokemon()
    assert espera(lambda: bool(pedidos), limite=15)
    assert pedidos[0][1] is not threading.main_thread(), \
        "download de grito na thread da interface travaria a tela"


# ---------------- menu e bandeja ----------------

def test_menu_mostra_o_estado_do_som(app, processa):
    from pokeshake.menu import OverlayMenu
    menu = OverlayMenu()
    try:
        # "desligado" contém "ligado": a conta tem que ser pelo fim do texto
        menu.marcar_som(True)
        assert menu.botao_som.text().endswith("ligado")
        menu.marcar_som(False)
        assert menu.botao_som.text().endswith("desligado")
    finally:
        menu.close()


def test_alternar_som_pelo_menu(poke, processa):
    antes = poke.gritos.ligado
    poke.menu.botao_som.click()
    processa(0.1)
    assert poke.gritos.ligado is not antes
    assert poke.acao_som.isChecked() is poke.gritos.ligado
    esperado = "ligado" if poke.gritos.ligado else "desligado"
    assert poke.menu.botao_som.text().endswith(esperado)


def test_bandeja_tem_o_som(poke):
    acoes = [a.text() for a in poke.tray.contextMenu().actions() if a.text()]
    assert "Som do grito" in acoes
