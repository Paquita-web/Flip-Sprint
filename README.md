🐄 Proyecto: Gestión de Exportación e Importación de Ternera Rubia Gallega
📖 Descripción

Este proyecto tiene como objetivo gestionar y automatizar el proceso de exportación e importación de ternera rubia gallega, asegurando trazabilidad, control de calidad y respaldo de los datos.
Incluye un sistema de gestión de información y un mecanismo de copias de seguridad automáticas para garantizar la disponibilidad y seguridad de los registros.

🎯 Objetivos

Registrar y gestionar lotes de carne para exportación e importación.
Controlar clientes, países destino y estados de los envíos.
Automatizar copias de seguridad diarias del sistema y la base de datos.
Facilitar la restauración rápida ante fallos o pérdida de información.

⚙️ Tecnologías utilizadas

Sistema operativo: Debian / Ubuntu
Lenguaje: Python 3
Base de datos: SQLite
Automatización: Bash + cron
Backup: rsync, tar, gzip
Control de versiones: Git + GitHub
CI/CD (opcional): GitHub Actions

Estructura del proyecto
proyecto-ternera/
├── src/
│   ├── gestion.py          # Lógica de gestión de datos
│   ├── base_datos.py       # Conexión y operaciones con SQLite
│   └── exportacion.py      # Funciones relacionadas con exportación
│
├── datos/
│   └── ternera.db          # Base de datos principal
│
├── backup/
│   ├── backup.sh           # Script de copias de seguridad
│   └── restore.sh          # Script de restauración
│
├── .github/workflows/
│   └── backup.yml          # Workflow de GitHub Actions (simulación de backup)
│
└── README.md               # Documentación del proyecto

🗂️ Estructura de la base de datos

Tabla lotes:
Campo	Tipo	Descripción
id	INTEGER (PK)	Identificador único del lote
origen	TEXT	Granja o productor
destino	TEXT	País o cliente destino
peso_total	REAL	Peso total (kg)
fecha_envio	DATE	Fecha de salida
estado	TEXT	Pendiente / En tránsito / Entregado

Tabla clientes:
Campo	Tipo	Descripción
id	INTEGER (PK)	Identificador
nombre	TEXT	Nombre del cliente
pais	TEXT	País de destino
contacto	TEXT	Datos de contacto
🔁 Workflow de copias de seguridad

Tipo: Completo diario
Frecuencia: 1 copia cada día a las 02:00 AM
Retención: Últimos 7 días
Ubicación: /mnt/backup o ~/backup
Ejecución automática: mediante cron

Script backup.sh
#!/bin/bash
FECHA=$(date +%Y-%m-%d_%H-%M)
ORIGEN="/srv/datos_empresa"  # o ~/datos_empresa
DESTINO="/mnt/backup"
LOG="/var/log/backup.log"

mkdir -p "$DESTINO"
rsync -av --delete "$ORIGEN" "$DESTINO/$FECHA/"
tar -czf "$DESTINO/backup_$FECHA.tar.gz" -C "$DESTINO" "$FECHA"
find "$DESTINO" -name "backup_*.tar.gz" -mtime +7 -delete
echo "[$(date)] Backup completado en $DESTINO/backup_$FECHA.tar.gz" >> "$LOG"

🧠 Workflow general del sistema
El usuario registra o actualiza datos (lotes, clientes, exportaciones).
El sistema guarda los cambios en la base de datos ternera.db.
Cada noche, cron ejecuta el script backup.sh.
Se crea un archivo comprimido con la copia de seguridad.
Las copias antiguas (más de 7 días) se eliminan automáticamente.
