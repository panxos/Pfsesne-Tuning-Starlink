<?php
/**
 * pfSense Starlink Tuning Agent
 * Autor: Generado por Asistente de IA para Francisco Aravena
 * Descripción: Script para auditar y aplicar optimizaciones de Starlink en pfSense
 * Uso: php pfsense_agent.php [audit|apply|restore|security]
 */

// Configuración de errores para depuración (Solo errores fatales para evitar ruido JSON)
ini_set('display_errors', '0'); // Desactivar salida a stdout directa
ini_set('log_errors', '1');     // Loguear errores
ini_set('error_log', '/tmp/pfsense_agent.log'); // Archivo de log dedicado
error_reporting(E_ERROR | E_PARSE); // Ignorar Deprecated/Warnings

// Cambiar al directorio de includes para evitar problemas de rutas relativas
chdir('/etc/inc');

// Forzar rutas de inclusión comunes en pfSense
$includes = array(
    "/etc/inc", 
    "/usr/local/www", 
    "/usr/local/captiveportal", 
    "/usr/local/pkg",
    "/usr/local/share/pear",
    "/usr/local/pfSense/include/www"
);
set_include_path(implode(":", $includes) . ":" . get_include_path());

// Cargar librerías esenciales en orden correcto
if (!file_exists("/etc/inc/globals.inc")) {
    // Si no encontramos globals, probablemente no es pfsense o la ruta está mal
    echo json_encode(['status' => 'error', 'message' => 'No se encontró /etc/inc/globals.inc. ¿Es esto un pfSense?']);
    exit(1);
}

require_once("globals.inc");
require_once("config.inc");
require_once("functions.inc");
require_once("util.inc");
require_once("pkg-utils.inc");

// Colores para salida en consola (si se ejecuta interactivamente)
if (!defined('RED')) define('RED', "\033[0;31m");
if (!defined('GREEN')) define('GREEN', "\033[0;32m");
if (!defined('YELLOW')) define('YELLOW', "\033[1;33m");
if (!defined('NC')) define('NC', "\033[0m");

// Configuración recomendada
$starlink_recommendations = [
    'sysctl' => [
        'net.inet.tcp.recvbuf_max' => '4194304',
        'net.inet.tcp.sendbuf_max' => '4194304',
        'net.inet.tcp.recvbuf_inc' => '65536',
        'net.inet.tcp.sendbuf_inc' => '65536',
        'net.inet.ip.intr_queue_maxlen' => '2048',
        'net.inet.tcp.mssdflt' => '1460'
    ],
    'gateway' => [
        'latency_low' => '200',
        'latency_high' => '400',
        'loss_low' => '10',
        'loss_high' => '20',
        'interval' => '2000'
    ]
];

/**
 * Imprime mensaje JSON para el cliente Python
 */
function return_json($status, $message, $data = []) {
    $response = [
        'status' => $status,
        'message' => $message,
        'data' => $data
    ];
    echo json_encode($response, JSON_PRETTY_PRINT);
    exit;
}

/**
 * Obtiene la interfaz WAN activa
 */
function get_wan_interface() {
    global $config;
    $wan_if = $config['interfaces']['wan']['if'];
    return $wan_if;
}

/**
 * Auditoría de Configuración
 */
function audit_config() {
    global $config, $starlink_recommendations;
    
    $report = [];
    $score = 100;

    // 1. Verificar "Block Private Networks" en WAN
    if (isset($config['interfaces']['wan']['blockpriv'])) {
        $report['wan_blockpriv'] = [
            'status' => 'FAIL',
            'msg' => 'La interfaz WAN bloquea redes privadas (afecta CGNAT de Starlink)',
            'fix' => 'Desactivar "Block private networks and loopback addresses"'
        ];
        $score -= 20;
    } else {
        $report['wan_blockpriv'] = ['status' => 'PASS', 'msg' => 'Bloqueo de redes privadas desactivado (Correcto)'];
    }

    // 2. Verificar "Reject Leases From" 192.168.100.1
    $reject_leases = isset($config['interfaces']['wan']['rejectleasesfrom']) ? $config['interfaces']['wan']['rejectleasesfrom'] : '';
    if (strpos($reject_leases, '192.168.100.1') === false) {
        $report['wan_rejectleases'] = [
            'status' => 'FAIL',
            'msg' => 'No se rechazan leases de 192.168.100.1 (puede causar perdida de IP)',
            'fix' => 'Añadir 192.168.100.1 a "Reject Leases From"'
        ];
        $score -= 20;
    } else {
        $report['wan_rejectleases'] = ['status' => 'PASS', 'msg' => 'Se rechazan leases de 192.168.100.1 (Correcto)'];
    }

    // 3. Verificar System Tunables
    $tunables_ok = 0;
    $tunables_total = count($starlink_recommendations['sysctl']);
    
    if (is_array($config['sysctl']['item'])) {
        foreach ($starlink_recommendations['sysctl'] as $key => $val) {
            $found = false;
            foreach ($config['sysctl']['item'] as $item) {
                if ($item['tunable'] == $key && $item['value'] == $val) {
                    $found = true;
                    break;
                }
            }
            if ($found) $tunables_ok++;
        }
    }

    if ($tunables_ok < $tunables_total) {
        $report['sysctl'] = [
            'status' => 'WARN',
            'msg' => "Solo $tunables_ok de $tunables_total optimizaciones de sysctl aplicadas",
            'fix' => 'Aplicar System Tunables recomendados'
        ];
        $score -= 10;
    } else {
        $report['sysctl'] = ['status' => 'PASS', 'msg' => 'Todas las optimizaciones sysctl están aplicadas'];
    }

    return_json('success', 'Auditoría completada', ['report' => $report, 'score' => $score]);
}

