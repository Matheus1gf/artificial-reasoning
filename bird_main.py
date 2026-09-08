#!/usr/bin/env python3
"""
Protótipo histórico de identificação de pássaros com IA
TCC - 2025

Ponto de entrada principal do sistema
"""

# Suprimir warnings SSL/OpenSSL antes de qualquer importação
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")
warnings.filterwarnings("ignore", message=".*urllib3 v2 only supports OpenSSL 1.1.1+.*")
warnings.filterwarnings("ignore", message=".*NotOpenSSLWarning.*")
# Suprimir warnings do TensorFlow
warnings.filterwarnings("ignore", category=UserWarning, module="tensorflow")
warnings.filterwarnings("ignore", message=".*TensorFlow.*")
warnings.filterwarnings("ignore", message=".*keras.*")
# Suprimir warnings gerais
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

import sys
import os
import tensorflow as tf
import logging
import json
from ultralytics import YOLO

logging.basicConfig(level=logging.INFO)

# --- CONFIGURAÇÃO ---
CLASSIFIER_MODEL_PATH = 'modelo_classificacao_passaros.keras'
YOLO_MODEL_PATH = 'runs/detect/train/weights/best.pt' # <<< NOVO: Caminho para o seu modelo YOLO treinado
CLASSES_FILE_PATH = 'data/classes.txt'
KNOWLEDGE_BASE_PATH = 'base_conhecimento.json'
# <<< NOVO: Limiar de confiança mínimo para aceitar a classificação de espécie
CONFIDENCE_THRESHOLD = 0.60 # 60%

# --- CARREGAMENTO DOS MODELOS ---
logging.info("Carregando modelo de classificação de espécies...")
modelo_especies = tf.keras.models.load_model(CLASSIFIER_MODEL_PATH)
logging.info(f"Carregando modelo de detecção de partes (YOLOv8) de '{YOLO_MODEL_PATH}'...")
modelo_yolo = YOLO(YOLO_MODEL_PATH)

base_conhecimento = {"especies_conhecidas": {}, "especies_novas": []}

def salvar_base_conhecimento(caminho=KNOWLEDGE_BASE_PATH):
    with open(caminho, 'w') as f:
        json.dump(base_conhecimento, f, indent=4, sort_keys=True)

def carregar_base_conhecimento(caminho=KNOWLEDGE_BASE_PATH):
    global base_conhecimento
    if os.path.exists(caminho):
        try:
            with open(caminho, 'r') as f:
                base_conhecimento = json.load(f)
                logging.info("Base de conhecimento carregada com sucesso.")
        except json.JSONDecodeError:
            logging.error("Erro ao decodificar base_conhecimento.json. Criando uma nova.")
            # Se o arquivo estiver corrompido, começamos do zero
            base_conhecimento = {"especies_conhecidas": {}, "especies_novas": []}
    else:
        logging.warning("Base de conhecimento não encontrada, criando uma nova.")

    # Bloco de verificação para garantir a compatibilidade
    # Garante que as chaves principais sempre existam no dicionário
    if 'especies_conhecidas' not in base_conhecimento:
        base_conhecimento['especies_conhecidas'] = {}
    if 'especies_novas' not in base_conhecimento:
        base_conhecimento['especies_novas'] = []

def identificar_especie(imagem):
    img_resized = cv2.resize(imagem, (224, 224))
    img_array = np.expand_dims(img_resized, axis=0) / 255.0
    predicao = modelo_especies.predict(img_array, verbose=0)
    id_classe = np.argmax(predicao[0])
    confianca = np.max(predicao[0])
    return id_classe, confianca

def carregar_nomes_classes(caminho=CLASSES_FILE_PATH):
    with open(caminho, 'r') as f:
        nomes = [' '.join(line.strip().split()[1:]).replace('_', ' ') for line in f]
    return nomes

def extrair_fatos_com_yolo(imagem):
    results = modelo_yolo(imagem, verbose=False)
    fatos_detectados = set()
    for r in results:
        for box in r.boxes:
            class_id = int(box.cls)
            class_name = modelo_yolo.names[class_id]
            fatos_detectados.add(class_name)
    return fatos_detectados

# >>>>> FUNÇÃO PRINCIPAL TOTALMENTE REFATORADA <<<<<
def analisar_imagem_passaro(caminho_imagem):
    imagem = cv2.imread(caminho_imagem)
    if imagem is None:
        logging.error(f"Erro ao carregar a imagem: {caminho_imagem}")
        return

    print("-" * 50)
    print(f"Analisando Imagem: {os.path.basename(caminho_imagem)}")
    
    # 1. RACIOCÍNIO BASEADO EM FATOS: É um pássaro?
    # A primeira pergunta é se a imagem contém partes que definem um pássaro.
    fatos_visuais = extrair_fatos_com_yolo(imagem)
    
    # Condições para ser considerado um pássaro
    is_bird = 'bico' in fatos_visuais or ('corpo' in fatos_visuais and 'asa' in fatos_visuais)

    if not is_bird:
        print("CONCLUSÃO: Não foi possível confirmar que é um pássaro.")
        print(f"Fatos Detectados: {list(fatos_visuais) if fatos_visuais else 'Nenhum'}")
        print("Análise encerrada para esta imagem.")
        print("-" * 50)
        return

    # 2. Se é um pássaro, vamos tentar identificar a espécie
    print(f"Fatos Visuais Detectados: {list(fatos_visuais)}")
    print("CONCLUSÃO PRELIMINAR: A imagem contém um pássaro.")

    id_especie, confianca = identificar_especie(imagem)
    nomes_classes = carregar_nomes_classes()
    nome_hipotese = nomes_classes[id_especie]

    # 3. Aplicar o ceticismo (limiar de confiança)
    if confianca >= CONFIDENCE_THRESHOLD:
        # A IA tem alta confiança, então é uma espécie que ela conhece
        especie_final = nome_hipotese
        print(f"ESPÉCIE (ALTA CONFIANÇA): '{especie_final}' com {confianca:.2%} de certeza.")
        
        # Adicionar à base de conhecimento de espécies conhecidas
        base_conhecimento["especies_conhecidas"][especie_final] = list(fatos_visuais)
        
    else:
        # A IA não tem certeza. É um pássaro, mas não um que ela reconhece bem.
        especie_final = f"Pássaro Desconhecido #{len(base_conhecimento['especies_novas']) + 1}"
        print(f"ESPÉCIE (BAIXA CONFIANÇA): É um pássaro, mas a espécie não foi reconhecida com certeza.")
        print(f"(Melhor palpite foi '{nome_hipotese}' com apenas {confianca:.2%} de confiança)")
        
        # Adicionar à lista de novas espécies para estudo futuro
        nova_especie_info = {
            "id_temporario": especie_final,
            "fatos": list(fatos_visuais),
            "palpite_classificador": nome_hipotese,
            "confianca_palpite": f"{confianca:.2%}"
        }
        base_conhecimento["especies_novas"].append(nova_especie_info)

    salvar_base_conhecimento()
    print("-" * 50)


def processar_diretorio(diretorio):
    for arquivo in os.listdir(diretorio):
        if arquivo.lower().endswith((".jpeg", ".jpg", ".png")):
            analisar_imagem_passaro(os.path.join(diretorio, arquivo))

# --- FLUXO DE EXECUÇÃO ---
if __name__ == "__main__":
    carregar_base_conhecimento()
    diretorio_de_teste = './dataset_teste'
    if not os.path.exists(diretorio_de_teste):
        print(f"\nAVISO: O diretório de teste '{diretorio_de_teste}' não foi encontrado.")
    else:
        processar_diretorio(diretorio_de_teste)
