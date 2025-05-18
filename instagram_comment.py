from instagrapi import Client
from dotenv import load_dotenv
import os
import time
import logging
import oci
import oci.generative_ai_inference.models
import requests
import base64
import json
from typing import List, Optional
from datetime import datetime
from instagram_mocks import MockInstagramClient

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('instagram_bot')

# Carrega as variáveis do arquivo .env
load_dotenv()

USE_MOCKS = os.getenv('USE_MOCKS', 'false').lower() == 'true'
session_file = 'instagram_session.json'

def carregar_prompt():
    try:
        with open('prompt.json', 'r', encoding='utf-8') as f:
            prompt_data = json.load(f)
            return prompt_data['prompt']
    except Exception as e:
        logger.info(f"Não foi possível carregar prompt.json: {str(e)}")
        return None

def carregar_usuarios() -> List[str]:
    """Carrega a lista de usuários do arquivo .env"""
    usuarios = os.getenv('INSTAGRAM_USERS', '').split(',')
    return [user.strip() for user in usuarios if user.strip()]

usuario = os.getenv('INSTAGRAM_USER')
senha = os.getenv('INSTAGRAM_PASSWORD')
url_do_post = os.getenv('INSTAGRAM_POST_URL')
comentario = os.getenv('INSTAGRAM_COMMENT')

config = {
    "user": os.getenv('OCI_USER'),
    "key_file": os.getenv('OCI_KEY_FILE'),
    "fingerprint": os.getenv('OCI_FINGERPRINT'),
    "tenancy": os.getenv('OCI_TENANCY'),
    "region": os.getenv('OCI_REGION')
}

try:
    if not os.path.exists(config["key_file"]):
        logger.info(f"Arquivo de chave não encontrado: {config['key_file']}")
        raise FileNotFoundError(f"Arquivo de chave não encontrado: {config['key_file']}")
    
    logger.info("Tentando inicializar cliente OCI com as seguintes configurações:")
    logger.info(f"User: {config['user']}")
    logger.info(f"Key File: {config['key_file']}")
    logger.info(f"Fingerprint: {config['fingerprint']}")
    logger.info(f"Tenancy: {config['tenancy']}")
    logger.info(f"Region: {config['region']}")
    
    endpoint = f"https://inference.generativeai.{config['region']}.oci.oraclecloud.com"
    logger.info(f"Endpoint: {endpoint}")
    
    oci_client = oci.generative_ai_inference.GenerativeAiInferenceClient(
        config=config,
        service_endpoint=endpoint,
        retry_strategy=oci.retry.NoneRetryStrategy(),
        timeout=(100, 240)
    )
    logger.info("Cliente OCI inicializado com sucesso!")
except FileNotFoundError as e:
    logger.info(f"Arquivo não encontrado: {str(e)}")
    oci_client = None
except Exception as e:
    logger.info(f"Não foi possível inicializar cliente OCI: {str(e)}")
    logger.info(f"Tipo do erro: {type(e).__name__}")
    oci_client = None

def time_execution(func_name):
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.info(f"Iniciando {func_name}...")
            start = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start
            logger.info(f"{func_name} concluído em {duration:.2f} segundos")
            return result
        return wrapper
    return decorator

@time_execution("Login")
def realizar_login(client, username, password):
    try:
        if os.path.exists(session_file):
            logger.info("Encontrada sessão salva. Tentando reutilizar...")
            client.load_settings(session_file)
            
            try:
                client.get_timeline_feed()
                logger.info("Sessão válida!")
                return True
            except Exception as e:
                logger.warning(f"Sessão expirada: {e}")
        
        logger.info("Realizando novo login...")
        success = client.login(username, password)
        
        if success:
            client.dump_settings(session_file)
            logger.info("Sessão salva com sucesso!")
        return success
    except Exception as e:
        logger.error(f"Erro ao fazer login: {e}")
        return False

