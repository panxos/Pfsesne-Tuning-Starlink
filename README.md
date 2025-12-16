# 📡 pfSense Starlink Tuner - Professional Edition

> **Professional Optimization, Auditing, and Tuning Tool for Starlink Internet Connections on pfSense.**
> *Herramienta Profesional de Optimización, Auditoría y Tuning para conexiones Starlink en pfSense.*

---

## 🚀 Overview / Descripción General

**(EN)**
This tool is an advanced, automated solution designed to optimize **pfSense** routers specifically for **Starlink** internet connections. Starlink's satellite nature (high bandwidth, variable latency, CGNAT) requires specific kernel and interface tunings that standard fiber configuratons do not provide.

This Professional Edition offers a Client-Agent architecture for secure, audited, and reversible changes, including a "Ultra Mode" for deep kernel optimization.

**(ES)**
Esta herramienta es una solución automatizada y avanzada diseñada para optimizar routers **pfSense** específicamente para conexiones de internet **Starlink**. La naturaleza satelital de Starlink (alto ancho de banda, latencia variable, CGNAT) requiere ajustes específicos de kernel e interfaz que las configuraciones estándar de fibra no ofrecen.

Esta Edición Profesional ofrece una arquitectura Cliente-Agente para realizar cambios seguros, auditados y reversibles, incluyendo un "Modo Ultra" para optimización profunda del kernel.

---

## 🔥 Features / Características

* **🛡️ Secure Architecture**: Uses SSH to deploy a temporary PHP agent. No permanent software installation on pfSense.
* **📊 Tuning Audit**: Scans your current configuration and rates your optimization level.
* **⚡ Automatic Tuning**:
  * **WAN Fixes**: Disables "Block Private Networks" (required for Starlink stats/CGNAT) and sets "Reject Leases From 192.168.100.1" (prevents hang on micro-drops).
  * **Sysctl Tuning**: Increases TCP buffers (4MB) and interrupt queues (2048) for high-latency throughput.
* **🚀 Ultra Mode (New!)**: Deep kernel optimization via `loader.conf` for >1Gbps throughput (Requires Reboot).
* **🔒 Security Scan**: Checks for default credentials, risky ports (22/80), and dangerous firewall rules.
* **💾 Auto-Backup & Rollback**: automatically downloads local backups before changes and offers one-click restore.

---

## 🛠️ Requirements / Requisitos

* **Client (Linux)**:
  * Python 3.6+
  * `sshpass` (optional, for password auth)
  * Network access to pfSense LAN/WAN IP
* **Server (pfSense)**:
  * pfSense 2.5, 2.6, 2.7+ (Community or Plus)
  * SSH Enabled (`System > Advanced > Secure Shell`)
  * User with root/admin privileges

---

## 📦 Installation / Instalación

```bash
# Clone the repository / Clonar el repositorio
git clone https://github.com/panxos/Pfsesne-Tuning-Starlink.git

# Enter directory / Entrar al directorio
cd Pfsesne-Tuning-Starlink

# Make executable / Hacer ejecutable
chmod +x Pfsesne-Tuning-Starlink.py
```

---

## 💻 Usage / Uso

Run the tool connecting to your pfSense IP.
*Ejecute la herramienta conectando a la IP de su pfSense.*

```bash
./Pfsesne-Tuning-Starlink.py --host 192.168.1.1 --user root
```

### Main Menu / Menú Principal

The tool will upload the agent and present a professional interactive menu:
*La herramienta subirá el agente y presentará un menú interactivo profesional:*

1. **Auditar Configuración**: Compara tu estado actual con las "Best Practices" de Starlink.
2. **Escaneo de Seguridad**: Busca vulnerabilidades básicas.
3. **Aplicar Optimizaciones**: Aplica los parches de configuración Sysctl y WAN (Sin reinicio).
4. **Restaurar Backup**: Revierte el último cambio realizado por la herramienta.
5. **Modo ULTRA**: Escribe optimizaciones en `loader.conf.d` para máximo rendimiento (Requiere Reinicio).

---

## 🔧 Technical Details / Detalles Técnicos

### Optimization Parameters / Parámetros de Optimización

| Tunable (Sysctl) | Value | Benefit / Beneficio |
| :--- | :--- | :--- |
| `net.inet.tcp.recvbuf_max` | `4194304` (4MB) | Increases download throughput over high latency. |
| `net.inet.tcp.sendbuf_max` | `4194304` (4MB) | Increases upload throughput over high latency. |
| `net.inet.ip.intr_queue_maxlen`| `2048` | Prevents packet drops during speed bursts. |
| `kern.ipc.maxsockbuf` (ULTRA)| `16777216` | Allows massive 16MB buffers for enterprise links. |
| `kern.ipc.nmbclusters` (ULTRA)| `1000000` | Supports 1M+ network packets in memory. |

---

## ⚠️ Disclaimer

This tool modifies system configurations. While it includes robust backup mechanisms, always ensure you have a full system backup before applying "Ultra Mode" changes.
*Esta herramienta modifica configuraciones del sistema. Aunque incluye mecanismos robustos de respaldo, siempre asegúrate de tener un backup completo del sistema antes de aplicar cambios en "Modo Ultra".*

---

## 👨‍💻 Credits / Créditos

**Author**: Francisco Aravena  
**GitHub**: [github.com/panxos/Pfsesne-Tuning-Starlink](https://github.com/panxos/Pfsesne-Tuning-Starlink)

*Built with ❤️ for the Starlink & pfSense Community.*
