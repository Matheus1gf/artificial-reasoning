# 🐦 Sistema de Identificação de Pássaros com IA

> Documento histórico do primeiro protótipo. As instruções atuais estão no [README do chatbot](../README.md). Os caminhos abaixo são os nomes usados na raiz do projeto original; os antigos pontos de entrada agora se chamam `bird_main.py` e `bird_app.py`, e suas dependências estão em `requirements-birds.txt`. As alegações e resultados deste documento não validam o chatbot atual.

**TCC - 2025** | Sistema avançado de identificação de pássaros utilizando inteligência artificial com aprendizado contínuo.

## 🚀 Início Rápido

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Baixar modelos necessários (IMPORTANTE!)
python3 download_models.py

# 3. Executar sistema
python3 -m streamlit run main.py
# OU
python3 start_system.py
```

## 📦 Modelos Necessários

⚠️ **IMPORTANTE**: Os modelos YOLO não estão incluídos no repositório devido ao limite de tamanho do GitHub.

### Baixar Modelos Automaticamente:
```bash
python3 download_models.py
```

### Baixar Modelos Manualmente:
- **yolov8n.pt** (recomendado para desenvolvimento): [Download](https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt)
- **yolov8s.pt** (melhor precisão): [Download](https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8s.pt)

### Modelos Opcionais:
- **yolov8m.pt**: [Download](https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8m.pt)
- **yolov8l.pt**: [Download](https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8l.pt)
- **yolov8x.pt**: [Download](https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8x.pt)

## 📁 Estrutura do Projeto

```
tcc_bird-identify/
├── src/                          # Código fonte principal
│   ├── core/                     # Módulos core do sistema
│   │   ├── intuition.py          # Motor de intuição
│   │   ├── annotator.py          # Anotador automático
│   │   ├── curator.py            # Curador híbrido
│   │   ├── learning.py           # Sistema de aprendizado
│   │   ├── reasoning.py          # Sistema de raciocínio
│   │   └── cache.py              # Cache de reconhecimento
│   ├── interfaces/               # Interfaces de usuário
│   │   ├── web_app.py            # Aplicação web principal
│   │   ├── manual_analysis.py    # Sistema de análise manual
│   │   └── tinder_interface.py   # Interface estilo Tinder
│   ├── training/                 # Scripts de treinamento
│   │   ├── yolo_trainer.py       # Treinamento YOLO
│   │   └── keras_trainer.py      # Treinamento Keras
│   └── utils/                    # Utilitários
│       ├── patches.py            # Patches de compatibilidade
│       └── logger.py             # Sistema de logs
├── data/                         # Dados do projeto
│   ├── datasets/                 # Datasets de treinamento
│   ├── models/                   # Modelos treinados
│   ├── learning_data/            # Dados de aprendizado
│   └── manual_analysis/          # Análises manuais
├── config/                       # Configurações
│   ├── models.yaml               # Configuração dos modelos
│   └── settings.yaml             # Configurações gerais
├── docs/                         # Documentação
├── scripts/                      # Scripts de instalação
├── main.py                       # Ponto de entrada principal
└── requirements.txt              # Dependências
```

## 🧠 Funcionalidades Principais

### 1. **Sistema de Intuição**
- Detecta fronteiras do conhecimento
- Identifica quando a IA precisa aprender
- Ativa ciclos de aprendizado automático

### 2. **Análise Híbrida**
- YOLO para detecção de partes
- Keras para classificação de espécies
- Validação com APIs externas

### 3. **Aprendizado Contínuo**
- Re-treinamento automático
- Feedback detalhado do usuário
- Sincronização de dados

### 4. **Interface Intuitiva**
- Upload e análise de imagens
- Interface estilo Tinder para aprovação
- Visualização de resultados

## 🔧 Instalação

### Requisitos
- Python 3.9+
- TensorFlow 2.x
- PyTorch
- OpenCV
- Streamlit

### Instalação Automática
```bash
# Linux/Mac
chmod +x scripts/install_linux.sh
./scripts/install_linux.sh

# Windows
scripts\install_windows.bat
```

### Instalação Manual
```bash
pip install -r requirements.txt
```

## 🎯 Como Usar

### 1. **Análise de Imagens**
1. Acesse a aplicação web
2. Faça upload de uma imagem
3. Clique em "Analisar Imagem"
4. Veja os resultados da detecção

### 2. **Análise Manual**
1. Vá para a aba "Análise Manual"
2. Use a interface estilo Tinder
3. Aprove ou rejeite imagens
4. Forneça feedback detalhado

### 3. **Feedback de Aprendizado**
1. Acesse a aba "Feedback de Aprendizado"
2. Visualize dados coletados
3. Monitore o progresso do ML
4. Analise características identificadas

## 📊 Monitoramento

### Sincronização
- Monitore o aprendizado contínuo
- Veja estatísticas de sincronização
- Controle o re-treinamento

### Cache de Reconhecimento
- Visualize imagens já reconhecidas
- Veja estatísticas por espécie
- Gerencie o cache

## 🛠️ Desenvolvimento

### Estrutura de Módulos
- **Core**: Lógica principal do sistema
- **Interfaces**: Interfaces de usuário
- **Training**: Scripts de treinamento
- **Utils**: Utilitários e patches

### Configuração
- Edite `config/settings.yaml` para ajustar configurações
- Modifique `config/models.yaml` para configurações dos modelos

## 📈 Roadmap

- [x] Sistema de intuição
- [x] Análise híbrida
- [x] Aprendizado contínuo
- [x] Interface web
- [x] Feedback detalhado
- [ ] API REST
- [ ] Mobile app
- [ ] Cloud deployment

## 🧪 Testes

### Automação
- O repositório inclui uma suíte Pytest em `tests/` e um fluxo GitHub Actions (`.github/workflows/tests.yml`) que executa `python -m pytest` e `python src/utils/warning_suppressor.py` em cada push/PR para `master`.

### Execução local
```bash
python3 -m pip install -r requirements.txt
python3 -m pip install pytest
python3 -m pytest
python3 src/utils/warning_suppressor.py  # Verificação complementar
```

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para a branch
5. Abra um Pull Request

## 📄 Licença

Este projeto é parte de um TCC acadêmico.

## 👨‍💻 Autor

**Matheus Ferreira** - TCC 2025

---

**Sistema de Identificação de Pássaros com IA** 🐦✨