@time_execution("Obtenção do último post")
def obter_ultimo_post_foto(client, username: str):
    """Obtém o último post que seja uma foto do usuário especificado"""
    try:
        logger.info(f"Buscando posts do usuário {username}")
        user_id = client.user_id_from_username(username)
        logger.info(f"ID do usuário: {user_id}")
        
        medias = client.user_medias(user_id, 20)  # Busca os últimos 20 posts
        logger.info(f"Total de posts encontrados: {len(medias)}")
        
        for i, media in enumerate(medias, 1):
            logger.info(f"\nAnalisando post {i}:")
            logger.info(f"Tipo de mídia: {media.media_type}")
            logger.info(f"Legenda: {media.caption_text[:100]}...")
            
            # Verifica se é uma foto (media_type 1) ou carrossel (media_type 8)
            if media.media_type in [1, 8]:
                # Se for carrossel, verifica se tem recursos e se o primeiro é uma foto
                if media.media_type == 8:
                    logger.info("Post é um carrossel")
                    if hasattr(media, 'resources') and media.resources:
                        first_resource = media.resources[0]
                        logger.info(f"Primeiro recurso do carrossel - Tipo: {first_resource.media_type}")
                        if first_resource.media_type == 1:  # Verifica se a primeira mídia é uma foto
                            logger.info("Carrossel válido encontrado (primeira mídia é foto)")
                            return media
                    else:
                        logger.info("Carrossel sem recursos")
                # Se for uma foto única, retorna direto
                elif media.media_type == 1:
                    logger.info("Foto única encontrada")
                    return media
            else:
                logger.info(f"Post ignorado - tipo de mídia não suportado: {media.media_type}")
                
        logger.info(f"Nenhuma foto encontrada para o usuário {username}")
        return None
    except Exception as e:
        logger.info(f"Não foi possível obter posts do usuário {username}: {e}")
        logger.info(f"Tipo do erro: {type(e).__name__}")
        return None

@time_execution("Obtenção do ID do post")
def obter_id_post(client, url):
    return client.media_pk_from_url(url)

@time_execution("Obtenção de informações do post")
def obter_info_post(client, media_id):
    return client.media_info(media_id)

@time_execution("Obtenção dos comentários")
def obter_comentarios(client, media_id, quantidade=10):
    return client.media_comments(media_id, amount=quantidade)

@time_execution("Envio de comentário")
def comentar_post(client, media_id, texto):
    return client.media_comment(media_id, texto)

@time_execution("Resposta ao comentário")
def responder_comentario(client, media_id, comentario_id, texto):
    return client.media_comment(media_id, texto, replied_to_comment_id=comentario_id)

@time_execution("Análise de imagem")
def analisar_imagem(media_info) -> str:
    """Analisa a imagem e legenda do post usando o Llama."""
    if oci_client is None:
        return "Cliente OCI não inicializado"
    
    try:
        if hasattr(media_info, 'resources') and media_info.resources:
            image_url = media_info.resources[0].thumbnail_url
            logger.info("Post é um carrossel, analisando primeira imagem")
        else:
            image_url = media_info.thumbnail_url
            logger.info("Post é uma imagem única")
            
        try:
            response = requests.get(image_url)
            response.raise_for_status()
            image_data = response.content
            base64_image = base64.b64encode(image_data).decode("utf-8")
            base64_image_url = f"data:image/jpeg;base64,{base64_image}"
        except Exception as e:
            logger.info(f"Não foi possível processar imagem: {str(e)}")
            return f"Não foi possível processar imagem: {str(e)}"
        
        prompt_text = """Analise esta imagem e sua legenda. Descreva em detalhes:
1. O que você vê na imagem
2. O contexto da legenda
3. O tom e estilo do post
4. Elementos visuais importantes

Legenda: {legenda}"""

        texto = oci.generative_ai_inference.models.TextContent(
            text=prompt_text.format(legenda=media_info.caption_text)
        )
        
        imagem = oci.generative_ai_inference.models.ImageContent(
            image_url=oci.generative_ai_inference.models.ImageUrl(url=base64_image_url)
        )
        
        mensagem = oci.generative_ai_inference.models.UserMessage(
            role="USER",
            content=[texto, imagem]
        )

        chat_request = oci.generative_ai_inference.models.GenericChatRequest(
            api_format="GENERIC",
            messages=[mensagem],
            num_generations=1,
            is_stream=False,
            max_tokens=600,
            temperature=0.7,
            frequency_penalty=0,
            presence_penalty=0,
            top_p=0.5,
            top_k=1
        )

        chat_detail = oci.generative_ai_inference.models.ChatDetails(
            compartment_id=os.getenv('OCI_COMPARTMENT_ID'),
            serving_mode=oci.generative_ai_inference.models.OnDemandServingMode(
                model_id="meta.llama-3.2-90b-vision-instruct"
            ),
            chat_request=chat_request
        )

        chat_response = oci_client.chat(chat_detail)
        
        if chat_response and chat_response.data and chat_response.data.chat_response:
            choices = chat_response.data.chat_response.choices
            if choices and len(choices) > 0:
                return choices[0].message.content[0].text.strip()
        
        return "Não foi possível analisar a imagem"
        
    except Exception as e:
        return f"Erro na análise: {str(e)}"

