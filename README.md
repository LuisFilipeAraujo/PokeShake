# PokeShake

Pokémon da [PokeAPI](https://github.com/PokeAPI/sprites) aparecem por cima da
sua área de trabalho. Dois modos de jogo, escolhidos num menu overlay.

## Uso

```bash
pip install -r requirements.txt
python pokeshake_init.py                 # abre o menu de modos
python pokeshake_init.py --mode catch    # já começa caçando
python pokeshake_init.py --mode shake
python pokeshake_init.py --demo          # mostra um Pokémon e sai
```

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
vezes e a captura é confirmada com faíscas e o nome dele na tela. `Esc` sai do
modo.

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
| [pokeshake/config.py](pokeshake/config.py) | todas as constantes de ajuste |
| [pokeshake/sprites.py](pokeshake/sprites.py) | download, cache em disco e preparo dos sprites |
| [pokeshake/pointer.py](pokeshake/pointer.py) | leitura do cursor e do gesto, sem hooks |
| [pokeshake/shake.py](pokeshake/shake.py) | modo Agitada |
| [pokeshake/catch.py](pokeshake/catch.py) | modo Caçada: física, colisão e captura |
| [pokeshake/pokedex.py](pokeshake/pokedex.py) | registro das capturas em disco |
| [pokeshake/menu.py](pokeshake/menu.py) | menu overlay, tela da Pokédex e ícone da bandeja |
| [pokeshake/app.py](pokeshake/app.py) | bandeja e troca de modos |

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
pip install -r requirements-dev.txt

pytest                                # suíte inteira, ~1 min
pytest -m "not slow"                  # sem os testes de performance
python pokeshake_init.py --dry-run    # só o e2e, direto
python -m pyflakes pokeshake tests    # restos e imports mortos
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
| [tests/test_app.py](tests/test_app.py) | menu, bandeja, troca de modos, Esc |
| [tests/test_dryrun.py](tests/test_dryrun.py) | e2e: o app como processo separado |

**O dry run** ([dryrun.py](pokeshake/dryrun.py)) sobe o aplicativo de verdade —
mesma `main`, mesma bandeja, mesmo menu — e passeia por 18 passos: liga a
Agitada, sacode o mouse, confere o sprite, troca para a Caçada, espera um
selvagem aparecer, arremessa a pokébola num alvo plantado, confirma a captura,
vê se ela entrou na Pokédex e aparece na tela dela, confere o intervalo, derruba
a rede para ver o aviso aparecer e sai com Esc. A Pokédex do dry run é um
arquivo descartável: um teste não pode inflar o progresso de verdade. O resultado vira código de saída, então
serve tanto na mão quanto dentro do pytest.

**Um teste mexe no dispositivo de verdade** e por isso é opt-in: ele injeta um
clique da roda com o cursor sobre a janela do próprio PokeShake, para o evento
ser consumido pelo app e não vazar para o que estiver aberto.

```bash
POKESHAKE_TEST_INPUT=1 pytest tests/test_pointer.py
```

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
