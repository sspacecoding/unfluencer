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

def carregar_prompt():
    try:
        with open('prompt.json', 'r', encoding='utf-8') as f:
            prompt_data = json.load(f)
            return prompt_data['prompt']
    except Exception as e:
        logger.error(f"Erro ao carregar prompt.json: {str(e)}")
        return None

usuario = os.getenv('INSTAGRAM_USER')
senha = os.getenv('INSTAGRAM_PASSWORD')
url_do_post = os.getenv('INSTAGRAM_POST_URL')
comentario = os.getenv('INSTAGRAM_COMMENT')
session_file = 'instagram_session.json'

config = {
    "user": os.getenv('OCI_USER'),
    "key_file": os.getenv('OCI_KEY_FILE'),
    "fingerprint": os.getenv('OCI_FINGERPRINT'),
    "tenancy": os.getenv('OCI_TENANCY'),
    "region": os.getenv('OCI_REGION')
}

try:
    if not os.path.exists(config["key_file"]):
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
    logger.error(f"Erro de arquivo: {str(e)}")
    oci_client = None
except Exception as e:
    logger.error(f"Erro ao inicializar cliente OCI: {str(e)}")
    logger.error(f"Tipo do erro: {type(e).__name__}")
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

@time_execution("Geração de resposta")
def gerar_resposta(comentario_texto: str, media_info) -> str:
    """Gera uma resposta usando o modelo Llama via OCI.

    Args:
        comentario_texto (str): O texto do comentário para gerar a resposta.
        media_info: Informações do post do Instagram, incluindo imagem.

    Returns:
        str: A resposta gerada pelo modelo Llama.

    Raises:
        Exception: Se houver erro na comunicação com a API OCI.
    """
    if oci_client is None:
        erro = "Cliente OCI não inicializado"
        logger.error(erro)
        return f"Erro: {erro}"
    
    try:
        logger.info("Iniciando geração de resposta...")
        logger.info(f"Comentário recebido: {comentario_texto}")
        
        # Carrega o prompt do arquivo JSON
        prompt_data = carregar_prompt()
        if not prompt_data:
            return "Erro: Não foi possível carregar o prompt"
        
        # Obtém a URL da primeira imagem do carrossel
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
            
            print("\n🖼️ Base64 da imagem:")
            print("=" * 50)
            print(base64_image[:100] + "..." if len(base64_image) > 100 else base64_image)
            print("=" * 50)
            print(f"Tamanho do base64: {len(base64_image)} caracteres")
            
            logger.info("Imagem convertida para base64 com sucesso")
        except Exception as e:
            logger.error(f"Erro ao processar imagem: {str(e)}")
            return f"Erro ao processar imagem: {str(e)}"
        
        # Constrói o prompt completo
        prompt_text = "\n".join(prompt_data['instructions'])
        prompt_text += "\n\n" + prompt_data['comment_template'].format(comment=comentario_texto)
        
        print("\n📝 Prompt enviado para o Llama:")
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
                    print(f"Texto: {content.text[:200]}..." if len(content.text) > 200 else f"Texto: {content.text}")
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
    """Solicita confirmação do usuário antes de enviar a resposta.

    Args:
        resposta (str): A resposta gerada que será enviada.

    Returns:
        bool: True se o usuário confirmar, False se cancelar.
    """
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
    """Permite ao usuário escolher o modo de comentário.

    Returns:
        str: '1' para comentar em um comentário específico, '2' para comentar no post.
    """
    print("\n📝 Escolha o modo de comentário:")
    print("1. Comentar em um comentário específico")
    print("2. Comentar diretamente no post")
    
    while True:
        escolha = input("\nDigite 1 ou 2: ").strip()
        if escolha in ['1', '2']:
            return escolha
        print("Por favor, digite 1 ou 2")

def escolher_comentario(comentarios: list) -> object:
    """Permite ao usuário escolher um comentário da lista.

    Args:
        comentarios (list): Lista de comentários disponíveis.

    Returns:
        object: O comentário escolhido ou None se o usuário cancelar.
    """
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

def main():
    logger.info("=== INICIANDO O PROGRAMA ===")
    total_start = time.time()
    
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
    
    try:
        media_id = obter_id_post(cl, url_do_post)
        logger.info(f"ID do post: {media_id}")
    except Exception as e:
        logger.error(f"Erro ao obter ID do post: {e}")
        return
    
    try:
        media_info = obter_info_post(cl, media_id)
    except Exception as e:
        logger.error(f"Erro ao obter informações do post: {e}")
        return
    
    print("\n📝 Descrição do Post:")
    print("=" * 50)
    print(media_info.caption_text)
    print("=" * 50)
    
    try:
        comentarios = obter_comentarios(cl, media_id)
        
        modo = escolher_modo_comentario()
        
        if modo == '1':
            comentario_escolhido = escolher_comentario(comentarios)
            if comentario_escolhido:
                try:
                    resposta = gerar_resposta(comentario_escolhido.text, media_info)
                    
                    if confirmar_resposta(resposta):
                        resposta = resposta.replace('"', '').replace("'", "")
                        result = responder_comentario(cl, media_id, comentario_escolhido.pk, resposta)
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
                    result = comentar_post(cl, media_id, resposta)
                    print("\n✅ Comentário enviado com sucesso!")
                    logger.info(f"Comentário publicado com ID: {result.pk}")
                else:
                    print("\n❌ Comentário cancelado pelo usuário!")
            except Exception as e:
                logger.error(f"Erro ao publicar comentário: {e}")
                print("\n❌ Falha ao enviar comentário!")
            
    except Exception as e:
        logger.error(f"Erro ao obter comentários: {e}")
        print("\n❌ Falha ao obter comentários!")
    
    total_time = time.time() - total_start
    logger.info(f"=== PROGRAMA CONCLUÍDO EM {total_time:.2f} SEGUNDOS ===")

if __name__ == "__main__":
    main()