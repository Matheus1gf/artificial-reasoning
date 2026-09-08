> Documento histórico da fase de identificação de pássaros. Para a aplicação conversacional atual, consulte o [README do chatbot](../README.md). Capacidades e resultados descritos aqui não constituem validação do chatbot.

# Guia de Instalação - Sistema IA Neuro-Simbólica

## Pré-requisitos

- **Python 3.8 ou superior**
- **pip** (gerenciador de pacotes Python)
- **Git** (para clonar o repositório)

## Instalação Rápida

### Windows
```bash
# Execute o arquivo de instalação
install_windows.bat
```

### macOS
```bash
# Torne o script executável e execute
chmod +x install_mac.sh
./install_mac.sh
```

### Linux (Ubuntu/Debian/CentOS/Arch)
```bash
# Torne o script executável e execute
chmod +x install_linux.sh
./install_linux.sh
```

## Instalação Manual

### 1. Clonar o repositório
```bash
git clone <url-do-repositorio>
cd tcc_bird-identify
```

### 2. Criar ambiente virtual (recomendado)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar dependências
```bash
# Instalar todas as dependências
pip install -r requirements.txt

# Ou instalar manualmente
pip install numpy==1.24.3
pip install opencv-python==4.8.1.78
pip install tensorflow==2.13.0
pip install ultralytics==8.0.196
pip install matplotlib==3.7.2
pip install scikit-learn==1.3.0
pip install scikit-image==0.21.0
pip install networkx==3.1
pip install requests==2.31.0
pip install pillow==10.0.0
pip install pandas==2.0.3
```

### 4. Dependências opcionais para APIs externas
```bash
# Para Gemini API
pip install google-generativeai==0.3.0

# Para GPT-4V API
pip install openai==0.28.0
```

## Verificação da Instalação

### Teste básico
```bash
python -c "import cv2, numpy, tensorflow, ultralytics, networkx, matplotlib; print('Instalação bem-sucedida!')"
```

### Teste do sistema
```bash
# Sistema básico
python main.py

# Sistema aprimorado
python enhanced_main.py
```

## Solução de Problemas

### Windows

**Problema**: Erro ao instalar OpenCV
```bash
pip install --upgrade pip
pip install --force-reinstall opencv-python
```

**Problema**: Erro de Visual C++
- Instale Microsoft Visual C++ Redistributable
- Ou use conda: `conda install opencv`

### macOS

**Problema**: Erro com OpenCV
```bash
brew install opencv
pip install opencv-python
```

**Problema**: Erro com TensorFlow
```bash
pip install --upgrade tensorflow
```

### Linux

**Problema**: Dependências do sistema faltando
```bash
# Ubuntu/Debian
sudo apt install python3-dev python3-tk libgl1-mesa-glx

# CentOS/RHEL
sudo yum install python3-devel tkinter mesa-libGL

# Arch Linux
sudo pacman -S python-tk mesa-libgl
```

**Problema**: OpenCV não funciona
```bash
sudo apt install python3-opencv
# Ou
pip install --force-reinstall opencv-python
```

## Configuração de APIs Externas

### Gemini API
1. Obtenha uma chave da API em: https://makersuite.google.com/app/apikey
2. Configure no `enhanced_main.py`:
```python
API_KEY_GEMINI = "sua_chave_aqui"
```

### GPT-4V API
1. Obtenha uma chave da API em: https://platform.openai.com/api-keys
2. Configure no `enhanced_main.py`:
```python
API_KEY_GPT4V = "sua_chave_aqui"
```

## Estrutura de Arquivos

```
tcc_bird-identify/
├── install_windows.bat      # Instalação para Windows
├── install_mac.sh          # Instalação para macOS
├── install_linux.sh        # Instalação para Linux
├── requirements.txt        # Lista de dependências
├── INSTALACAO.md          # Este arquivo
├── main.py                # Sistema básico
├── enhanced_main.py       # Sistema aprimorado
├── knowledge_graph.py     # Grafo de conhecimento
├── gradcam_module.py      # Grad-CAM e auto-anotação
├── continuous_learning.py # Aprendizado contínuo
├── innovation_module.py   # Módulo de inovação
└── dataset_teste/         # Imagens para teste
```

## Comandos Úteis

### Atualizar dependências
```bash
pip install --upgrade -r requirements.txt
```

### Verificar versões instaladas
```bash
pip list
```

### Desinstalar e reinstalar
```bash
pip uninstall -r requirements.txt -y
pip install -r requirements.txt
```

### Limpar cache do pip
```bash
pip cache purge
```

## Suporte

Se encontrar problemas:

1. **Verifique a versão do Python**: `python --version`
2. **Atualize o pip**: `pip install --upgrade pip`
3. **Use ambiente virtual**: Sempre recomendado
4. **Consulte os logs**: Os scripts de instalação mostram erros detalhados
5. **Teste individualmente**: Instale cada pacote separadamente para identificar problemas

## Próximos Passos

Após a instalação:

1. **Execute o sistema básico**: `python main.py`
2. **Teste o sistema aprimorado**: `python enhanced_main.py`
3. **Configure APIs externas** (opcional)
4. **Leia o ROADMAP_DESENVOLVIMENTO.md** para próximos passos
