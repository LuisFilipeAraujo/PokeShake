# Segurança

## Fronteira de confiança

O PokeShake é um app de desktop que roda com o seu usuário, sem privilégio
elevado, e tudo o que entra de fora vem de duas origens fixas, declaradas em
[pokeshake/config.py](pokeshake/config.py):

| Origem | O que vem | Para onde vai |
|---|---|---|
| `raw.githubusercontent.com/PokeAPI/sprites` | PNG e GIF de Pokémon e pokébolas | decodificadores de imagem do Qt |
| `raw.githubusercontent.com/PokeAPI/cries` | Ogg Vorbis e MP3 dos gritos | backend de mídia do Qt (FFmpeg) |
| `pokeapi.co/api/v2` | JSON com a lista de nomes | `json.loads` |

As URLs são constantes no código. Nada que venha da rede escolhe o endereço do
próximo download, e nenhum nome de arquivo é montado com texto de fora: os
caminhos do cache saem de inteiros e de nomes fixos, o que fecha travessia de
diretório.

## O que já é feito

- **Só HTTPS**, com verificação de certificado padrão do `requests`.
- **Teto de tamanho** (`LIMITE_DOWNLOAD`, 4 MB): a resposta é lida em pedaços e
  descartada se passar. Sem isso, uma resposta enorme viria inteira para a
  memória.
- **Validação de conteúdo antes de gravar no cache**: imagem precisa começar
  com cabeçalho de PNG ou GIF, áudio com Ogg, MP3 ou RIFF. É o que impede a
  página de login de um portal cativo, que responde 200, de virar um sprite
  permanente no disco.
- **Timeouts em toda requisição** (8 s para arquivos, 10 s para a lista de
  nomes), para o app não ficar pendurado numa rede que engole pacotes.
- **JSON de fora é tratado como suspeito**: a Pokédex em disco, se estiver
  ilegível, é preservada como `.quebrado` e a sessão começa limpa em vez de o
  app cair.
- **Nenhum `eval`, `exec`, `pickle`, shell ou subprocesso** no código do app.
- **Leitura de teclado restrita**: o gesto de arremesso é lido por consulta ao
  estado de um botão (`GetAsyncKeyState`), sem hook global. Só o botão
  configurado e `Esc` são consultados, e só enquanto o modo Caçada está ligado.
  Nada é interceptado nem escondido de outros programas.
- **Dependências com piso e teto** no [pyproject.toml](pyproject.toml), conjunto
  exato verificado em [constraints.txt](constraints.txt), e `pip-audit` no CI a
  cada execução.

## Risco que permanece

Bytes baixados são entregues aos decodificadores de imagem, GIF e áudio do Qt e
do FFmpeg. Uma falha de memória nesses decodificadores é explorável por conteúdo
malicioso, e isso não se projeta fora — só se reduz, o que as medidas acima
fazem: origem fixa, HTTPS, cabeçalho conferido, tamanho limitado. Quem leva a
sério roda o app num usuário sem privilégio e mantém o PyQt6 atualizado.

O cache em `~/.poke_shake_cache` fica com a permissão padrão do diretório
pessoal: quem já tem acesso à sua conta pode trocar um sprite por outro
conteúdo. Não há assinatura dos arquivos em cache.

## Reportar um problema

Abra uma issue em
[github.com/LuisFilipeAraujo/PokeShake/issues](https://github.com/LuisFilipeAraujo/PokeShake/issues).
É um projeto pessoal, sem SLA de resposta — e, se o problema for grave, diga
isso no título.
