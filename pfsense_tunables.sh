#!/bin/sh
#===============================================================================
# pfSense/FreeBSD Network Tunables Script
# Autor: Francisco Aravena
# Descripción: Aplica tunables de red optimizados para Starlink/alta latencia
#              con soporte para backup y rollback
#===============================================================================

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Directorios y archivos
BACKUP_DIR="/root/tunables_backup"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/sysctl_backup_${TIMESTAMP}.conf"
LOADER_BACKUP="${BACKUP_DIR}/loader_backup_${TIMESTAMP}.conf"
LATEST_BACKUP="${BACKUP_DIR}/latest_backup.conf"
LATEST_LOADER="${BACKUP_DIR}/latest_loader.conf"

# Crear directorio de backup si no existe
mkdir -p "$BACKUP_DIR"

#===============================================================================
# TUNABLES A APLICAR
#===============================================================================

# Sysctl tunables (se aplican en caliente)
SYSCTL_TUNABLES="
net.inet.tcp.recvbuf_max=4194304
net.inet.tcp.sendbuf_max=4194304
net.inet.tcp.recvbuf_auto=1
net.inet.tcp.sendbuf_auto=1
net.inet.tcp.recvbuf_inc=65536
net.inet.tcp.sendbuf_inc=65536
net.inet.tcp.rfc1323=1
net.inet.ip.intr_queue_maxlen=1024
net.inet.tcp.delayed_ack=0
net.inet.tcp.mssdflt=1460
"

# Loader tunables (requieren reboot)
LOADER_TUNABLES="
kern.ipc.nmbclusters=1000000
kern.ipc.maxsockbuf=16777216
net.isr.maxthreads=-1
net.isr.bindthreads=1
"

#===============================================================================
# FUNCIONES
#===============================================================================

print_header() {
    echo ""
    echo "${BLUE}============================================================${NC}"
    echo "${BLUE} $1${NC}"
    echo "${BLUE}============================================================${NC}"
    echo ""
}

print_success() {
    echo "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo "${RED}[✗]${NC} $1"
}

print_info() {
    echo "${BLUE}[i]${NC} $1"
}

# Verificar si es root
check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        print_error "Este script debe ejecutarse como root"
        exit 1
    fi
}

# Backup de valores actuales de sysctl
backup_sysctl() {
    print_info "Guardando valores actuales de sysctl..."
    
    echo "# Backup de sysctl - ${TIMESTAMP}" > "$BACKUP_FILE"
    echo "# Generado automáticamente - NO EDITAR" >> "$BACKUP_FILE"
    echo "" >> "$BACKUP_FILE"
    
    for tunable in $SYSCTL_TUNABLES; do
        key=$(echo "$tunable" | cut -d'=' -f1)
        current_value=$(sysctl -n "$key" 2>/dev/null)
        if [ -n "$current_value" ]; then
            echo "${key}=${current_value}" >> "$BACKUP_FILE"
            print_success "Backup: ${key}=${current_value}"
        else
            print_warning "No se pudo obtener valor de: $key"
        fi
    done
    
    # Guardar como último backup
    cp "$BACKUP_FILE" "$LATEST_BACKUP"
    print_success "Backup guardado en: $BACKUP_FILE"
}

# Backup de loader.conf
backup_loader() {
    print_info "Guardando configuración de loader..."
    
    if [ -f "/boot/loader.conf.local" ]; then
        cp "/boot/loader.conf.local" "$LOADER_BACKUP"
        cp "/boot/loader.conf.local" "$LATEST_LOADER"
        print_success "Backup de loader.conf.local guardado"
    else
        echo "# No existía loader.conf.local previo" > "$LOADER_BACKUP"
        cp "$LOADER_BACKUP" "$LATEST_LOADER"
        print_warning "No existía /boot/loader.conf.local previo"
    fi
}

# Aplicar tunables de sysctl
apply_sysctl() {
    print_header "APLICANDO TUNABLES DE SYSCTL"
    
    failed=0
    for tunable in $SYSCTL_TUNABLES; do
        key=$(echo "$tunable" | cut -d'=' -f1)
        value=$(echo "$tunable" | cut -d'=' -f2)
        
        if sysctl "$tunable" > /dev/null 2>&1; then
            new_value=$(sysctl -n "$key")
            print_success "${key} = ${new_value}"
        else
            print_error "Falló: $tunable"
            failed=$((failed + 1))
        fi
    done
    
    if [ $failed -gt 0 ]; then
        print_warning "$failed tunables fallaron"
        return 1
    fi
    return 0
}