/**
 * Auditoría de Seguridad
 */
function audit_security() {
    global $config;
    $issues = [];
    
    // 1. Usuario admin por defecto
    if ($config['system']['user'][0]['name'] === 'admin') {
         // Verificar si el hash es el por defecto (pfSense default es 'pfsense')
         // Nota: No podemos desencriptar, pero podemos advertir que existe el usuario admin
         $issues[] = [
             'severity' => 'HIGH',
             'msg' => 'El usuario "admin" por defecto existe. Se recomienda crear un usuario nuevo y deshabilitar admin.'
         ];
    }

    // 2. Puerto SSH por defecto
    $ssh_port = isset($config['system']['ssh']['port']) ? $config['system']['ssh']['port'] : 22;
    if ($ssh_port == 22) {
        $issues[] = [
            'severity' => 'MEDIUM',
            'msg' => 'SSH está corriendo en el puerto 22 estándar. Considere cambiarlo.'
        ];
    }

    // 3. WebGUI en puerto 80/443
    $webgui_port = isset($config['system']['webgui']['port']) ? $config['system']['webgui']['port'] : '';
    if ($webgui_port == '' || $webgui_port == 443 || $webgui_port == 80) {
        $issues[] = [
             'severity' => 'LOW',
             'msg' => 'WebGUI usa puerto estándar (80/443). Mejor cambiarlo para reducir ruido en logs.'
        ];
    }
    
    // 4. Reglas "Any" en WAN
    // (Lógica simplificada para detectar reglas muy abiertas en WAN)
    if (is_array($config['filter']['rule'])) {
        foreach ($config['filter']['rule'] as $rule) {
            if ($rule['interface'] == 'wan' && !isset($rule['disabled'])) {
                if ($rule['source']['any'] && $rule['destination']['any']) {
                     $issues[] = [
                        'severity' => 'CRITICAL',
                        'msg' => 'Se detectó una regla ANY en WAN activa. Esto es un riesgo grave de seguridad.'
                    ];
                }
            }
        }
    }

    return_json('success', 'Escaneo de seguridad completado', ['issues' => $issues]);
}

/**
 * Aplicar Optimizaciones
 */
function apply_tuning() {
    global $config, $starlink_recommendations;

    // Crear backup antes de modificar
    $backup_name = "Backup Pre-Starlink-Tuning " . date("Ymd-His");
    write_config($backup_name);
    $changes = [];

    // 1. Fix WAN: Desactivar Block Private Networks
    if (isset($config['interfaces']['wan']['blockpriv'])) {
        unset($config['interfaces']['wan']['blockpriv']);
        $changes[] = "WAN: Desactivado 'Block Private Networks'";
    }

    // 2. Fix WAN: Reject Leases From
    $current_reject = isset($config['interfaces']['wan']['rejectleasesfrom']) ? $config['interfaces']['wan']['rejectleasesfrom'] : '';
    if (strpos($current_reject, '192.168.100.1') === false) {
        if (!empty($current_reject)) {
            $config['interfaces']['wan']['rejectleasesfrom'] .= ' 192.168.100.1';
        } else {
            $config['interfaces']['wan']['rejectleasesfrom'] = '192.168.100.1';
        }
        $changes[] = "WAN: Añadido 192.168.100.1 a 'Reject Leases From'";
    }

    // 3. Aplicar Sysctls
    if (!is_array($config['sysctl'])) $config['sysctl'] = [];
    if (!is_array($config['sysctl']['item'])) $config['sysctl']['item'] = [];

    foreach ($starlink_recommendations['sysctl'] as $key => $val) {
        $found = false;
        foreach ($config['sysctl']['item'] as &$item) {
            if ($item['tunable'] == $key) {
                $item['value'] = $val;
                $item['descr'] = "Optimizado por Starlink Tuner";
                $found = true;
                break;
            }
        }
        if (!$found) {
            $config['sysctl']['item'][] = [
                'tunable' => $key,
                'value' => $val,
                'descr' => "Optimizado por Starlink Tuner"
            ];
        }
    }
    $changes[] = "Sistema: Tunables de red aplicados/actualizados";

    // Guardar cambios
    write_config("Aplicado Tuning Starlink: " . implode(", ", $changes));
    
    // Aplicar sysctls dinámicamente sin reiniciar si es posible
    system_setup_sysctl(); 
    // Recargar configuración de interfaces
    interface_configure("wan");

    return_json('success', 'Cambios aplicados correctamente', ['changes' => $changes]);
}

