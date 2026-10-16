"""Modo Caçada: arremesso, colisão, captura e o intervalo de expectativa."""
import math
import time

import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication

from pokeshake import config as cfg
from pokeshake import sprites
from pokeshake.catch import Wild


def planta(catch, pikachu, x=900, y=400, pid=25):
    data, is_gif = pikachu
    alvo = Wild(pid, sprites.Sprite(data, is_gif, target_h=cfg.WILD_HEIGHT), QPointF(x, y))
    catch.wilds.append(alvo)
    return alvo


def bola_na_mao(catch, pokebola, x=300, y=400):
    catch.ball = None
    catch._nasce_bola("poke-ball", pokebola)
    catch.ball.pos = QPointF(x, y)
    catch.ball.escala = 1.0
    return catch.ball


def arremessa(catch, pointer, vx, vy, de=None):
    """Solta o gesto com uma velocidade de cursor conhecida."""
    catch.carregando = True
    catch.pressionado_em = catch._cursor() if de is None else QPointF(*de)
    pointer.velocity = lambda: (vx, vy)
    catch._soltou(None)


# ---------------- acerto ----------------

def test_acerto_captura_o_pokemon(catch, pointer, pikachu, pokebola, simula, rapido):
    alvo = planta(catch, pikachu)
    bola = bola_na_mao(catch, pokebola)
    capturas = []
    catch.captured.connect(capturas.append)

    arremessa(catch, pointer, 1400.0, -60.0)
    assert bola.estado == "voando"

    estados = simula(catch, 6.0, ate=lambda: catch.capturados > 0)
    assert "sugando" in estados
    assert "balancando" in estados
    assert catch.capturados == 1
    assert alvo not in catch.wilds
    assert capturas == ["Pikachu"]


def test_captura_gera_comemoracao(catch, pointer, pikachu, pokebola, simula, rapido):
    planta(catch, pikachu)
    bola_na_mao(catch, pokebola)
    arremessa(catch, pointer, 1400.0, -60.0)
    simula(catch, 6.0, ate=lambda: catch.capturados > 0)
    assert catch.particulas, "a captura precisa soltar faíscas"
    assert catch.banners, "a captura precisa anunciar o nome"
    assert "Pikachu" in catch.banners[0]["texto"]


def test_sequencia_de_captura_leva_o_tempo_configurado(catch, pointer, pikachu,
                                                       pokebola, simula):
    """Sem encurtar as animações: sugada + três balançadas têm que caber no
    tempo que a configuração promete."""
    planta(catch, pikachu)
    bola_na_mao(catch, pokebola)
    arremessa(catch, pointer, 2000.0, -40.0)
    inicio = time.monotonic()
    simula(catch, 12.0, ate=lambda: catch.capturados > 0)
    levou = time.monotonic() - inicio
    minimo = cfg.SUCK_S + cfg.WOBBLES * cfg.WOBBLE_S
    assert catch.capturados == 1
    assert minimo <= levou <= minimo + 2.0, f"levou {levou:.1f}s, esperava ~{minimo:.1f}s"


def test_pokemon_capturado_some_da_tela(catch, pointer, pikachu, pokebola, simula, rapido):
    planta(catch, pikachu)
    bola_na_mao(catch, pokebola)
    arremessa(catch, pointer, 1400.0, -60.0)
    simula(catch, 6.0, ate=lambda: not catch.wilds)
    assert not catch.wilds


# ---------------- erro ----------------

def test_erro_nao_captura(catch, pointer, pikachu, pokebola, simula, rapido):
    planta(catch, pikachu, x=1500, y=300)
    bola = bola_na_mao(catch, pokebola, x=300, y=800)
    arremessa(catch, pointer, -1500.0, -200.0)
    simula(catch, 4.0, ate=lambda: bola.estado == "fim")
    assert catch.capturados == 0
    assert bola.estado == "fim", "a bola errada precisa sumir sozinha"


def test_bola_perdida_nao_fica_para_sempre(catch, pointer, pokebola, simula):
    bola_na_mao(catch, pokebola, x=600, y=600)
    arremessa(catch, pointer, 0.0, -2000.0)
    simula(catch, cfg.MISS_TTL + 3, ate=lambda: not catch.voando)
    assert not catch.voando


# ---------------- força e direção ----------------

def test_gesto_fraco_vira_arremesso_minimo(catch, pointer, pokebola):
    bola = bola_na_mao(catch, pokebola, x=600, y=600)
    arremessa(catch, pointer, 5.0, 5.0)
    velocidade = math.hypot(bola.vel.x(), bola.vel.y())
    assert velocidade == pytest.approx(cfg.THROW_SPEED_MIN, abs=1)
    assert bola.vel.y() < 0, "sem direção nenhuma, a bola vai para cima"


def test_arrasto_sem_flick_segue_o_trajeto(catch, pointer, pokebola):
    """Quem arrasta devagar e solta parado ainda arremessa para onde arrastou."""
    bola = bola_na_mao(catch, pokebola, x=600, y=600)
    destino = catch._cursor()
    arremessa(catch, pointer, 0.0, 0.0, de=(destino.x(), destino.y() + 300))
    assert bola.vel.y() < -400
    assert abs(bola.vel.x()) < 1


def test_velocidade_tem_teto(catch, pointer, pokebola):
    """Sem teto, um repelão sumiria com a bola em um quadro."""
    bola = bola_na_mao(catch, pokebola, x=600, y=600)
    arremessa(catch, pointer, 90000.0, 0.0)
    assert math.hypot(bola.vel.x(), bola.vel.y()) <= cfg.THROW_SPEED_MAX + 1


