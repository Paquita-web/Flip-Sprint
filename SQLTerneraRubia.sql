CREATE DATABASE IF NOT EXISTS logistic_db;
USE logistic_db;

-- 1. Tabla shipments (Datos Maestros del Envío)
[cite_start]-- Almacena información estática y crítica como la caducidad[cite: 3].
CREATE TABLE shipments (
    [cite_start]id_paquete VARCHAR(50) NOT NULL PRIMARY KEY COMMENT 'Identificador único del envío [cite: 4]',
    [cite_start]producto VARCHAR(100) NOT NULL COMMENT 'Tipo de producto transportado [cite: 4]',
    [cite_start]fecha_caducidad DATE NOT NULL COMMENT 'Limite de vida útil del producto [cite: 4]',
    [cite_start]ruta_asignada VARCHAR(100) COMMENT 'Ruta logistica planificada [cite: 4]',
    [cite_start]estado_actual VARCHAR(20) DEFAULT 'En ruta' COMMENT 'Estado operativo del envío [cite: 4]',
    [cite_start]created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT 'Momento de creación del registro [cite: 4]'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. Tabla telemetry (Series de Tiempo y Sensores)
[cite_start]-- Diseñada para persistir cada lectura de sensor IoT en tiempo real[cite: 6].
CREATE TABLE telemetry (
    [cite_start]id BIGINT AUTO_INCREMENT NOT NULL PRIMARY KEY COMMENT 'Clave de registro única [cite: 8]',
    [cite_start]timestamp TIMESTAMP NOT NULL COMMENT 'Momento exacto de la lectura [cite: 8]',
    [cite_start]id_paquete VARCHAR(50) NOT NULL COMMENT 'Vincula la lectura al envío [cite: 8]',
    [cite_start]temperatura_c FLOAT NOT NULL COMMENT 'Temperatura del entorno de la carga (°C) [cite: 8]',
    [cite_start]fuerza_g_ejez FLOAT NOT NULL COMMENT 'Aceleración en eje Z (impacto/caída) [cite: 8]',
    [cite_start]latitud FLOAT COMMENT 'Ubicación geográfica [cite: 8]',
    [cite_start]longitud FLOAT COMMENT 'Ubicación geográfica [cite: 8]',
    [cite_start]alerta_generada BOOLEAN DEFAULT FALSE COMMENT 'Indica si superó el umbral de detección [cite: 8]',
    puerta_abierta BOOLEAN DEFAULT FALSE COMMENT 'NUEVO: Sensor de estado de puerta (TRUE = Abierta, FALSE = Cerrada)',
    CONSTRAINT fk_telemetry_shipment FOREIGN KEY (id_paquete) REFERENCES shipments(id_paquete) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_telemetry_paquete_time (id_paquete, timestamp) -- Índice recomendado para consultas de series temporales
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. Tabla alerts (Registro de Incidencias)
[cite_start]-- Registra eventos de anomalías para analítica y KPIs[cite: 10, 11].
CREATE TABLE alerts (
    [cite_start]id BIGINT AUTO_INCREMENT NOT NULL PRIMARY KEY COMMENT 'Clave de registro de la alerta [cite: 12]',
    [cite_start]id_telemetria BIGINT NOT NULL COMMENT 'Vincula la alerta a la lectura que la disparó [cite: 13]',
    [cite_start]id_paquete VARCHAR(50) NOT NULL COMMENT 'Envío afectado [cite: 13]',
    [cite_start]timestamp_alerta TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT 'Momento en que el sistema generó la alerta [cite: 13]',
    [cite_start]tipo_alerta VARCHAR(50) NOT NULL COMMENT 'Razón (ej. TEMPERATURA, IMPACTO, PUERTA_ABIERTA) [cite: 13]',
    [cite_start]es_falso_positivo BOOLEAN DEFAULT FALSE COMMENT 'Marcador para KPI de Confianza [cite: 13]',
    CONSTRAINT fk_alerts_telemetry FOREIGN KEY (id_telemetria) REFERENCES telemetry(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_alerts_shipments FOREIGN KEY (id_paquete) REFERENCES shipments(id_paquete) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;