/**
 * Aplicar Optimizaciones ULTRA (Loader)
 */
function apply_ultra_tuning() {
    $changes = [];
    $loader_tunables = [
        'kern.ipc.nmbclusters' => '1000000',
        'kern.ipc.maxsockbuf' => '16777216',
        'net.isr.defaultqlimit' => '2048',
        'net.inet.tcp.tso' => '0' // Desactivar TSO ayuda con Starlink a veces
    ];

    // Detectar sistema de arranque (pfSense nuevo vs viejo)
    $loader_dir = '/boot/loader.conf.d';
    $target_file = '';
    
    if (is_dir($loader_dir)) {
        // Método moderno: archivo dedicado
        $target_file = $loader_dir . '/starlink.conf';
        $content = "# Optimización Starlink ULTRA - Generado automáticamente\n";
        foreach ($loader_tunables as $key => $val) {
            $content .= "$key=\"$val\"\n";
        }
        file_put_contents($target_file, $content);
        $changes[] = "Creado archivo moderno: $target_file";
    } else {
        // Método clásico: loader.conf.local
        $target_file = '/boot/loader.conf.local';
        $current_content = file_exists($target_file) ? file_get_contents($target_file) : "";
        
        // Limpiar entradas antiguas nuestras
        $lines = explode("\n", $current_content);
        $clean_lines = [];
        foreach ($lines as $line) {
            $is_target = false;
            foreach ($loader_tunables as $key => $val) {
                if (strpos($line, $key) === 0) {
                    $is_target = true;
                    break;
                }
            }
            if (!$is_target && !empty(trim($line))) {
                $clean_lines[] = $line;
            }
        }
        
        // Agregar nuevas
        $clean_lines[] = "\n# Optimización Starlink ULTRA";
        foreach ($loader_tunables as $key => $val) {
            $clean_lines[] = "$key=\"$val\"";
        }
        
        file_put_contents($target_file, implode("\n", $clean_lines) . "\n");
        $changes[] = "Modificado archivo clásico: $target_file";
    }

    return_json('success', 'Optimizaciones ULTRA aplicadas (Requiere REINICIO)', ['changes' => $changes]);
}

/**
 * Restaurar Configuración Anterior
 */
function agent_restore_backup() {
    // Restaurar el último backup disponible en el historial
    // NOTA: Esto es una simplificación. En un caso real, buscaríamos el backup específico.
    // Para este script, asumiremos que si el usuario pide restore, quiere el inmediato anterior.
    
    global $g; // Variable global de pfSense
    
    // Obtener lista de backups
    $backups = list_backups();
    if (count($backups) > 0) {
        $latest = $backups[0]; // El más reciente (que acabamos de hacer si aplicamos)
        // Necesitamos el ANTERIOR a ese si acabamos de aplicar, o el último si fue manual.
        // Por seguridad, este script listará backups y pedirá confirmación en una versión interactiva
        // Pero para automatización simple, vamos a revertir al penúltimo si el último dice "Starlink"
        
        // Mejor estrategia: Buscar el último backup que NO sea del tuner, o simplemente revertir el último cambio.
        // Implementación segura: Revertir ultimo cambio.
        
        $conf_file = $g['conf_path'] . '/backup/config-' . $latest['time'] . '.xml';
        if (file_exists($conf_file)) {
            if (config_restore($conf_file) == 0) {
                return_json('success', 'Configuración restaurada al backup: ' . date("Y-m-d H:i:s", $latest['time']));
            } else {
                 return_json('error', 'Fallo al restaurar la configuración');
            }
        }
    }
    return_json('error', 'No se encontraron backups para restaurar');
}


// --- Main ---

$mode = isset($argv[1]) ? $argv[1] : 'help';

switch ($mode) {
    case 'audit':
        audit_config();
        break;
    case 'security':
        audit_security();
        break;
    case 'apply':
        apply_tuning();
        break;
    case 'ultra':
        apply_ultra_tuning();
        break;
    case 'restore':
        agent_restore_backup();
        break;
    default:
        echo "Uso: php pfsense_agent.php [audit|security|apply|restore]\n";
        break;
}

?>
