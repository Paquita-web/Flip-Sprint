Resumen del Proyecto y Enfoque 

Atributo
Descripción
Misión
Diseñar, construir y desplegar un pipeline de datos de extremo a extremo para la Detección de Incidentes en Tiempo Real en envíos refrigerados de GreenDelivery.
Arquitectura
Edge (Simulador)  MQTT Broker  Cloud Ingesta (Low-Code)  PostgreSQL (Storage)  BI (Decisión/KPIs).
Enfoque
Seguridad desde el Diseño (CIA) y Resiliencia (evitar la pérdida de datos ante fallos).
Entregable Clave
Sistema funcional que detecta anomalías sostenidas, un Dashboard con KPIs de negocio y un Informe Justificativo (máx. 4 págs.).


Semana 1: Fundamentos y Flujo de Datos (Capítulos 1 y 2)

El objetivo es establecer el flujo de datos y justificar la arquitectura.

1. Flujo de Datos Robusto (Capítulo 1) 

Componente
Tarea Clave
Resultado Esperado
Justificación de Ingeniería
Edge (Simulador)
Script Python (paho-mqtt) que genera JSON con temp, g_force, id_paquete, timestamp.
El script publica datos continuamente a un tópico MQTT (ej. greendelivery/trackers/telemetry).
Uso de MQTT (IoT): Protocolo ligero y eficiente para redes inestables; modelo Publicador/Suscriptor para Desacoplamiento.
Ingesta (Low-Code)
Flujo en Node-RED/n8n que se suscribe al tópico MQTT.
El flujo recibe el mensaje y realiza una validación básica de formato (JSON correcto).
PaaS/Función Gestionada: Prototipado rápido y bajo control operativo para la lógica inicial.
Persistencia
El flujo llama a la API de Ingesta (FastAPI) y esta inserta el dato en PostgreSQL.
Se insertan filas en la tabla telemetry de PostgreSQL.
Base de Datos Relacional: Garantiza la Integridad de Datos con esquema fijo para la analítica; la API desacopla el flujo del motor de la BD.
Resiliencia
Configurar en el "Nodo HTTP Request" una Lógica de Reintentos con Backoff.
Si la BD o API cae, los datos se ponen en cola o se reintentan (evitando la pérdida).
Disponibilidad (A) y Resiliencia: No se pueden perder eventos (coste alto para el negocio). Backoff evita saturar el servicio que se recupera.


2. Documentación Arquitectónica (Capítulo 2) 

Entregable: diagrams/arquitectura_T2.png y Fichas de Decisión en el informe.
Diagrama de Arquitectura: Dibujar un diagrama de bloques simple (Ej. con Draw.io) mostrando el flujo Edge  Broker  Flujo Low-Code  API  DB  Dashboard.
Justificación Cloud/NIST: Para cada bloque, justificar la elección:
MQTT Broker: Desacoplamiento. Permite que el sensor no se preocupe por el estado del receptor.
Node-RED/n8n: Escalabilidad bajo demanda (si se ejecuta en FaaS) y Pago por uso.
PostgreSQL (Managed): Servicio Gestionado (Menos Operaciones) a costa de posible Vendor Lock-In.

Semana 2: Inteligencia, Seguridad y Demostración (Capítulos 3, 4 y 5)

El objetivo es añadir la lógica de negocio, los KPIs y blindar el sistema.

3. Detección Inteligente y Métricas (Capítulo 3) 

Lógica de Detección con Estado:
Implementar la regla: Alerta si    durante  eventos consecutivos (ej. ) para el mismo id_paquete.
Desafío: Usar una caché o una variable de estado en el procesador (Node-RED/n8n) para mantener el contador  por cada paquete activo.
Métrica de Negocio (Paso 2):
Elegir la métrica clave. Para GreenDelivery, el coste de un Falso Negativo (envío dañado sin alerta) es mayor que el de un Falso Positivo (alerta innecesaria).
Decisión: Optimizar para Recall (Exhaustividad) para minimizar la pérdida de incidentes reales.
Evaluación (Paso 3):
Script de Python/Pandas para aplicar la lógica de  eventos al labels.csv.
Calcular la Matriz de Confusión y el Recall (y F1-Score) de vuestra regla.