# Aplicar tunables de loader (para próximo reboot)
apply_loader() {
    print_header "CONFIGURANDO LOADER TUNABLES (requiere reboot)"
    
    LOADER_FILE="/boot/loader.conf.local"
    
    # Crear archivo si no existe
    touch "$LOADER_FILE"
    
    for tunable in $LOADER_TUNABLES; do
        key=$(echo "$tunable" | cut -d'=' -f1)
        value=$(echo "$tunable" | cut -d'=' -f2)
        
        # Remover entrada existente si la hay
        if grep -q "^${key}=" "$LOADER_FILE" 2>/dev/null; then
            # Usar sed compatible con FreeBSD
            sed -i '' "/^${key}=/d" "$LOADER_FILE"
        fi
        
        # Agregar nueva entrada
        echo "${key}=\"${value}\"" >> "$LOADER_FILE"
        print_success "Configurado: ${key}=\"${value}\""
    done
    
    print_warning "Los loader tunables se aplicarán después del próximo reboot"
}

# Rollback de sysctl
rollback_sysctl() {
    print_header "ROLLBACK DE SYSCTL"
    
    if [ ! -f "$LATEST_BACKUP" ]; then
        print_error "No se encontró backup para restaurar"
        print_info "Buscando backups disponibles..."
        ls -la "$BACKUP_DIR"/*.conf 2>/dev/null || echo "No hay backups"
        return 1
    fi
    
    print_info "Restaurando desde: $LATEST_BACKUP"
    
    while IFS= read -r line; do
        # Saltar comentarios y líneas vacías
        case "$line" in
            \#*|"") continue ;;
        esac
        
        if sysctl "$line" > /dev/null 2>&1; then
            print_success "Restaurado: $line"
        else
            print_error "Falló restaurar: $line"
        fi
    done < "$LATEST_BACKUP"
    
    print_success "Rollback de sysctl completado"
}

# Rollback de loader
rollback_loader() {
    print_header "ROLLBACK DE LOADER"
    
    if [ ! -f "$LATEST_LOADER" ]; then
        print_error "No se encontró backup de loader para restaurar"
        return 1
    fi
    
    cp "$LATEST_LOADER" "/boot/loader.conf.local"
    print_success "Restaurado /boot/loader.conf.local"
    print_warning "Los cambios de loader se aplicarán después del próximo reboot"
}

# Mostrar valores actuales
show_current() {
    print_header "VALORES ACTUALES DE SYSCTL"
    
    for tunable in $SYSCTL_TUNABLES; do
        key=$(echo "$tunable" | cut -d'=' -f1)
        current=$(sysctl -n "$key" 2>/dev/null || echo "N/A")
        recommended=$(echo "$tunable" | cut -d'=' -f2)
        
        if [ "$current" = "$recommended" ]; then
            echo "${GREEN}[OK]${NC} ${key} = ${current}"
        else
            echo "${YELLOW}[!=]${NC} ${key} = ${current} (recomendado: ${recommended})"
        fi
    done
    
    echo ""
    print_header "CONFIGURACIÓN DE LOADER"
    
    if [ -f "/boot/loader.conf.local" ]; then
        cat "/boot/loader.conf.local"
    else
        print_info "No existe /boot/loader.conf.local"
    fi
}

# Test de conectividad
test_network() {
    print_header "TEST DE CONECTIVIDAD"
    
    print_info "Probando conexión a Internet..."
    
    # Test DNS
    if host google.com > /dev/null 2>&1; then
        print_success "DNS funcionando"
    else
        print_error "DNS no responde"
        return 1
    fi
    
    # Test ping
    if ping -c 3 8.8.8.8 > /dev/null 2>&1; then
        print_success "Ping a 8.8.8.8 exitoso"
        ping -c 3 8.8.8.8 | tail -1
    else
        print_error "Ping falló"
        return 1
    fi
    
    # Test ping a 1.1.1.1
    if ping -c 3 1.1.1.1 > /dev/null 2>&1; then
        print_success "Ping a 1.1.1.1 exitoso"
    fi
    
    return 0
}

# Listar backups disponibles
list_backups() {
    print_header "BACKUPS DISPONIBLES"
    
    if [ -d "$BACKUP_DIR" ]; then
        ls -lah "$BACKUP_DIR"/ 2>/dev/null || print_info "No hay backups"
    else
        print_info "Directorio de backups no existe"
    fi
}

# Restaurar desde backup específico
restore_specific() {
    backup_file="$1"
    
    if [ ! -f "$backup_file" ]; then
        print_error "Archivo no encontrado: $backup_file"
        return 1
    fi
    
    print_header "RESTAURANDO DESDE: $backup_file"
    
    while IFS= read -r line; do
        case "$line" in
            \#*|"") continue ;;
        esac
        
        if sysctl "$line" > /dev/null 2>&1; then
            print_success "Restaurado: $line"
        else
            print_error "Falló: $line"
        fi
    done < "$backup_file"
}

# Mostrar ayuda
show_help() {
    echo ""
    echo "USO: $0 [OPCIÓN]"
    echo ""
    echo "OPCIONES:"
    echo "  apply       - Aplicar todos los tunables (con backup automático)"
    echo "  apply-test  - Aplicar tunables y testear, rollback automático si falla"
    echo "  rollback    - Restaurar último backup"
    echo "  show        - Mostrar valores actuales vs recomendados"
    echo "  test        - Ejecutar test de conectividad"
    echo "  list        - Listar backups disponibles"
    echo "  restore FILE- Restaurar desde backup específico"
    echo "  sysctl-only - Solo aplicar sysctl (sin loader)"
    echo "  loader-only - Solo configurar loader tunables"
    echo "  help        - Mostrar esta ayuda"
    echo ""
    echo "EJEMPLOS:"
    echo "  $0 show              # Ver estado actual"
    echo "  $0 apply-test        # Aplicar con test automático"
    echo "  $0 rollback          # Revertir cambios"
    echo "  $0 restore /root/tunables_backup/sysctl_backup_20241215_120000.conf"
    echo ""
}

# Aplicar con test automático
apply_with_test() {
    print_header "APLICACIÓN CON TEST AUTOMÁTICO"
    
    # Backup primero
    backup_sysctl
    backup_loader
    
    # Aplicar sysctl
    if ! apply_sysctl; then
        print_error "Algunos tunables fallaron, pero continuando..."
    fi
    
    # Esperar un momento
    sleep 2
    
    # Test de red
    print_info "Esperando 5 segundos antes del test..."
    sleep 5
    
    if test_network; then
        print_success "Test de red exitoso - cambios aplicados correctamente"
        
        # Preguntar si aplicar loader tunables
        echo ""
        print_warning "¿Desea también configurar los loader tunables? (requiere reboot)"
        printf "Responder [s/N]: "
        read -r response
        
        case "$response" in
            [sS]|[sS][iI])
                apply_loader
                ;;
            *)
                print_info "Loader tunables no modificados"
                ;;
        esac
    else
        print_error "Test de red falló - iniciando rollback automático"
        rollback_sysctl
        print_warning "Se han restaurado los valores anteriores"
        return 1
    fi
}

#===============================================================================
# MAIN
#===============================================================================

check_root

case "$1" in
    apply)
        backup_sysctl
        backup_loader
        apply_sysctl
        apply_loader
        ;;
    apply-test)
        apply_with_test
        ;;
    rollback)
        rollback_sysctl
        rollback_loader
        ;;
    show)
        show_current
        ;;
    test)
        test_network
        ;;
    list)
        list_backups
        ;;
    restore)
        if [ -z "$2" ]; then
            print_error "Debe especificar el archivo de backup"
            list_backups
            exit 1
        fi
        restore_specific "$2"
        ;;
    sysctl-only)
        backup_sysctl
        apply_sysctl
        ;;
    loader-only)
        backup_loader
        apply_loader
        ;;
    help|--help|-h|"")
        show_help
        ;;
    *)
        print_error "Opción desconocida: $1"
        show_help
        exit 1
        ;;
esac

echo ""
print_info "Script finalizado"
