# Unfluencer: Comentários inúteis que ninguém precisa 

### O objetivo é simples: acabar com o feed de aplausos automáticos e incomodar criadores que levam comentários de internet a sério demais.

Enquanto os algoritmos tradicionais servem pra confirmar suas crenças, reforçar bolhas e garantir aplausos automáticos, o Unfluencer se infiltra nesse ciclo de validação **e simplesmente discorda.** Ele lê postagens públicas e seus comentários, detecta bajulação, frases feitas, publis disfarçadas de opinião, e responde com uma cutucada que ninguém pediu. **Sem ofensas, sem crimes. Só incômodo de qualidade.**

### 1. Cutucada Pública: *Um lembrete de que nem todo post precisa de aplauso.*

O Unfluencer analisa postagens públicas principalmente aquelas que tentam ensinar algo, vender alguma fórmula ou influenciar com frases prontas.
Ele gera comentários que desafiam a narrativa idealizada, cutucam o ego e puxam o criador para a realidade. **Ele não odeia ninguém. Só não acredita em nada.**

### 2. Advogado do Diabo: *Levanta dúvidas, joga com o contraditório.*

Um influenciador posta um conteúdo e enquanto o post brilha e os comentários viram um culto coletivo, o Unfluencer entra em ação. Ele lê os comentários vazios, os elogios automáticos, os papagaios de influenciador, e solta **aquela resposta incômoda que expõe o quão vazio é tudo aquilo.**

Se o influenciador posta esperando só elogio, o Unfluencer entrega dúvida. Se alguém comenta “perfeita”, o Unfluencer responde “tá, mas por quê?”.
**Não porque ele se importa, mas porque quem se importa demais merece um comentário inútil para ser incomodado.**

[Saiba mais detalhes sobre o projeto na página oficial.](https://roan-asphalt-23d.notion.site/Unfluencer-1f6e40c8a60f8009926efd9f0b747b9b)

## Como rodar o Unfluencer

Para testar o Unfluencer na sua máquina, você precisará configurar duas coisas: uma conta de Instagram e uma conta na Oracle Cloud.

#### 1. Configurar uma conta no Instagram

O Unfluencer utiliza a biblioteca `instagrapi` para interagir com postagens públicas. Para isso, você deve:

- Criar uma conta no [Instagram](https://www.instagram.com/) exclusiva para testes.
- Garantir que a conta esteja **ativa e verificada** (sem pendências de segurança).
- **Preferencialmente** com autenticação em dois fatores ativada (isso ajuda na estabilidade da sessão com o `instagrapi`).

Depois disso, atualize suas credenciais no arquivo `.env`, seguindo o modelo em [`env.example`](https://github.com/sspacecoding/unfluencer/blob/main/.env.example).

#### 2. Configurar a Oracle Cloud 

1. Crie uma conta gratuita em [cloud.oracle.com](https://cloud.oracle.com/)
2. Acesse o painel de **IAM (Identity & Access Management)**
3. Crie um novo **usuário**
4. Gere um **par de chaves** (pública e privada)
5. Adicione a **chave pública** ao seu usuário no painel da Oracle

Com isso feito, preencha as seguintes variáveis no seu arquivo `.env`:

```env
OCI_USER=ocid1.user.oc1..xxxx
OCI_KEY_FILE=/caminho/para/sua/chave-privada.pem
OCI_FINGERPRINT=xx:xx:xx:xx:xx
OCI_TENANCY=ocid1.tenancy.oc1..xxxx
OCI_REGION=sa-saopaulo-1
OCI_COMPARTMENT_ID=ocid1.compartment.oc1..xxx
```

- Instale as dependências as [dependências](https://github.com/sspacecoding/unfluencer/blob/main/requirements.txt) usando o comando `pip install -r requirements.txt`.


## Como o Unfluencer funciona

O script principal do projeto é o [`instagram_comment.py`](./instagram_comment.py), responsável por automatizar o processo de comentar postagens. Abaixo, o fluxo geral da aplicação:

- Faz login no Instagram usando `instagrapi`. Se existir uma sessão (`instagram_session.json`), ela é reutilizada.
- Obtém o ID da postagem a partir da URL (`INSTAGRAM_POST_URL`).
- Baixa a imagem da postagem e converte para base64.
- Lê a legenda ou um comentário existente.
- Constrói um prompt com texto + imagem e envia para o modelo **LLaMA 3.2 Vision** via **OCI Generative AI API**.
- Recebe a resposta de comentário provocativo.
- Comenta diretamente no post ou responde a um comentário existente.

### Arquivos importantes

- `.env`: armazena as credenciais de acesso (Instagram + OCI)
- `prompt.json`: define as instruções e template do prompt enviado à IA
- `instagram_session.json`: salva a sessão de login para evitar autenticação repetida


> O Unfluencer é basicamente isso: uma IA que acorda, faz um comentário inútil que ninguém pediu, e volta a dormir.

Para fins comerciais ou solicitações de uso, entre em contato com os criadores. O conteúdo completo da licença está disponível no arquivo [LICENSE](https://github.com/sspacecoding/unfluencer/blob/main/LICENSE).
_Desenvolvido por [@spacecoding](https://www.instagram.com/) [@santgus](https://www.instagram.com/sant.gus/) [@jorge.hen](https://www.instagram.com/jorg.hen/)_

