"""E2E: roda o aplicativo de verdade, como processo separado.

É o teste que mais se parece com usar o programa: sobe `pokeshake_init.py`,
deixa o roteiro do dry run passear pelos dois modos e cobra o código de saída.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]

# o filho escreveria na codificação do console do Windows, que embaralha os
# acentos quando a saída vem por pipe
AMBIENTE = {**os.environ, "PYTHONIOENCODING": "utf-8"}


@pytest.fixture(scope="module")
def dryrun():
    inicio = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-u", "pokeshake_init.py", "--dry-run"],
        cwd=RAIZ, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=180, env=AMBIENTE)
    return proc, time.monotonic() - inicio


def test_dry_run_passa(dryrun):
    proc, _ = dryrun
    if proc.returncode != 0:
        pytest.fail(f"dry run falhou (código {proc.returncode})\n"
                    f"--- saída ---\n{proc.stdout}\n--- erros ---\n{proc.stderr}")


def test_dry_run_nao_pula_passos(dryrun):
    proc, _ = dryrun
    total = sum(1 for linha in proc.stdout.splitlines()
                if linha.strip().startswith(("ok", "FALHA")))
    assert total >= 13, f"só {total} passos executados:\n{proc.stdout}"
    assert f"{total}/{total} passos" in proc.stdout


def test_dry_run_cobre_os_dois_modos(dryrun):
    proc, _ = dryrun
    saida = proc.stdout
    for trecho in ["modo Agitada", "modo Caçada", "captura confirmada",
                   "captura entra na Pokédex", "captura pede o grito",
                   "intervalo de expectativa", "rede cai e o HUD avisa",
                   "Esc volta para pausado"]:
        assert trecho in saida, f"o roteiro não cobriu {trecho!r}"


def test_dry_run_nao_deixa_lixo_no_stderr(dryrun):
    proc, _ = dryrun
    ruido = [linha for linha in proc.stderr.splitlines()
             if linha.strip() and "DeprecationWarning" not in linha]
    assert not ruido, "o app escreveu em stderr:\n" + "\n".join(ruido)


def test_dry_run_termina_em_tempo_razoavel(dryrun):
    _, duracao = dryrun
    assert duracao < 90, f"dry run levou {duracao:.0f}s"


@pytest.mark.parametrize("modo", ["shake", "catch", "off"])
def test_aplicativo_sobe_em_cada_modo(modo):
    """Smoke: o ponto de entrada tem que subir e ficar de pé em qualquer modo."""
    proc = subprocess.Popen(
        [sys.executable, "-u", "pokeshake_init.py", "--mode", modo],
        cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace", env=AMBIENTE)
    try:
        time.sleep(6)
        assert proc.poll() is None, (
            f"o app morreu sozinho no modo {modo}:\n{proc.communicate()[1]}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
