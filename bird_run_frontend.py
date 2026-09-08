#!/usr/bin/env python3
"""
Script histórico de inicialização da interface de identificação de pássaros
"""

import subprocess
import sys
import os

def check_dependencies():
    """Verifica se as dependências estão instaladas"""
    try:
        import streamlit
        import plotly
        print("Streamlit e Plotly instalados")
        return True
    except ImportError as e:
        print(f"Dependência faltando: {e}")
        return False

def install_dependencies():
    """Instala as dependências necessárias"""
    print("Instalando dependências do frontend...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "streamlit", "plotly"])
        print("Dependências instaladas com sucesso!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Erro ao instalar dependências: {e}")
        return False

def run_frontend():
    """Executa o frontend"""
    print("Iniciando Logical AI Reasoning System...")
    print("Frontend será aberto em: http://localhost:8501")
    print("Pressione Ctrl+C para parar")
    print("=" * 50)
    
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", "bird_app.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Erro ao executar frontend: {e}")
    except KeyboardInterrupt:
        print("\nFrontend encerrado pelo usuário")

def main():
    """Função principal"""
    print("LOGICAL AI REASONING SYSTEM - FRONTEND")
    print("=" * 50)
    
    # Verificar dependências
    if not check_dependencies():
        print("Instalando dependências necessárias...")
        if not install_dependencies():
            print("Não foi possível instalar as dependências")
            return
    
    # Executar frontend
    run_frontend()

if __name__ == "__main__":
    main()
