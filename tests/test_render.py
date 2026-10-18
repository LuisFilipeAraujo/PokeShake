"""Desenho do modo Caçada: região suja, textos e custo por quadro.

A janela da caçada cobre a área de trabalho inteira e só repinta o que mudou.
Se a região declarada não cobrir tudo que é desenhado, sobra rastro do quadro
anterior na tela do usuário — daí estes testes.
"""
import time

import pytest
from PyQt6.QtCore import QPointF, QRect, QRectF
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication

from pokeshake import config as cfg
from pokeshake import sprites
from pokeshake.catch import Wild


def cena_completa(catch, pikachu, pokebola):
    """Monta uma cena com um exemplar de cada coisa desenhável."""
    data, is_gif = pikachu
    alvo = Wild(25, sprites.Sprite(data, is_gif, target_h=cfg.WILD_HEIGHT),
                QPointF(700, 500))
    catch.wilds.append(alvo)

    catch._nasce_bola("poke-ball", pokebola)
    voando = catch.ball
    voando.escala = 1.0
    voando.pos = QPointF(1000, 300)
    voando.estado = "voando"
    catch.ball = None
    catch.voando.append(voando)

    catch._nasce_bola("ultra-ball", pokebola)
    catch.ball.escala = 1.0
    catch.carregando = True

    catch.particulas.append({"pos": QPointF(1500, 800), "vida": 1.0,
                             "vel": QPointF(0, 0), "cor": QColor(255, 220, 80), "r": 5.0})
    catch.banners.append({"texto": "Gotcha! Charizard foi capturado!",
                          "pos": QPointF(900, 700), "nascido": time.monotonic()})
    return alvo, voando


def test_regiao_cobre_tudo_que_e_desenhado(catch, pikachu, pokebola):
    alvo, voando = cena_completa(catch, pikachu, pokebola)
    regiao = catch._regiao_suja()
    assert regiao.contains(alvo.rect().toRect())
    assert regiao.contains(catch._area_bola(voando))
    assert regiao.contains(catch._area_bola(catch.ball, 190))
    assert regiao.contains(QRect(1495, 795, 10, 10))
    assert regiao.contains(catch._area_hud())


def test_regiao_cobre_a_bola_girando(catch, pokebola):
    """A bola gira: a caixa precisa caber na diagonal do sprite, não no lado."""
    catch._nasce_bola("poke-ball", pokebola)
    bola = catch.ball
    bola.escala = 1.0
    bola.giro = 45
    meia_diagonal = bola.pixmap.width() * 0.7071 / 2
    area = catch._area_bola(bola)
    assert area.width() / 2 >= meia_diagonal


def test_uniao_com_o_quadro_anterior_apaga_o_rastro(catch, pikachu, pokebola):
    _, voando = cena_completa(catch, pikachu, pokebola)
    antes = catch._regiao_suja()
    voando.pos = QPointF(1600, 320)
    depois = catch._regiao_suja()
    antiga = QRect(990, 290, 20, 20)
    assert not depois.contains(antiga), "a posição velha não está mais na região nova"
    assert depois.united(antes).contains(antiga), "a união precisa apagar o rastro"


def test_regiao_cobre_o_banner_mais_comprido(catch):
    """A largura do texto depende da fonte e do DPI da máquina, então a região
    tem que seguir a medida, não um valor fixo."""
    nomes = [sprites.pokemon_name(i) for i in (25, 6, 386, 487, 800, 1017)]
    texto = f"Gotcha! {max(nomes, key=len)} é novo na Pokédex!"
    catch.banners.append({"texto": texto, "pos": QPointF(900, 700),
                          "nascido": time.monotonic()})
    largura = catch.largura_banner(texto)
    # o banner sobe enquanto desaparece: a faixa varrida vai de -120 a -24
    varrido = QRectF(900 - largura / 2, 700 - 120, largura, 96).toRect()
    assert catch._regiao_suja().contains(varrido), f"{texto!r} tem {largura}px"


def test_area_do_hud_cobre_todas_as_caixas(catch):
    """Vale para qualquer número de linhas e qualquer fonte: a área suja é a
    união das caixas que o desenho usa."""
    area = catch._area_hud()
    caixas = catch.caixas_hud(time.monotonic())
    assert caixas
    for texto, caixa in caixas:
        assert area.contains(caixa.toRect()), f"{texto!r} fica fora da região"


def test_canvas_cobre_todos_os_monitores(catch):
    virtual = QApplication.primaryScreen().virtualGeometry()
    assert catch.canvas.geometry() == virtual


def test_um_quadro_desenha_sem_erro(catch, pikachu, pokebola, processa):
    cena_completa(catch, pikachu, pokebola)
    catch.step()
    processa(0.2)
    imagem = catch.canvas.grab().toImage()
    assert imagem.width() > 0


@pytest.mark.slow
def test_custo_de_um_quadro(catch, pikachu, pokebola, processa):
    """Guarda-chuva contra regressão de performance no desenho."""
    cena_completa(catch, pikachu, pokebola)
    tempos = []
    original = catch.canvas.paintEvent

    def medido(event):
        inicio = time.perf_counter()
        original(event)
        tempos.append((time.perf_counter() - inicio) * 1000)

    catch.canvas.paintEvent = medido
    catch.frame.start(cfg.FRAME_MS)
    processa(3.0)
    catch.frame.stop()
    catch.canvas.paintEvent = original

    assert len(tempos) > 60, f"só {len(tempos)} quadros em 3s"
    mediana = sorted(tempos)[len(tempos) // 2]
    assert mediana < 8, f"paint em {mediana:.1f}ms por quadro"


def test_regiao_cobre_a_segunda_linha_do_hud(catch):
    """A segunda linha caía fora da faixa fixa: apareceria cortada, ou só
    quando outra coisa sujasse aquele pedaço da tela."""
    sprites.falhas.registrar("sem conexão")
    try:
        area = catch._area_hud()
        caixas = catch.caixas_hud(time.monotonic())
        assert len(caixas) == 2
        assert area.contains(caixas[-1][1].toRect())
    finally:
        sprites.falhas.limpar()
