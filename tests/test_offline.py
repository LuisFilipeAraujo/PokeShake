"""O que o usuário vê quando o download falha.

Sem isso o app fica mudo sem internet: nenhum sprite aparece, nada explica o
motivo, e sacudir o mouse parece defeito.
"""
import threading
import time

import pytest
import requests
from PyQt6.QtGui import QFont, QPainter, QPixmap

from pokeshake import config as cfg
from pokeshake import sprites
from pokeshake.shake import ShakeMode


class SessaoMorta:
    """Sem rota para o host, como quem está sem rede."""

    headers = {}

    def __init__(self):
        self.chamadas = 0

    def get(self, *a, **k):
        self.chamadas += 1
        raise requests.ConnectionError("sem rota para o host")


class SessaoComStatus:
    """Responde sempre com o mesmo status, sem conteúdo útil."""

    headers = {}

    def __init__(self, status):
        self.status = status
        self.chamadas = 0

    def get(self, *a, **k):
        self.chamadas += 1
        sessao = self

        class R:
            status_code = sessao.status
            ok = 200 <= sessao.status < 300
            content = b""
        return R()


@pytest.fixture
def cache_vazio(tmp_path, monkeypatch):
    """Cache em diretório novo: nada vem do disco de verdade.

    O recuo da busca de nomes também é zerado: ele vive em variável de módulo,
    e uma tentativa gasta por outro teste faria o próximo achar que a rede
    continua fora.
    """
    monkeypatch.setattr(cfg, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(sprites, "_names", None)
    monkeypatch.setattr(sprites, "_ultima_tentativa_nomes", 0.0)
    sprites.falhas.limpar()
    yield tmp_path
    sprites.falhas.limpar()


@pytest.fixture
def sem_rede(cache_vazio, monkeypatch):
    sessao = SessaoMorta()
    monkeypatch.setattr(sprites, "_session", sessao)
    return sessao


# ---------------- registro da falha ----------------

def test_falha_de_conexao_fica_registrada(sem_rede):
    data, is_gif = sprites.fetch_pokemon(25)
    assert data is None
    assert sprites.falhas.recente()
    assert "conexão" in sprites.falhas.motivo


def test_pokebola_tambem_registra(sem_rede):
    assert sprites.fetch_ball("poke-ball") is None
    assert sprites.falhas.recente()


class SessaoSemGif:
    """404 no GIF animado (caso real de boa parte da Pokédex) e PNG de verdade."""

    headers = {}
    PNG = bytes.fromhex("89504e470d0a1a0a") + b"resto"

    def get(self, url, *a, **k):
        sem_gif = url.endswith(".gif")
        png = self.PNG

        class R:
            status_code = 404 if sem_gif else 200
            ok = not sem_gif
            content = b"" if sem_gif else png
        return R()


def test_gif_ausente_nao_conta_como_falha(cache_vazio, monkeypatch):
    """A falta do GIF animado é esperada e o PNG cobre: avisar o usuário aqui
    seria mentira."""
    monkeypatch.setattr(sprites, "_session", SessaoSemGif())
    data, is_gif = sprites.fetch_pokemon(25)
    assert data and not is_gif
    assert not sprites.falhas.recente()
    assert (cache_vazio / "25.gif.missing").exists()


def test_png_ausente_nao_ganha_lapide(cache_vazio, monkeypatch):
    """Rede que responde 404 para tudo (sinkhole de DNS, proxy) mataria o
    Pokémon para sempre naquela máquina se a ausência fosse anotada."""
    monkeypatch.setattr(sprites, "_session", SessaoComStatus(404))
    assert sprites.fetch_pokemon(25) == (None, False)
    assert not (cache_vazio / "25.png.missing").exists()
    assert sprites.falhas.recente(), "404 no PNG é a rede mentindo: tem que avisar"


def test_portal_cativo_nao_entra_no_cache(cache_vazio, monkeypatch):
    """Wifi de hotel responde 200 com a página de login. Gravar isso criaria um
    Pokémon invisível permanente, que ainda ocupa vaga e pode ser capturado."""
    class SessaoPortal:
        headers = {}

        def get(self, *a, **k):
            class R:
                status_code = 200
                ok = True
                content = b"<html><body>Faca login</body></html>"
            return R()

    monkeypatch.setattr(sprites, "_session", SessaoPortal())
    assert sprites.fetch_pokemon(25) == (None, False)
    assert not list(cache_vazio.glob("25.*")), "lixo gravado no cache"
    assert sprites.falhas.recente()
    assert "no lugar da imagem" in sprites.falhas.motivo


def test_erro_de_servidor_conta_como_falha(cache_vazio, monkeypatch):
    monkeypatch.setattr(sprites, "_session", SessaoComStatus(503))
    assert sprites.fetch_ball("poke-ball") is None
    assert sprites.falhas.recente()
    assert "503" in sprites.falhas.motivo


def test_offline_nao_marca_sprite_como_ausente(sem_rede, cache_vazio):
    """Marcar ausência numa queda de rede envenenaria o cache: o sprite
    nunca mais seria tentado, mesmo com a internet de volta."""
    sprites.fetch_pokemon(25)
    assert not list(cache_vazio.glob("*.missing"))


def test_download_que_funciona_limpa_o_aviso(cache_vazio, monkeypatch):
    sprites.falhas.registrar("sem conexão")
    assert sprites.falhas.recente()

    class SessaoBoa:
        headers = {}

        def get(self, *a, **k):
            class R:
                status_code = 200
                ok = True
                content = b"\x89PNG conteudo"
            return R()

    monkeypatch.setattr(sprites, "_session", SessaoBoa())
    assert sprites.fetch_ball("poke-ball")
    assert not sprites.falhas.recente()


def test_aviso_expira(cache_vazio):
    sprites.falhas.registrar("sem conexão")
    assert sprites.falhas.recente(janela=10)
    time.sleep(0.05)
    assert not sprites.falhas.recente(janela=0.01)


# ---------------- nomes sem travar a interface ----------------

def test_nome_do_pokemon_nao_toca_a_rede(sem_rede):
    """pokemon_name é chamado da thread da interface no instante da captura:
    um timeout aqui congelaria o overlay no meio da comemoração."""
    inicio = time.perf_counter()
    nome = sprites.pokemon_name(25)
    assert time.perf_counter() - inicio < 0.1
    assert sem_rede.chamadas == 0, "a interface não pode fazer HTTP"
    assert nome == "Pokémon #25"


def test_prefetch_falha_sem_rede(sem_rede):
    assert sprites.prefetch_names() is False


def test_lista_vazia_nao_e_memoizada(sem_rede, cache_vazio, monkeypatch):
    """A sessão que começasse sem internet mostraria "Pokémon #25" para sempre
    se a lista vazia virasse definitiva."""
    assert sprites.pokemon_name(1) == "Pokémon #1"

    class SessaoComNomes:
        headers = {}

        def get(self, *a, **k):
            class R:
                status_code = 200
                ok = True

                def json(self):
                    return {"results": [{"name": "bulbasaur"}, {"name": "ivysaur"}]}
            return R()

    monkeypatch.setattr(sprites, "_session", SessaoComNomes())
    assert sprites.prefetch_names() is True
    assert sprites.pokemon_name(1) == "Bulbasaur"


def test_nome_composto_fica_legivel(cache_vazio, monkeypatch):
    monkeypatch.setattr(sprites, "_names", {"1": "mr-mime"})
    assert sprites.pokemon_name(1) == "Mr Mime"


def test_catch_busca_os_nomes_fora_da_thread_da_interface(catch, pikachu, espera,
                                                          monkeypatch):
    """A busca tem que acontecer na thread de fundo que já baixa o sprite."""
    threads = []
    monkeypatch.setattr(sprites, "prefetch_names",
                        lambda: threads.append(threading.current_thread()) or True)
    catch.silencio_ate = 0.0
    catch.solta_pokemon()
    assert espera(lambda: bool(threads), limite=15)
    assert threads[0] is not threading.main_thread()


# ---------------- aviso na tela ----------------

def test_hud_avisa_que_nao_deu_para_baixar(catch):
    sprites.falhas.registrar("sem conexão")
    try:
        linhas = catch._linhas_hud(time.monotonic())
        assert any("Não consegui baixar" in linha for linha in linhas)
        assert any("sem conexão" in linha for linha in linhas)
    finally:
        sprites.falhas.limpar()


def test_aviso_tem_prioridade_sobre_procurando(catch):
    """Durante o intervalo, dizer "procurando" sem rede seria enganoso."""
    catch.iniciado = time.monotonic() - 100
    catch.silencio_ate = time.monotonic() + 30
    catch.wilds.clear()
    sprites.falhas.registrar("sem conexão")
    try:
        linhas = catch._linhas_hud(time.monotonic())
        assert not any("Procurando" in linha for linha in linhas)
        assert any("Não consegui baixar" in linha for linha in linhas)
    finally:
        sprites.falhas.limpar()


def test_aviso_sai_do_hud_quando_a_rede_volta(catch):
    sprites.falhas.registrar("sem conexão")
    sprites.falhas.limpar()
    linhas = catch._linhas_hud(catch.iniciado + 1)
    assert not any("Não consegui baixar" in linha for linha in linhas)


def test_aviso_cabe_na_area_reservada_do_hud(app, catch):
    """O HUD marca uma faixa fixa de 1000px como suja; texto mais largo que
    isso deixaria rastro na tela."""
    sprites.falhas.registrar("a PokeAPI respondeu 503")
    try:
        pix = QPixmap(10, 10)
        p = QPainter(pix)
        p.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        larguras = [p.fontMetrics().horizontalAdvance(linha) + 28
                    for linha in catch._linhas_hud(time.monotonic())]
        p.end()
        assert max(larguras) <= 1000
    finally:
        sprites.falhas.limpar()


def test_aviso_aparece_desenhado_na_tela(catch, processa):
    """A prova do sintoma: com a tela vazia, ainda tem que haver pixel."""
    sprites.falhas.registrar("sem conexão")
    try:
        catch.wilds.clear()
        catch.ball = None
        catch.step()
        processa(0.3)
        imagem = catch.canvas.grab().toImage()
        area = catch._area_hud()
        opacos = sum(1 for x in range(area.left(), area.right(), 3)
                     for y in range(area.top(), area.bottom(), 2)
                     if imagem.pixelColor(x, y).alpha() > 40)
        assert opacos > 200, f"só {opacos} pixels desenhados: a tela ficou muda"
    finally:
        sprites.falhas.limpar()


# ---------------- aviso no modo Agitada ----------------

def test_modo_agitada_avisa_quando_nao_baixa(app, pointer, sem_rede, espera):
    """Este modo não tem HUD: o aviso tem que sair por outro caminho."""
    modo = ShakeMode(pointer)
    modo.start()
    avisos = []
    modo.download_falhou.connect(avisos.append)
    modo.summon_at_cursor()
    assert espera(lambda: bool(avisos), limite=15)
    modo.stop()
    assert "conexão" in avisos[0]


def test_bandeja_avisa_uma_vez_por_janela(app, entrada, monkeypatch):
    """Sacudir o mouse várias vezes offline não pode virar enxurrada de balões."""
    from pokeshake.app import PokeShake
    poke = PokeShake(app)
    mensagens = []
    monkeypatch.setattr(poke.tray, "showMessage",
                        lambda *a, **k: mensagens.append(a[1]))
    try:
        for _ in range(5):
            poke._download_falhou("sem conexão")
        assert len(mensagens) == 1, f"{len(mensagens)} balões para 5 falhas"

        poke._ultimo_aviso -= cfg.AVISO_FALHA_S + 1      # passou a janela
        poke._download_falhou("sem conexão")
        assert len(mensagens) == 2
    finally:
        poke.cleanup()
        poke.menu.close()
        poke.tray.hide()


# ---------------- o que o aviso diz ----------------

def test_aviso_diz_que_faltou_a_pokebola(sem_rede, catch):
    """Com Pokémon vindos do cache e sem bola, "não consegui baixar o sprite"
    faria o usuário achar que o arremesso quebrou."""
    assert sprites.fetch_ball("poke-ball") is None
    linhas = catch._linhas_hud(time.monotonic())
    assert any("a pokébola" in linha for linha in linhas)


def test_aviso_diz_que_faltou_o_sprite(sem_rede, catch):
    assert sprites.fetch_pokemon(25) == (None, False)
    linhas = catch._linhas_hud(time.monotonic())
    assert any("o sprite" in linha for linha in linhas)


def test_bandeja_mostra_o_problema_na_dica(app, entrada):
    """O balão é transitório e o Windows pode silenciá-lo; a dica do ícone fica."""
    from pokeshake.app import PokeShake
    poke = PokeShake(app)
    try:
        poke._download_falhou("sem conexão")
        assert "Não consegui baixar" in poke.tray.toolTip()
    finally:
        poke.cleanup()
        poke.menu.close()
        poke.tray.hide()


# ---------------- a espera não pode travar o jogo ----------------

def test_aparicao_nao_espera_a_lista_de_nomes(catch, espera, monkeypatch):
    """Buscar o nome antes de entregar o sprite atrasava cada aparição pelo
    timeout da PokeAPI, e os Pokémon chegavam em blocos."""
    liberado = threading.Event()

    def prefetch_lento():
        liberado.wait(6)
        return False

    monkeypatch.setattr(sprites, "prefetch_names", prefetch_lento)
    catch.silencio_ate = 0.0
    catch.solta_pokemon()
    try:
        apareceu = espera(lambda: bool(catch.wilds), limite=4)
    finally:
        liberado.set()
    assert apareceu, "a aparição ficou presa esperando o nome"


def test_nomes_recuam_depois_de_falhar(sem_rede):
    """Sem recuo, cada aparição pagaria o timeout inteiro de novo."""
    assert sprites.prefetch_names() is False
    assert sem_rede.chamadas == 1
    assert sprites.prefetch_names() is False
    assert sem_rede.chamadas == 1


def test_dica_do_gesto_espera_a_primeira_bola(catch, pokebola):
    """Sem rede no arranque, o relógio da dica venceria antes de existir o que
    arremessar, e o usuário nunca saberia qual é o gesto."""
    catch.iniciado = time.monotonic() - 100
    catch.primeira_bola = True
    catch.ball = None
    catch._nasce_bola("poke-ball", pokebola)
    linhas = catch._linhas_hud(time.monotonic())
    assert any(cfg.GESTO_NOME in linha for linha in linhas)


def test_start_pede_uma_bola_so(app, pointer, monkeypatch):
    """start() e o primeiro quadro pediam a bola junto: dois downloads, um no
    lixo — e, sem rede, duas threads em timeout de uma vez."""
    from pokeshake.catch import CatchMode
    modo = CatchMode(pointer)
    pedidos = []
    monkeypatch.setattr(modo, "pede_bola", lambda: pedidos.append(1))
    monkeypatch.setattr(modo, "solta_pokemon", lambda: None)
    modo.start()
    modo.frame.stop()
    modo.spawn.stop()
    modo.step()
    modo.stop()
    assert len(pedidos) == 1
