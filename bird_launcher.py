#!/usr/bin/env python3
"""
Launcher histórico - Sistema de Identificação de Pássaros
Versão: 2.0
Autor: Sistema de IA Neuro-Simbólica
Data: 2025-09-23

Este launcher executa automaticamente:
1. Detecção do sistema operacional
2. Verificação e instalação de dependências
3. Inicialização do sistema
4. Abertura automática do navegador
5. Log detalhado em tempo real
"""

import os
import sys
import platform
import subprocess
import time
import webbrowser
import threading
import json
from datetime import datetime
from pathlib import Path

class Colors:
    """Cores para o terminal"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

class UniversalLauncher:
    def __init__(self):
        self.start_time = datetime.now()
        self.os_system = platform.system().lower()
        self.os_release = platform.release()
        self.python_version = sys.version
        self.project_root = Path(__file__).parent
        self.log_file = self.project_root / "launcher.log"
        self.requirements_file = self.project_root / "requirements-birds.txt"
        self.main_file = self.project_root / "bird_main.py"
        
        # Configurações por sistema operacional
        self.os_config = {
            'windows': {
                'python_cmd': 'python',
                'pip_cmd': 'pip',
                'browser_cmd': 'start',
                'kill_cmd': 'taskkill /F /IM python.exe'
            },
            'darwin': {  # macOS
                'python_cmd': 'python3',
                'pip_cmd': 'pip3',
                'browser_cmd': 'open',
                'kill_cmd': 'pkill -f streamlit'
            },
            'linux': {
                'python_cmd': 'python3',
                'pip_cmd': 'pip3',
                'browser_cmd': 'xdg-open',
                'kill_cmd': 'pkill -f streamlit'
            }
        }
        
        self.config = self.os_config.get(self.os_system, self.os_config['linux'])
        
    def log(self, message, level="INFO", color=Colors.WHITE):
        """Log com timestamp e cores"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_message = f"[{timestamp}] [{level}] {message}"
        
        # Exibir no terminal com cores
        print(f"{color}[{timestamp}] {level}: {message}{Colors.END}")
        
        # Salvar no arquivo de log
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"{log_message}\n")
    
    def log_success(self, message):
        """Log de sucesso"""
        self.log(f"✅ {message}", "SUCCESS", Colors.GREEN)
    
    def log_error(self, message):
        """Log de erro"""
        self.log(f"❌ {message}", "ERROR", Colors.RED)
    
    def log_warning(self, message):
        """Log de aviso"""
        self.log(f"⚠️ {message}", "WARNING", Colors.YELLOW)
    
    def log_info(self, message):
        """Log de informação"""
        self.log(f"ℹ️ {message}", "INFO", Colors.CYAN)
    
    def log_step(self, step, message):
        """Log de etapa"""
        self.log(f"🔄 ETAPA {step}: {message}", "STEP", Colors.BLUE)
    
    def run_command(self, command, description="", check=True):
        """Executa comando com log detalhado"""
        self.log_info(f"Executando: {description or command}")
        
        try:
            if isinstance(command, str):
                result = subprocess.run(
                    command.split(),
                    capture_output=True,
                    text=True,
                    check=check
                )
            else:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    check=check
                )
            
            if result.stdout:
                self.log_info(f"Saída: {result.stdout.strip()}")
            
            if result.stderr and result.stderr.strip():
                self.log_warning(f"Stderr: {result.stderr.strip()}")
            
            return result.returncode == 0, result
        
        except subprocess.CalledProcessError as e:
            self.log_error(f"Erro ao executar comando: {e}")
            if e.stdout:
                self.log_info(f"Stdout: {e.stdout}")
            if e.stderr:
                self.log_error(f"Stderr: {e.stderr}")
            return False, e
        except Exception as e:
            self.log_error(f"Erro inesperado: {e}")
            return False, e
    
    def detect_os(self):
        """ETAPA 1: Detectar sistema operacional"""
        self.log_step(1, "Detectando sistema operacional")
        
        self.log_info(f"Sistema: {self.os_system}")
        self.log_info(f"Release: {self.os_release}")
        self.log_info(f"Arquitetura: {platform.machine()}")
        self.log_info(f"Python: {self.python_version}")
        
        if self.os_system not in self.os_config:
            self.log_warning(f"Sistema operacional '{self.os_system}' não reconhecido, usando configuração Linux")
            self.os_system = 'linux'
        
        self.log_success(f"Sistema operacional detectado: {self.os_system.upper()}")
        return True
    
    def check_python(self):
        """ETAPA 2: Verificar Python"""
        self.log_step(2, "Verificando Python")
        
        python_cmd = self.config['python_cmd']
        success, result = self.run_command(f"{python_cmd} --version", "Verificando versão do Python")
        
        if not success:
            self.log_error("Python não encontrado!")
            return False
        
        self.log_success("Python encontrado e funcionando")
        return True
    
    def check_dependencies(self):
        """ETAPA 3: Verificar dependências"""
        self.log_step(3, "Verificando dependências")
        
        if not self.requirements_file.exists():
            self.log_error(f"Arquivo {self.requirements_file} não encontrado!")
            return False
        
        self.log_info("Lendo arquivo requirements.txt")
        with open(self.requirements_file, 'r') as f:
            requirements = f.read().strip().split('\n')
        
        self.log_info(f"Encontradas {len(requirements)} dependências")
        
        pip_cmd = self.config['pip_cmd']
        
        # Verificar se pip está funcionando
        success, result = self.run_command(f"{pip_cmd} --version", "Verificando pip")
        if not success:
            self.log_error("pip não encontrado!")
            return False
        
        self.log_success("pip encontrado e funcionando")
        return True
    
    def install_dependencies(self):
        """ETAPA 4: Instalar/atualizar dependências"""
        self.log_step(4, "Instalando/atualizando dependências")
        
        pip_cmd = self.config['pip_cmd']
        
        # Atualizar pip primeiro
        self.log_info("Atualizando pip...")
        success, result = self.run_command(f"{pip_cmd} install --upgrade pip", "Atualizando pip", check=False)
        
        # Instalar dependências
        self.log_info("Instalando dependências do requirements.txt...")
        success, result = self.run_command(
            f"{pip_cmd} install -r {self.requirements_file}",
            "Instalando dependências",
            check=False
        )
        
        if success:
            self.log_success("Dependências instaladas com sucesso")
        else:
            self.log_warning("Algumas dependências podem ter falhado, mas continuando...")
        
        return True
    
    def check_errors(self):
        """ETAPA 5: Verificar erros"""
        self.log_step(5, "Verificando erros")
        
        # Verificar se main.py existe
        if not self.main_file.exists():
            self.log_error(f"Arquivo {self.main_file} não encontrado!")
            return False
        
        # Verificar se src/ existe
        src_dir = self.project_root / "src"
        if not src_dir.exists():
            self.log_error("Diretório src/ não encontrado!")
            return False
        
        # Testar importação básica
        self.log_info("Testando importações básicas...")
        python_cmd = self.config['python_cmd']
        
        test_script = """
import sys
sys.path.insert(0, 'src')
try:
    from core.intuition import IntuitionEngine
    print("✅ IntuitionEngine importado com sucesso")
except Exception as e:
    print(f"❌ Erro ao importar IntuitionEngine: {e}")
    sys.exit(1)
"""
        
        success, result = self.run_command(
            [python_cmd, "-c", test_script],
            "Testando importações",
            check=False
        )
        
        if success:
            self.log_success("Importações funcionando corretamente")
        else:
            self.log_warning("Alguns problemas de importação detectados, mas continuando...")
        
        return True
    
    def start_system(self):
        """ETAPA 6: Iniciar sistema"""
        self.log_step(6, "Iniciando sistema")
        
        # Parar processos anteriores se existirem
        self.log_info("Verificando processos anteriores...")
        success, result = self.run_command(
            self.config['kill_cmd'],
            "Parando processos anteriores",
            check=False
        )
        
        # Aguardar um pouco
        time.sleep(2)
        
        # Iniciar Streamlit
        python_cmd = self.config['python_cmd']
        self.log_info("Iniciando Streamlit...")
        
        # Comando para iniciar Streamlit
        streamlit_cmd = [
            python_cmd, "-m", "streamlit", "run", "bird_main.py",
            "--server.port", "8501",
            "--server.headless", "true"
        ]
        
        self.log_info(f"Comando: {' '.join(streamlit_cmd)}")
        
        # Iniciar em background
        try:
            process = subprocess.Popen(
                streamlit_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.log_success("Streamlit iniciado em background")
            
            # Aguardar inicialização
            self.log_info("Aguardando inicialização do sistema...")
            time.sleep(8)
            
            # Verificar se está rodando
            success, result = self.run_command(
                f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:8501",
                "Verificando se sistema está rodando",
                check=False
            )
            
            if success and "200" in result.stdout:
                self.log_success("Sistema iniciado com sucesso!")
                return True, process
            else:
                self.log_error("Sistema não respondeu corretamente")
                return False, process
                
        except Exception as e:
            self.log_error(f"Erro ao iniciar sistema: {e}")
            return False, None
    
    def open_browser(self):
        """ETAPA 7: Abrir navegador"""
        self.log_step(7, "Abrindo navegador")
        
        url = "http://localhost:8501"
        self.log_info(f"Abrindo {url} no navegador...")
        
        try:
            webbrowser.open(url)
            self.log_success("Navegador aberto com sucesso")
            return True
        except Exception as e:
            self.log_error(f"Erro ao abrir navegador: {e}")
            return False
    
    def start_monitoring(self, process):
        """ETAPA 8: Monitoramento em tempo real"""
        self.log_step(8, "Iniciando monitoramento em tempo real")
        
        def monitor_process():
            while True:
                try:
                    # Verificar se processo ainda está rodando
                    if process.poll() is not None:
                        self.log_error("Processo Streamlit parou inesperadamente!")
                        break
                    
                    # Verificar status HTTP
                    success, result = self.run_command(
                        f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:8501",
                        "Verificando status HTTP",
                        check=False
                    )
                    
                    if success and "200" in result.stdout:
                        self.log_success("Sistema funcionando normalmente")
                    else:
                        self.log_warning("Sistema pode estar com problemas")
                    
                    time.sleep(30)  # Verificar a cada 30 segundos
                    
                except Exception as e:
                    self.log_error(f"Erro no monitoramento: {e}")
                    time.sleep(30)
        
        # Iniciar thread de monitoramento
        monitor_thread = threading.Thread(target=monitor_process, daemon=True)
        monitor_thread.start()
        
        self.log_success("Monitoramento iniciado")
        return True
    
    def run(self):
        """Executar launcher completo"""
        # Limpar log anterior
        if self.log_file.exists():
            self.log_file.unlink()
        
        self.log_info("=" * 60)
        self.log_info("🚀 LAUNCHER UNIVERSAL - SISTEMA DE IDENTIFICAÇÃO DE PÁSSAROS")
        self.log_info("=" * 60)
        self.log_info(f"Data/Hora: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.log_info(f"Diretório: {self.project_root}")
        self.log_info("=" * 60)
        
        try:
            # Executar etapas
            if not self.detect_os():
                return False
            
            if not self.check_python():
                return False
            
            if not self.check_dependencies():
                return False
            
            if not self.install_dependencies():
                return False
            
            if not self.check_errors():
                return False
            
            success, process = self.start_system()
            if not success:
                return False
            
            if not self.open_browser():
                self.log_warning("Navegador não pôde ser aberto automaticamente")
            
            if not self.start_monitoring(process):
                return False
            
            # Sucesso total
            end_time = datetime.now()
            duration = end_time - self.start_time
            
            self.log_success("=" * 60)
            self.log_success("🎉 SISTEMA INICIADO COM SUCESSO!")
            self.log_success("=" * 60)
            self.log_success(f"Tempo total: {duration.total_seconds():.2f} segundos")
            self.log_success(f"URL: http://localhost:8501")
            self.log_success(f"Log salvo em: {self.log_file}")
            self.log_success("=" * 60)
            
            # Manter processo rodando
            self.log_info("Sistema rodando... Pressione Ctrl+C para parar")
            
            try:
                process.wait()
            except KeyboardInterrupt:
                self.log_info("Parando sistema...")
                process.terminate()
                self.log_success("Sistema parado com sucesso")
            
            return True
            
        except Exception as e:
            self.log_error(f"Erro crítico: {e}")
            return False

def main():
    """Função principal"""
    launcher = UniversalLauncher()
    success = launcher.run()
    
    if not success:
        print(f"\n{Colors.RED}❌ Launcher falhou! Verifique o log: {launcher.log_file}{Colors.END}")
        sys.exit(1)
    else:
        print(f"\n{Colors.GREEN}✅ Launcher executado com sucesso!{Colors.END}")

if __name__ == "__main__":
    main()