@time_execution("Geração de resposta")
def gerar_resposta(comentario_texto: str, media_info) -> str:
    """Gera uma resposta usando o modelo Llama via OCI."""
    if oci_client is None:
        erro = "Cliente OCI não inicializado"
        logger.error(erro)
        return f"Erro: {erro}"
    
    try:
        logger.info("Iniciando geração de resposta...")
        logger.info(f"Comentário recebido: {comentario_texto}")
        
        # Primeiro, faz a análise da imagem
        print("\n🔍 Analisando imagem e legenda...")
        analise = analisar_imagem(media_info)
        print("\n📊 Análise do post:")
        print("=" * 50)
        print(analise)
        print("=" * 50)
        
        prompt_data = carregar_prompt()
        if not prompt_data:
            return "Erro: Não foi possível carregar o prompt"
        
        if hasattr(media_info, 'resources') and media_info.resources:
            image_url = media_info.resources[0].thumbnail_url
            logger.info("Post é um carrossel, usando primeira imagem")
        else:
            image_url = media_info.thumbnail_url
            logger.info("Post é uma imagem única")
            
        logger.info(f"URL da imagem: {image_url}")
        
        try:
            response = requests.get(image_url)
            response.raise_for_status()
            image_data = response.content
            base64_image = base64.b64encode(image_data).decode("utf-8")
            base64_image_url = f"data:image/jpeg;base64,{base64_image}"
            
            logger.info("Imagem convertida para base64 com sucesso")
        except Exception as e:
            logger.info(f"Não foi possível processar imagem: {str(e)}")
            return f"Não foi possível processar imagem: {str(e)}"
        
        # Limpa apenas emojis e caracteres não desejados, mantendo acentos
        import re
        # Remove emojis e outros caracteres especiais não desejados
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"  # emoticons
            u"\U0001F300-\U0001F5FF"  # símbolos & pictogramas
            u"\U0001F680-\U0001F6FF"  # transport & map symbols
            u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)
        
        comentario_limpo = emoji_pattern.sub('', comentario_texto)
        logger.info(f"Comentário após limpeza: {comentario_limpo}")
        
        # Constrói o prompt completo incluindo a análise
        prompt_text = "\n".join(prompt_data['instructions'])
        prompt_text += "\n\nAnálise do post:\n" + analise
        prompt_text += "\n\n" + prompt_data['comment_template'].format(comment=comentario_limpo)
        
        print("\n📝 Comentário que será enviado para o Llama:")
        print("=" * 50)
        print(comentario_limpo)
        print("=" * 50)
        
        print("\n📋 Prompt completo que será enviado para o Llama:")
        print("=" * 50)
        print(prompt_text)
        print("=" * 50)
        
        texto = oci.generative_ai_inference.models.TextContent(
            text=prompt_text
        )
        
        imagem = oci.generative_ai_inference.models.ImageContent(
            image_url=oci.generative_ai_inference.models.ImageUrl(url=base64_image_url)
        )
        
        mensagem = oci.generative_ai_inference.models.UserMessage(
            role="USER",
            content=[texto, imagem]
        )
        logger.info("Mensagem criada com sucesso")

        print("\n⚙️ Configurações do chat:")
        print("=" * 50)
        print(f"Modelo: meta.llama-3.2-90b-vision-instruct")
        print(f"Max tokens: 600")
        print(f"Temperature: 0.7")
        print(f"Top P: 0.5")
        print(f"Top K: 1")
        print("=" * 50)

        chat_request = oci.generative_ai_inference.models.GenericChatRequest(
            api_format="GENERIC",
            messages=[mensagem],
            num_generations=1,
            is_stream=False,
            max_tokens=600,
            temperature=0.7,
            frequency_penalty=0,
            presence_penalty=0,
            top_p=0.5,
            top_k=1
        )
        logger.info("Chat request configurado")

        chat_detail = oci.generative_ai_inference.models.ChatDetails(
            compartment_id=os.getenv('OCI_COMPARTMENT_ID'),
            serving_mode=oci.generative_ai_inference.models.OnDemandServingMode(
                model_id="meta.llama-3.2-90b-vision-instruct"
            ),
            chat_request=chat_request
        )
        logger.info("Chat details configurados")

        print("\n📤 Request completo para o Llama:")
        print("=" * 50)
        print(f"Compartment ID: {chat_detail.compartment_id}")
        print(f"Model ID: {chat_detail.serving_mode.model_id}")
        print("\nMensagens:")
        for msg in chat_request.messages:
            print(f"\nRole: {msg.role}")
            for content in msg.content:
                if hasattr(content, 'text'):
                    print(f"Texto completo:")
                    print("-" * 50)
                    print(content.text)
                    print("-" * 50)
                if hasattr(content, 'image_url'):
                    print(f"URL da imagem: {content.image_url.url[:100]}...")
        print("\nConfigurações:")
        print(f"Max tokens: {chat_request.max_tokens}")
        print(f"Temperature: {chat_request.temperature}")
        print(f"Top P: {chat_request.top_p}")
        print(f"Top K: {chat_request.top_k}")
        print("=" * 50)

        logger.info("Fazendo chamada para a API...")
        chat_response = oci_client.chat(chat_detail)
        logger.info("Resposta recebida da API")
        
        if chat_response and chat_response.data and chat_response.data.chat_response:
            choices = chat_response.data.chat_response.choices
            if choices and len(choices) > 0:
                response_text = choices[0].message.content[0].text
                logger.info(f"Resposta completa da Llama: {chat_response.data}")
                return response_text.strip()
        
        erro = "Resposta da API inválida ou vazia"
        logger.error(erro)
        return f"Erro: {erro}"
        
    except Exception as e:
        erro = f"Erro ao gerar resposta com Llama via OCI: {str(e)}"
        logger.error(erro)
        logger.error(f"Tipo do erro: {type(e).__name__}")
        return f"Erro: {erro}"