def test_bola_no_maximo_nao_atravessa_o_alvo(catch, pointer, pikachu, pokebola,
                                             simula, rapido):
    """A colisão é checada em passos curtos justamente por causa deste caso."""
    planta(catch, pikachu, x=1000, y=500)
    bola_na_mao(catch, pokebola, x=200, y=500)
    arremessa(catch, pointer, cfg.THROW_SPEED_MAX, 0.0)
    simula(catch, 6.0, ate=lambda: catch.capturados > 0)
    assert catch.capturados == 1


def test_gesto_sem_bola_na_mao_nao_quebra(catch, pointer):
    catch.ball = None
    catch._segurou(None)
    catch._soltou(None)
    assert not catch.voando
    assert not catch.carregando


# ---------------- intervalo depois da captura ----------------

def test_captura_abre_intervalo(catch, pointer, pikachu, pokebola, simula, rapido):
    catch.silencio_ate = 0.0
    planta(catch, pikachu)
    bola_na_mao(catch, pokebola)
    arremessa(catch, pointer, 1400.0, -60.0)
    simula(catch, 6.0, ate=lambda: catch.capturados > 0)

    falta = catch.silencio_ate - time.monotonic()
    assert cfg.PAUSE_MIN - 1 <= falta <= cfg.PAUSE_MAX
    assert catch.spawn.remainingTime() / 1000 >= falta - 0.5, \
        "a próxima aparição foi agendada para dentro do intervalo"


def test_nada_aparece_durante_o_intervalo(catch, pikachu, processa):
    catch.silencio_ate = time.monotonic() + 30
    catch.solta_pokemon()               # força uma tentativa
    processa(2.5)
    assert not catch.wilds


def test_sprite_atrasado_tambem_respeita_o_intervalo(catch, pikachu):
    """O download é assíncrono: um sprite pedido antes pode chegar depois."""
    catch.silencio_ate = time.monotonic() + 30
    data, is_gif = pikachu
    catch._nasce_pokemon(25, data, is_gif)
    assert not catch.wilds


def test_hud_avisa_que_esta_procurando(catch):
    catch.iniciado = time.monotonic() - 100      # passou da dica inicial
    catch.silencio_ate = time.monotonic() + 30
    catch.wilds.clear()
    linhas = catch._linhas_hud(time.monotonic())
    assert any("Procurando" in linha for linha in linhas)


def test_hud_mostra_a_dica_no_comeco(catch):
    linhas = catch._linhas_hud(catch.iniciado + 1)
    assert any(cfg.GESTO_NOME in linha for linha in linhas)


def test_hud_conta_as_capturas(catch):
    catch.capturados = 7
    assert "Capturados: 7" in catch._linhas_hud(time.monotonic())[0]


def test_nada_aparece_no_meio_de_uma_captura(catch, pikachu, pokebola, processa):
    """Um Pokémon novo entrando durante a comemoração estragaria o momento."""
    catch.silencio_ate = 0.0
    bola = bola_na_mao(catch, pokebola)
    bola.alvo = planta(catch, pikachu, x=50, y=50)
    catch.ball = None
    bola.vai_para("balancando", time.monotonic())
    catch.voando.append(bola)
    assert catch._em_captura()

    antes = len(catch.wilds)
    catch.solta_pokemon()
    processa(2.0)
    assert len(catch.wilds) == antes


def test_aparicoes_voltam_depois_do_intervalo(catch, espera):
    catch.silencio_ate = 0.0
    catch.solta_pokemon()
    assert espera(lambda: len(catch.wilds) >= 1, limite=15)


# ---------------- cena e ciclo de vida ----------------

def test_pokemon_nasce_dentro_de_alguma_tela(catch, pikachu):
    data, is_gif = pikachu
    sprite = sprites.Sprite(data, is_gif, target_h=cfg.WILD_HEIGHT)
    origem = catch.canvas.geometry().topLeft()
    telas = [t.geometry() for t in QApplication.screens()]
    for _ in range(20):
        p = catch._lugar_livre(sprite)
        ponto = (int(p.x() + origem.x()), int(p.y() + origem.y()))
        assert any(t.contains(*ponto) for t in telas), f"{ponto} caiu fora dos monitores"
    sprite.stop()


def test_limite_de_pokemon_na_tela(catch, pikachu):
    catch.silencio_ate = 0.0
    data, is_gif = pikachu
    for _ in range(cfg.WILD_MAX + 3):
        catch._nasce_pokemon(25, data, is_gif)
    assert len(catch.wilds) == cfg.WILD_MAX


def test_pokemon_foge_depois_do_tempo(catch, pikachu, monkeypatch):
    monkeypatch.setattr(cfg, "WILD_TTL", 0.05)
    alvo = planta(catch, pikachu)
    time.sleep(0.1)
    alvo.step(time.monotonic(), 0.016)
    assert alvo.estado == "fora"


def test_parar_o_modo_limpa_a_tela(catch):
    catch.stop()
    assert catch.canvas is None
    assert not catch.wilds and not catch.voando and not catch.particulas
    assert catch.ball is None
    catch.start()                       # a fixture vai parar de novo no fim
    catch.frame.stop()
    catch.spawn.stop()


def test_parar_desliga_a_leitura_do_gesto(catch, pointer):
    assert pointer.watch_gesture
    catch.stop()
    assert not pointer.watch_gesture
    catch.start()
    catch.frame.stop()
    catch.spawn.stop()
