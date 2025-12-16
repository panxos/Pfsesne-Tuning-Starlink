#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pfSense Starlink Tuner - Professional Client
Autor: Francisco Aravena (Asistente IA)
Descripción: Cliente para auditar y optimizar pfSense para Starlink via Cliente-Agente.
"""

import os
import sys
import subprocess
import json
import time
import argparse
from datetime import datetime

# Configuración
Agente_Local = "pfsense_agent.php"
Agente_Remoto = "/tmp/pfsense_agent.php"

# Colores ANSI
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    MAGENTA = '\033[35m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_banner():
    # Banner estilo HUD / Cyberpunk Clean
    c = Colors
    
    print(f"\n{c.CYAN}╔══════════════════════════════════════════════════════════════╗{c.ENDC}")
    print(f"{c.CYAN}║{c.ENDC}  {c.MAGENTA}   _____ __             __    _       __{c.ENDC}                 {c.CYAN}║{c.ENDC}")
    print(f"{c.CYAN}║{c.ENDC}  {c.MAGENTA}  / ___// /_____ ______/ /   (_)___  / /___{c.ENDC}             {c.CYAN}║{c.ENDC}")
    print(f"{c.CYAN}║{c.ENDC}  {c.MAGENTA}  \\__ \\/ __/ __ `/ ___/ /   / / __ \\/ //_/{c.ENDC}              {c.CYAN}║{c.ENDC}")
    print(f"{c.CYAN}║{c.ENDC}  {c.MAGENTA} ___/ / /_/ /_/ / /  / /___/ / / / / ,<{c.ENDC}                 {c.CYAN}║{c.ENDC}")
    print(f"{c.CYAN}║{c.ENDC}  {c.MAGENTA}/____/\\__/\\__,_/_/  /_____/_/_/ /_/_/|_|{c.ENDC}                {c.CYAN}║{c.ENDC}")
    print(f"{c.CYAN}║{c.ENDC}                                                              {c.CYAN}║{c.ENDC}")
    print(f"{c.CYAN}║{c.ENDC}     {c.BOLD}PFSENSE HIGH PERFORMANCE OPTIMIZER {c.BLUE}|{c.ENDC} {c.BOLD}STARLINK EDITION{c.ENDC}    {c.CYAN}║{c.ENDC}")
    print(f"{c.CYAN}╠══════════════════════════════════════════════════════════════╣{c.ENDC}")
    print(f"{c.CYAN}║{c.ENDC}  {c.BLUE}AUTHOR :{c.ENDC} {c.BOLD}Francisco Aravena{c.ENDC}                                {c.CYAN}║{c.ENDC}")
    print(f"{c.CYAN}║{c.ENDC}  {c.BLUE}GITHUB :{c.ENDC} {c.UNDERLINE}github.com/panxos/Pfsesne-Tuning-Starlink{c.ENDC}        {c.CYAN}║{c.ENDC}")
    print(f"{c.CYAN}╚══════════════════════════════════════════════════════════════╝{c.ENDC}")
    print(f"   {c.FAIL}[ SYSTEM READY ]{c.ENDC}   {c.WARNING}[ SSH SECURE ]{c.ENDC}   {c.GREEN}[ SATELLITE LINK ]{c.ENDC}\n")

def check_dependencies():
    """Verifica si ssh, scp, sshpass están disponibles"""
    if subprocess.call("which ssh > /dev/null", shell=True) != 0:
        print(f"{Colors.FAIL}[Error] No se encontró el comando 'ssh'.{Colors.ENDC}")
        sys.exit(1)
    if subprocess.call("which sshpass > /dev/null", shell=True) != 0:
        print(f"{Colors.WARNING}[Aviso] 'sshpass' no instalado. Si no usa llaves SSH, el script podría fallar.{Colors.ENDC}")
    if not os.path.exists(Agente_Local):
        print(f"{Colors.FAIL}[Error] No se encontró el archivo del agente '{Agente_Local}'.{Colors.ENDC}")
        sys.exit(1)
        
def download_local_backup(host, user, password):
    """Descarga config.xml localmente antes de aplicar cambios"""
    backup_dir = "backups"
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        
    filename = f"config-{host}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xml"
    local_path = os.path.join(backup_dir, filename)
    remote_path = "/conf/config.xml"
    
    print(f"{Colors.CYAN}[Backup] Descargando respaldo local a {local_path}...{Colors.ENDC}")
    
    base_cmd = get_ssh_cmd_prefix(password)
    # SCP con -O y -q por si acaso
    scp_cmd = base_cmd + [
        "scp", "-o", "StrictHostKeyChecking=no", "-O", "-q",
        f"{user}@{host}:{remote_path}", local_path
    ]
    
    result = subprocess.run(scp_cmd, capture_output=True)
    if result.returncode == 0:
        print(f"{Colors.GREEN}[✓] Backup guardado exitosamente.{Colors.ENDC}")
        return True
    else:
        print(f"{Colors.FAIL}[!] Error descargando backup: {result.stderr.decode()}{Colors.ENDC}")
        # Intentar sin -O si falló
        scp_cmd.remove("-O")
        result_retry = subprocess.run(scp_cmd, capture_output=True)
        if result_retry.returncode == 0:
             print(f"{Colors.GREEN}[✓] Backup guardado (protocolo SFTP).{Colors.ENDC}")
             return True
             
        return False

def get_ssh_cmd_prefix(password):
    """Retorna el prefijo para usar sshpass si hay password"""
    if password:
        return ["sshpass", "-p", password]
    return []

def ssh_exec(host, user, password, command):
    """Ejecuta un comando via SSH y retorna la salida"""
    base_cmd = get_ssh_cmd_prefix(password)
    ssh_cmd = base_cmd + [
        "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
        f"{user}@{host}", command
    ]
    try:
        result = subprocess.run(ssh_cmd, capture_output=True, text=True)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        return "", str(e), -1

def upload_agent(host, user, password):
    """Sube el agente PHP al pfSense con reintentos y compatibilidad legacy"""
    print(f"{Colors.BLUE}[*] Subiendo agente al pfSense ({host})...{Colors.ENDC}")
    base_cmd = get_ssh_cmd_prefix(password)
    
    # Intento 1: SCP estándar (puede usar SFTP) + Quiet
    scp_cmd = base_cmd + [
        "scp", "-o", "StrictHostKeyChecking=no", "-q",
        Agente_Local, f"{user}@{host}:{Agente_Remoto}"
    ]
    
    result = subprocess.run(scp_cmd, capture_output=True)
    if result.returncode == 0:
        return True
        
    # Si falla, probar con legacy SCP (-O) para compatibilidad con servidores antiguos
    print(f"{Colors.WARNING}[Debug] SCP estándar falló (código {result.returncode}), reintentando con protocolo Legacy (-O)...{Colors.ENDC}")
    scp_cmd_legacy = scp_cmd + ["-O"]
    
    result_legacy = subprocess.run(scp_cmd_legacy, capture_output=True)
    if result_legacy.returncode == 0:
         print(f"{Colors.GREEN}[Debug] Transferencia Legacy exitosa.{Colors.ENDC}")
         return True

    # Si ambos fallan, mostrar error del primero que suele ser más descriptivo
    print(f"{Colors.FAIL}[!] Error subiendo agente: {result.stderr.decode()}{Colors.ENDC}")
    if result.stdout: print(f"Stdout: {result.stdout.decode()}")
    return False

def remove_agent(host, user, password):
    """Limpia el agente del pfSense"""
    ssh_exec(host, user, password, f"rm -f {Agente_Remoto}")

def run_agent_action(host, user, password, action):
    """Ejecuta una acción del agente y parsea el JSON"""
    if not upload_agent(host, user, password):
        return None

def run_agent_action(host, user, password, action):
    """Ejecuta una acción del agente y parsea el JSON"""
    if not upload_agent(host, user, password):
        return None

    print(f"{Colors.BLUE}[*] Ejecutando: {action}...{Colors.ENDC}")
    
    # Usar ruta absoluta y forzar include_path para asegurar que encuentre las librerías de pfSense
    includes = "/etc/inc:/usr/local/www:/usr/local/captiveportal:/usr/local/pkg"
    cmd = f"/usr/local/bin/php -d include_path='{includes}' {Agente_Remoto} {action}"
    
    stdout, stderr, code = ssh_exec(host, user, password, cmd)
    
    # Debug si falla
    if code != 0:
        print(f"{Colors.WARNING}[Debug] Exit Code: {code}{Colors.ENDC}")

    # Limpiamos salidas extrañas (a veces pfSense imprime banners)
    try:
        # Buscamos el inicio del JSON
        json_start = stdout.find('{')
        json_end = stdout.rfind('}') + 1
        if json_start != -1 and json_end != -1:
            json_str = stdout[json_start:json_end]
            data = json.loads(json_str)
            remove_agent(host, user, password)
            return data
        else:
            print(f"{Colors.FAIL}[!] Error: La respuesta no es JSON válido.{Colors.ENDC}")
            print(f"Salida Raw: '{stdout}'") 
            
            if stderr: 
                print(f"{Colors.WARNING}--- STDERR ---{Colors.ENDC}")
                # Filtrar línea por línea
                for line in stderr.splitlines():
                    if "post-quantum" in line or "store now, decrypt later" in line or "openssh.com" in line:
                        continue
                    print(line)
                print(f"{Colors.WARNING}--------------{Colors.ENDC}")
                
            remove_agent(host, user, password)
            return None
    except json.JSONDecodeError:
        print(f"{Colors.FAIL}[!] Error decodificando JSON.{Colors.ENDC}")
        print(f"Salida: {stdout}")
        remove_agent(host, user, password)
        return None
    except json.JSONDecodeError:
        print(f"{Colors.FAIL}[!] Error decodificando JSON.{Colors.ENDC}")
        print(f"Salida: {stdout}")
        remove_agent(host, user, password)
        return None

def show_audit_report(data):
    if not data or 'data' not in data:
        print("No hay datos de reporte.")
        return

    report = data['data'].get('report', {})
    score = data['data'].get('score', 0)
    
    print("\n" + f"{Colors.HEADER}--- RESULTADOS DE AUDITORÍA ---{Colors.ENDC}")
    for key, item in report.items():
        status = item['status']
        msg = item['msg']
        
        if status == 'PASS':
            symbol = f"{Colors.GREEN}[✓] OPTIMIZADO{Colors.ENDC}"
        elif status == 'WARN':
            symbol = f"{Colors.WARNING}[!] MEJORABLE{Colors.ENDC}"
        else:
            symbol = f"{Colors.FAIL}[✗] PENDIENTE{Colors.ENDC}"
            
        print(f"{symbol} : {msg}")
        if status != 'PASS' and 'fix' in item:
            print(f"    -> Recomendación: {item['fix']}")
            
    # Calcular color del score
    score_color = Colors.GREEN
    if score < 80: score_color = Colors.WARNING
    if score < 50: score_color = Colors.FAIL
    
    print(f"\nPUNTUACIÓN DE OPTIMIZACIÓN: {score_color}{score}/100{Colors.ENDC}")

def show_security_report(data):
    if not data or 'data' not in data:
        return

    issues = data['data'].get('issues', [])
    print("\n" + f"{Colors.HEADER}--- AUDITORÍA DE SEGURIDAD ---{Colors.ENDC}")
    
    if not issues:
        print(f"{Colors.GREEN}[✓] No se detectaron problemas de seguridad obvios.{Colors.ENDC}")
    else:
        for issue in issues:
            sev = issue['severity']
            color = Colors.WARNING
            if sev == 'HIGH' or sev == 'CRITICAL': color = Colors.FAIL
            print(f"{color}[{sev}] {issue['msg']}{Colors.ENDC}")

def main():
    print_banner()
    check_dependencies()
    
    parser = argparse.ArgumentParser(description='Herramienta de Optimización pfSense Starlink')
    parser.add_argument('--host', help='Dirección IP del pfSense', default='192.168.1.1')
    parser.add_argument('--user', help='Usuario SSH (root/admin)', default='root')
    parser.add_argument('--password', help='Contraseña SSH (opcional)', default=None)
    args = parser.parse_args()

    host = args.host
    user = args.user
    password = args.password
    
    # Si no hay password y sshpass está instalado, preguntar
    if not password and subprocess.call("which sshpass > /dev/null", shell=True) == 0:
        print(f"{Colors.WARNING}Nota: Si usa llaves SSH, presione Enter.{Colors.ENDC}")
        import getpass
        password = getpass.getpass(f"Contraseña para {user}@{host}: ")
        if not password: password = None

    while True:
        print("\nOpciones:")
        print("1. Auditar Configuración (Starlink Tuning)")
        print("2. Escaneo de Seguridad Básico")
        print("3. Aplicar Optimizaciones (Requiere confirmación)")
        print(f"4. Restaurar Backup Anterior (Rollback)")
        print(f"{Colors.WARNING}5. Aplicar Modo ULTRA (Reinicia Configuración de Arranque){Colors.ENDC}")
        print("0. Salir")
        
        choice = input(f"\nSeleccione una opción [{host}]: ")
        
        if choice == '1':
            res = run_agent_action(host, user, password, 'audit')
            if res: show_audit_report(res)
            
        elif choice == '2':
            res = run_agent_action(host, user, password, 'security')
            if res: show_security_report(res)
            
        elif choice == '3':
            confirm = input(f"{Colors.WARNING}¿Está seguro de aplicar cambios en {host}? Se creará un backup. (s/n): {Colors.ENDC}")
            if confirm.lower() == 's':
                # Descargar backup local primero
                download_local_backup(host, user, password)
                
                res = run_agent_action(host, user, password, 'apply')
                if res and res['status'] == 'success':
                    print(f"\n{Colors.GREEN}[Exito] {res['message']}{Colors.ENDC}")
                    for change in res['data']['changes']:
                         print(f" + {change}")
                    print("\nSe recomienda reiniciar el pfSense para asegurar que todos los cambios surtan efecto completo.")
                elif res:
                    print(f"\n{Colors.FAIL}[Error] {res['message']}{Colors.ENDC}")
                    
        elif choice == '4':
            confirm = input(f"{Colors.FAIL}¿Desea restaurar la configuración anterior? (s/n): {Colors.ENDC}")
            if confirm.lower() == 's':
                res = run_agent_action(host, user, password, 'restore')
                if res and res['status'] == 'success':
                     print(f"\n{Colors.GREEN}[Rollback] {res['message']}{Colors.ENDC}")
                elif res:
                     print(f"\n{Colors.FAIL}[Error] {res['message']}{Colors.ENDC}")

        elif choice == '5':
            print(f"\n{Colors.FAIL}!!! ADVERTENCIA: MODO ULTRA !!!{Colors.ENDC}")
            print("Este modo modifica archivos de arranque del sistema (/boot/loader.conf).")
            print("Es necesario para soportar +1Gbps y ultra-baja latencia.")
            print("REQUIERE REINICIO DEL EQUIPO PARA APLICARSE.")
            confirm = input(f"¿Está 100% seguro de continuar? (escriba 'si'): ")
            if confirm.lower() == 'si':
                # Descargar backup local primero
                download_local_backup(host, user, password)

                res = run_agent_action(host, user, password, 'ultra')
                if res and res['status'] == 'success':
                     print(f"\n{Colors.GREEN}[Exito] {res['message']}{Colors.ENDC}")
                     for change in res['data']['changes']:
                         print(f" + {change}")
                     print(f"\n{Colors.WARNING}DEBE REINICIAR EL PFSENSE MANUALMENTE PARA QUE SURTA EFECTO.{Colors.ENDC}")
                elif res:
                     print(f"\n{Colors.FAIL}[Error] {res['message']}{Colors.ENDC}")

        elif choice == '0':
            print("Saliendo...")
            sys.exit(0)
            
        else:
            print("Opción no válida.")

if __name__ == "__main__":
    main()