def confirmar_resposta(resposta: str) -> bool:
    """Solicita confirmação do usuário antes de enviar a resposta."""
    print("\n🤖 Resposta gerada:")
    print("=" * 50)
    print(resposta)
    print("=" * 50)
    
    while True:
        confirmacao = input("\nDeseja enviar esta resposta? (yes/no): ").lower().strip()
        if confirmacao in ['yes', 'no']:
            return confirmacao == 'yes'
        print("Por favor, responda com 'yes' ou 'no'")

def escolher_modo_comentario() -> str:
    """Permite ao usuário escolher o modo de comentário."""
    print("\n📝 Escolha o modo de comentário:")
    print("1. Comentar em um comentário específico")
    print("2. Comentar diretamente no post")
    
    while True:
        escolha = input("\nDigite 1 ou 2: ").strip()
        if escolha in ['1', '2']:
            return escolha
        print("Por favor, digite 1 ou 2")

def escolher_comentario(comentarios: list) -> object:
    """Permite ao usuário escolher um comentário da lista."""
    print("\n💬 Comentários disponíveis:")
    print("=" * 50)
    for i, comentario in enumerate(comentarios, 1):
        print(f"{i}. {comentario.user.username}: {comentario.text}")
    print("=" * 50)
    
    while True:
        try:
            escolha = int(input("\nDigite o número do comentário (ou 0 para voltar): ").strip())
            if escolha == 0:
                return None
            if 1 <= escolha <= len(comentarios):
                return comentarios[escolha - 1]
            print(f"Por favor, digite um número entre 1 e {len(comentarios)}")
        except ValueError:
            print("Por favor, digite um número válido")

