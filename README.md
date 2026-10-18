# PokeShake

[![CI](https://github.com/LuisFilipeAraujo/PokeShake/actions/workflows/ci.yml/badge.svg)](https://github.com/LuisFilipeAraujo/PokeShake/actions/workflows/ci.yml)

Pokémon da [PokeAPI](https://github.com/PokeAPI/sprites) aparecem por cima da
sua área de trabalho. Dois modos de jogo, escolhidos num menu overlay.

## Uso

```bash
pip install -e .                 # ou: pip install -e . -c constraints.txt

pokeshake                        # abre o menu de modos
pokeshake --mode catch           # já começa caçando
pokeshake --mode shake
pokeshake --demo                 # mostra um Pokémon e sai
```

`python pokeshake_init.py` continua funcionando igual, sem instalar nada. As
dependências de execução estão no [pyproject.toml](pyproject.toml) com piso e
teto de versão; [constraints.txt](constraints.txt) tem o conjunto exato já
verificado, para quando você quiser reproduzir o mesmo ambiente.

Para sair: "Sair do PokeShake" no menu, "Sair" no ícone da bandeja, ou Ctrl+C no
terminal. O menu abre clicando no ícone da bandeja e pode ser arrastado pelo
corpo.

## Modos

### Agitada

Sacuda o mouse e um Pokémon aleatório aparece por alguns segundos, sobe e some.

A detecção lê a posição do cursor a cada 16 ms numa janela de 0,6 s e conta
quantas vezes o movimento horizontal inverte de sentido, exigindo pelo menos
40 px de trecho a cada inversão — assim um movimento normal de mouse nunca
dispara.

### Caçada

Pokémon vão aparecendo sozinhos pela tela e ficam por 30 segundos antes de
fugir. Uma pokébola aleatória (entre as 15 variedades da PokeAPI) fica na sua
mão, junto ao cursor.

**Segure a roda do mouse e arremesse** na direção do Pokémon. Enquanto segura, a
bola recua no sentido contrário ao movimento — como quem toma impulso — e uma
linha tracejada mostra para onde ela vai sair. Ao soltar, a direção e a força
vêm da velocidade do cursor nos últimos 140 ms; se você soltar parado, vale o
trajeto desde onde começou a segurar.

Acertou, capturou: o Pokémon é sugado para dentro da bola, ela balança três
vezes e a captura é confirmada com faíscas, o nome dele na tela e o **grito do
Pokémon**. `Esc` sai do modo.

O grito vem do repositório [PokeAPI/cries](https://github.com/PokeAPI/cries) e é
baixado junto com o sprite, quando o Pokémon aparece — na hora da captura o som
sai na mesma hora, sem esperar download. Para silenciar, use **Som do grito** no
menu ou no ícone da bandeja; o volume inicial está em `CRY_VOLUME`.

### Pokédex

Cada captura é gravada em `~/.poke_shake_cache/pokedex.json`, então o progresso
sobrevive ao fechamento — o HUD mostra `Capturados: 3 · Pokédex: 47/1025`, e
espécie nova ganha banner próprio ("é novo na Pokédex!"). O botão **Pokédex** no
menu (ou no ícone da bandeja) abre a lista do que você já pegou, com as
miniaturas, o nome, quantas vezes e a data da primeira captura.

A tela monta as miniaturas só a partir do cache de sprites, sem baixar nada:
abrir com dezenas de Pokémon travaria a interface. A gravação é por arquivo
temporário trocado no lugar, para uma queda no meio da escrita não truncar o
progresso, e um arquivo ilegível é preservado como `.quebrado` em vez de
apagado.

Depois de cada captura a mata fica quieta por 6 a 12 segundos, para a próxima
aparição valer expectativa em vez de virar fila. Nada aparece durante a
animação da captura, e o HUD avisa que está procurando o próximo. A faixa está
em `PAUSE_MIN` / `PAUSE_MAX`.

Nada é interceptado: o estado do botão é lido por consulta
(`GetAsyncKeyState`), sem hook global, e só o botão configurado é consultado.
Como o clique da roda não é suprimido, ele continua chegando ao programa que
estiver embaixo do cursor — em navegador, isso liga o autoscroll. Para trocar o
gesto, mude `THROW_GESTURE` em [pokeshake/config.py](pokeshake/config.py) para
`ctrl`, `shift`, `alt` ou `right`.

## Estrutura

| Arquivo | Papel |
|---|---|
| [pokeshake_init.py](pokeshake_init.py) | ponto de entrada |
| [pyproject.toml](pyproject.toml) | metadados, dependências e configuração de teste |
| [pokeshake/config.py](pokeshake/config.py) | todas as constantes de ajuste |
| [pokeshake/sprites.py](pokeshake/sprites.py) | download, cache em disco e preparo dos sprites |
| [pokeshake/pointer.py](pokeshake/pointer.py) | leitura do cursor e do gesto, sem hooks |
| [pokeshake/shake.py](pokeshake/shake.py) | modo Agitada |
| [pokeshake/catch.py](pokeshake/catch.py) | modo Caçada: física, colisão e captura |
| [pokeshake/pokedex.py](pokeshake/pokedex.py) | registro das capturas em disco |
| [pokeshake/som.py](pokeshake/som.py) | grito na captura e o filtro de ruído do backend |
| [pokeshake/menu.py](pokeshake/menu.py) | menu overlay, tela da Pokédex e ícone da bandeja |
| [pokeshake/app.py](pokeshake/app.py) | bandeja e troca de modos |
| [pokeshake/testing.py](pokeshake/testing.py) | dublês de rede, de mouse e de som, usados pelos testes e pelo dry run |

Os sprites ficam em `~/.poke_shake_cache`, então cada Pokémon só é baixado uma
vez; IDs sem GIF animado são anotados para não repetir o 404. Os nomes vêm da
PokeAPI numa única chamada, também em cache. A Pokédex fica no mesmo lugar, em
`pokedex.json`.

## Detalhes de implementação

- **Overlay**: no modo Agitada, cada sprite é uma janela sem borda, sempre no
  topo e transparente a cliques. No modo Caçada é uma única janela do tamanho da
  área de trabalho inteira, o que simplifica colisão e ordem de desenho.
- **Custo**: essa janela grande recomporia dezenas de MB por segundo se fosse
  repintada inteira a 60 fps, então só a região que mudou (neste quadro e no
  anterior) é marcada como suja. Medido em 2 monitores (3120x1920): 62 fps,
  ~13% de um núcleo caçando, ~2% parado.
- **Coordenadas**: a posição vem do próprio Qt, então a escala de tela do
  Windows (125%, 150%) não desloca os sprites.
- **Som**: os gritos chegam com extensão `.ogg`, mas o conteúdo é Ogg Vorbis em
  alguns Pokémon e MP3 em outros — quem decide é o conteúdo, e o backend FFmpeg
  do Qt toca os dois. Esse backend escreve uma ou duas linhas direto no stderr a
  cada decodificação ("[mp3float @ 0x…] Could not update timestamps"), fora do
  log do Qt, então nenhuma variável de ambiente as cala. O stderr é desviado por
  um cano que descarta só as linhas nesse formato e repassa todo o resto; um
  traceback que escape de um slot vai direto ao descritor original, porque o
  PyQt aborta o processo em seguida e a mensagem morreria no cano.
- **Sem internet**: o app avisa em vez de ficar mudo. No modo Caçada, uma linha
  no HUD diz o que falhou e qual sprite faltou — "o sprite" ou "a pokébola",
  porque não ter bola na mão se parece com arremesso quebrado. No modo Agitada,
  que não tem HUD, o aviso sai num balão da bandeja (no máximo um por 12 s),
  mais a dica do ícone, que fica: o balão é transitório e o Windows pode
  silenciá-lo. A tentativa se repete a cada aparição, então o jogo volta sozinho
  quando a rede volta.
- **Rede que mente**: wifi de hotel responde 200 com a página de login, e
  gravar isso no cache criaria um Pokémon invisível permanente — que ainda
  ocuparia vaga e poderia ser "capturado". Só entra no cache o que começa com
  cabeçalho de PNG ou de GIF. Na mesma linha, só o GIF animado pode ser anotado
  como ausente: todo ID da Pokédex tem PNG, então 404 nele é a rede mentindo, e
  anotar mataria aquele Pokémon para sempre naquela máquina.
- **Nomes**: nunca são buscados na thread da interface. `pokemon_name` só lê
  memória e disco; quem faz rede é o `prefetch_names`, chamado da thread de
  fundo que baixa o sprite, depois de entregá-lo. Buscar na hora da captura
  congelaria o overlay pelo timeout; buscar antes de entregar atrasaria cada
  aparição pelo mesmo tempo. Lista vazia nunca é definitiva, e uma falha recua
  60 s antes de nova tentativa.

## Qualidade

```bash
pip install -e ".[dev]"

pytest                                # suíte inteira, ~1 min
pytest -m "not slow"                  # sem os que dependem de hardware
python pokeshake_init.py --dry-run    # só o e2e, direto
python -m pyflakes pokeshake tests    # restos e imports mortos
python -m pip_audit                   # vulnerabilidade conhecida nas dependências
```

São três camadas:

**Testes de unidade e integração** rodam contra o Qt de verdade — janelas,
timers, event loop — mas nunca contra o mouse da máquina: a entrada é
roteirizada pela costura `ler_cursor` / `pressionado` em
[pointer.py](pokeshake/pointer.py), a mesma que o dry run usa.

| Arquivo | O que cobre |
|---|---|
| [tests/test_sprites.py](tests/test_sprites.py) | download, cache, reserva do PNG, nomes, escala |
| [tests/test_pointer.py](tests/test_pointer.py) | leitura do cursor, velocidade do gesto, bordas do botão |
| [tests/test_shake.py](tests/test_shake.py) | detecção da agitada, falsos positivos, janela do sprite |
| [tests/test_catch.py](tests/test_catch.py) | arremesso, colisão, captura, intervalo de expectativa |
| [tests/test_render.py](tests/test_render.py) | região suja, largura dos textos, custo do quadro |
| [tests/test_offline.py](tests/test_offline.py) | falha de download: aviso na tela, cache não envenenado, nomes sem travar |
| [tests/test_pokedex.py](tests/test_pokedex.py) | registro, arquivo estragado, integração com a captura, tela |
| [tests/test_som.py](tests/test_som.py) | formatos de áudio, roteamento do grito, silêncio, filtro de ruído |
| [tests/test_app.py](tests/test_app.py) | menu, bandeja, troca de modos, Esc |
| [tests/test_dryrun.py](tests/test_dryrun.py) | e2e: o app como processo separado |

**O dry run** ([dryrun.py](pokeshake/dryrun.py)) sobe o aplicativo de verdade —
mesma `main`, mesma bandeja, mesmo menu — e passeia por 18 passos: liga a
Agitada, sacode o mouse, confere o sprite, troca para a Caçada, espera um
selvagem aparecer, arremessa a pokébola num alvo plantado, confirma a captura,
vê se ela entrou na Pokédex, se o grito foi pedido e se ela aparece na tela da
Pokédex, confere o intervalo, derruba a rede para ver o aviso aparecer e sai com
Esc. A Pokédex do dry run é um arquivo descartável e o som é registrado em vez
de tocado: um teste não pode inflar o progresso de verdade nem fazer barulho na
máquina de ninguém. O resultado vira código de saída, então
serve tanto na mão quanto dentro do pytest.

**Um teste mexe no dispositivo de verdade** e por isso é opt-in: ele injeta um
clique da roda com o cursor sobre a janela do próprio PokeShake, para o evento
ser consumido pelo app e não vazar para o que estiver aberto.

```bash
POKESHAKE_TEST_INPUT=1 pytest tests/test_pointer.py
```

### No GitHub Actions

[ci.yml](.github/workflows/ci.yml) roda em `windows-latest`, em Python 3.12 e
3.14: pyflakes, a suíte e o dry run. Três decisões que fazem a diferença entre
um CI útil e um CI que vive vermelho:

- **`QT_QPA_PLATFORM=offscreen`**: o runner não tem desktop como o de uma
  máquina de verdade. A suíte inteira foi conferida nessa plataforma, inclusive
  o dry run — que ali cai no caminho "sem área de notificação", o mesmo de quem
  desliga os ícones da bandeja.
- **`-m "not slow"`**: o custo de quadro e a reprodução de áudio dependem de
  hardware e não dizem nada num runner compartilhado. Rode esses dois na sua
  máquina.
- **Cache de `~/.poke_shake_cache`**: os testes baixam sprites de verdade. Com
  cache a execução é rápida e a rede sai do caminho crítico; sem cache a suíte
  ainda passa, porque o que não baixa vira teste pulado e não falha.

Nenhum teste depende de fonte, DPI ou resolução: a região suja do HUD é medida
a partir do texto, e as asserções conferem que ela cobre as caixas desenhadas —
não uma largura fixa em pixels.

O CI instala pelas **faixas** do pyproject, não pelo `constraints.txt`: assim
ele avisa quando uma versão nova de PyQt6 quebra algo, em vez de isso aparecer
só na máquina de quem instalar depois. O passo do `pip-audit` falha de
propósito quando surge CVE numa dependência — fica vermelho sem ninguém ter
mexido no código, que é justamente o aviso que se quer.

## Segurança

[SECURITY.md](SECURITY.md) tem a fronteira de confiança por escrito: o que é
baixado, de onde, o que é validado antes de entrar no cache, e qual risco
permanece. Em resumo: três origens fixas por HTTPS, teto de 4 MB por resposta,
cabeçalho de arquivo conferido antes de gravar, nenhum `eval`/`exec`/shell, e
leitura de teclado restrita ao botão configurado enquanto o modo Caçada está
ligado.

## Ajustes

As constantes estão todas em [pokeshake/config.py](pokeshake/config.py):

| Constante | Efeito |
|---|---|
| `SHAKE_REVERSALS` | quantas inversões de direção exigir (menos = mais sensível) |
| `SHAKE_SEGMENT_PX` | tamanho mínimo de cada trecho da agitada |
| `SHAKE_DISPLAY_MS` | quanto tempo o sprite fica na tela |
| `THROW_GESTURE` | tecla ou botão do arremesso |
| `WILD_TTL` | segundos até o Pokémon fugir |
| `WILD_MAX` | quantos Pokémon podem estar na tela ao mesmo tempo |
| `SPAWN_MIN` / `SPAWN_MAX` | intervalo entre aparições |
| `PAUSE_MIN` / `PAUSE_MAX` | silêncio depois de uma captura |
| `WILD_HEIGHT` | altura do Pokémon na tela, em pixels |
| `HIT_SHRINK` | área de acerto (1.0 = o sprite inteiro; menor = mais difícil) |
| `THROW_SPEED_MIN` / `MAX` | limites de força do arremesso |
| `GRAVITY` | o quanto a bola cai durante o voo |
| `CRY_VOLUME` | volume do grito, de 0.0 a 1.0; 0 começa mudo |