def processar_usuario(client, username: str):
    """Processa um usuário específico, obtendo seu último post e interagindo com ele."""
    logger.info(f"Processando usuário: {username}")
    
    try:
        media_info = obter_ultimo_post_foto(client, username)
        if not media_info:
            logger.info(f"Nenhum post de foto encontrado para {username}")
            return
        
        print(f"\n📝 Post de {username}:")
        print("=" * 50)
        print(media_info.caption_text)
        print("=" * 50)
        
        comentarios = obter_comentarios(client, media_info.pk)
        
        modo = escolher_modo_comentario()
        
        if modo == '1':
            comentario_escolhido = escolher_comentario(comentarios)
            if comentario_escolhido:
                try:
                    resposta = gerar_resposta(comentario_escolhido.text, media_info)
                    
                    if confirmar_resposta(resposta):
                        resposta = resposta.replace('"', '').replace("'", "")
                        result = responder_comentario(client, media_info.pk, comentario_escolhido.pk, resposta)
                        print("\n✅ Resposta enviada com sucesso!")
                        logger.info(f"Resposta publicada com ID: {result.pk}")
                    else:
                        print("\n❌ Resposta cancelada pelo usuário!")
                except Exception as e:
                    logger.error(f"Erro ao publicar resposta: {e}")
                    print("\n❌ Falha ao enviar resposta!")
            else:
                print("\n❌ Nenhum comentário selecionado!")
        else:
            try:
                resposta = gerar_resposta(media_info.caption_text, media_info)
                
                if confirmar_resposta(resposta):
                    result = comentar_post(client, media_info.pk, resposta)
                    print("\n✅ Comentário enviado com sucesso!")
                    logger.info(f"Comentário publicado com ID: {result.pk}")
                else:
                    print("\n❌ Comentário cancelado pelo usuário!")
            except Exception as e:
                logger.error(f"Erro ao publicar comentário: {e}")
                print("\n❌ Falha ao enviar comentário!")
                
    except Exception as e:
        logger.error(f"Erro ao processar usuário {username}: {e}")
        print(f"\n❌ Falha ao processar usuário {username}!")

def main():
    logger.info("=== INICIANDO O PROGRAMA ===")
    total_start = time.time()
    
    # Carrega lista de usuários
    usuarios = carregar_usuarios()
    if not usuarios:
        logger.error("Nenhum usuário encontrado na configuração!")
        return
    
    print(f"\n👥 Usuários carregados: {len(usuarios)}")
    for i, user in enumerate(usuarios, 1):
        print(f"{i}. {user}")
    
    if USE_MOCKS:
        logger.info("Usando mocks para simulação")
        cl = MockInstagramClient()
    else:
        cl = Client()
        # Configuração do dispositivo
        cl.set_device({
            "app_version": "219.0.0.12.117",
            "android_version": 0,
            "android_release": "0",
            "dpi": "640dpi",
            "resolution": "1242x2688",
            "manufacturer": "Apple",
            "device": "iPhone",
            "model": "iPhone XS",
            "cpu": "apple"
        })
    
    if not realizar_login(cl, usuario, senha):
        logger.error("Falha ao fazer login! Verificar credenciais.")
        return
    
    # Processa cada usuário da lista
    for username in usuarios:
        processar_usuario(cl, username)
        print("\n" + "="*50 + "\n")
    
    total_time = time.time() - total_start
    logger.info(f"=== PROGRAMA CONCLUÍDO EM {total_time:.2f} SEGUNDOS ===")

if __name__ == "__main__":
    main()