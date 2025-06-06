# Telegram Scheduler Bot

Bot de Telegram avanzado para programar y gestionar mensajes automáticos con interfaz de botones interactivos.

## Características

### Funcionalidades Principales
- **Programación de Mensajes**: Programa mensajes para horarios específicos
- **Mensajes por Fecha**: Programa mensajes para fechas específicas (DD/MM/YYYY)
- **Mensajes Repetitivos**: Configura mensajes diarios, semanales o mensuales
- **Envío Inmediato**: Envía mensajes instantáneamente
- **Gestión de Emails**: Envío de emails programados y automáticos
- **Consulta del Clima**: Información meteorológica por comando
- **Interfaz Interactiva**: Navegación por botones, sin comandos complejos

### Características Técnicas
- Menú interactivo con botones organizados
- Dashboard en tiempo real con estadísticas
- Sistema de keep-alive automático
- Gestión de usuarios autorizados
- Base de datos PostgreSQL integrada
- Sistema de backup y restauración
- Logs detallados y sistema de errores

## Instalación

### Requisitos
- Python 3.11+
- PostgreSQL
- Cuenta de bot de Telegram

### Dependencias
```bash
pip install python-telegram-bot psycopg2-binary flask schedule pytz requests smtplib
```

### Variables de Entorno Requeridas
```bash
TELEGRAM_BOT_TOKEN=tu_token_del_bot
DATABASE_URL=postgresql://usuario:password@host:puerto/basedatos
USUARIO_AUTORIZADO_ID=tu_user_id
GMAIL_EMAIL=tu_email@gmail.com
GMAIL_APP_PASSWORD=tu_app_password
OPENWEATHER_API_KEY=tu_api_key_clima
```

## Configuración

1. **Crear Bot de Telegram**:
   - Contacta @BotFather en Telegram
   - Crea un nuevo bot con `/newbot`
   - Obtén el token del bot

2. **Configurar Base de Datos**:
   - Configura PostgreSQL
   - Establece la variable DATABASE_URL

3. **Configurar Email (Opcional)**:
   - Habilita autenticación de 2 factores en Gmail
   - Genera una contraseña de aplicación
   - Configura GMAIL_EMAIL y GMAIL_APP_PASSWORD

4. **API del Clima (Opcional)**:
   - Regístrate en OpenWeatherMap
   - Obtén tu API key
   - Configura OPENWEATHER_API_KEY

## Uso

### Inicio del Bot
```bash
python main.py
```

### Comandos Principales (También disponibles por botones)

#### Mensajes Básicos
- `/start` - Inicia el bot y muestra el dashboard
- `/enviar "mensaje" [chat_id]` - Envía mensaje inmediato
- `/programar "mensaje" HH:MM [chat_id]` - Programa mensaje para hoy
- `/programar_fecha "mensaje" DD/MM/YYYY HH:MM` - Programa para fecha específica
- `/repetir "mensaje" HH:MM intervalo [chat_id]` - Mensaje repetitivo

#### Gestión
- `/listar` - Ver mensajes programados
- `/cancelar <número>` - Cancela mensaje programado
- `/estadisticas` - Estadísticas del bot
- `/backup` - Exporta configuración

#### Email y Clima
- `/email "asunto" "mensaje" email@domain.com` - Envía email
- `/programar_email "asunto" "mensaje" HH:MM email@domain.com` - Email programado
- `/clima ciudad` - Consulta clima
- `/clima_email ciudad email@domain.com` - Clima por email

#### Administración
- `/agregar <user_id>` - Autoriza usuario
- `/remover <user_id>` - Desautoriza usuario
- `/chat_info` - Información del chat actual

### Formatos de Tiempo
- **Hora**: `HH:MM` (formato 24 horas)
- **Fecha**: `DD/MM/YYYY`
- **Intervalos**: `diario`, `semanal`, `mensual`

### Ejemplos de Uso
```bash
# Programar mensaje para las 2:30 PM
/programar "Reunión de equipo en 30 minutos" 14:30

# Mensaje para fecha específica
/programar_fecha "Feliz Año Nuevo!" 01/01/2026 00:00

# Mensaje repetitivo diario
/repetir "Buenos días equipo" 08:00 diario

# Email con clima
/clima_email Madrid jefe@empresa.com
```

## Arquitectura

### Archivos Principales
- `main.py` - Bot principal con lógica de comandos
- `keep_alive.py` - Sistema keep-alive con Flask
- `mensajes.json` - Almacenamiento de mensajes programados
- `estadisticas.json` - Estadísticas y logs del bot

### Base de Datos
- **usuarios_autorizados**: Lista de usuarios con permisos
- **estadisticas**: Registro de acciones y uso del bot

### Sistema de Menús
- **Dashboard Principal**: Resumen con estadísticas en tiempo real
- **Menús por Categoría**: Programación, gestión, configuración
- **Navegación Intuitiva**: Botones "Volver" y submenús organizados

## Características Avanzadas

### Keep-Alive Inteligente
- Sistema automático para mantener el bot activo 24/7
- Ping entre servicios para prevenir hibernación
- Monitoreo del estado del servidor

### Gestión de Usuarios
- Sistema de autorización por ID de usuario
- Múltiples administradores
- Control de acceso granular

### Sistema de Backup
- Exportación automática de configuración
- Backup de mensajes programados
- Restauración de estado

### Monitoreo y Logs
- Estadísticas detalladas de uso
- Logs de errores y eventos
- Dashboard de métricas en tiempo real

## Desarrollo

### Estructura del Código
```
telegram-scheduler-bot/
├── main.py                 # Bot principal
├── keep_alive.py          # Sistema keep-alive
├── mensajes.json          # Datos de mensajes
├── estadisticas.json      # Estadísticas
├── requirements.txt       # Dependencias
└── README.md             # Documentación
```

### Contribuir
1. Fork el repositorio
2. Crea una rama para tu feature
3. Realiza tus cambios
4. Envía un pull request

## Licencia

Este proyecto está bajo la Licencia MIT. Ver `LICENSE` para más detalles.

## Soporte

Para reportar bugs o solicitar features, abre un issue en el repositorio.

## Changelog

### v2.0.0
- Implementación de menú interactivo con botones
- Dashboard en tiempo real
- Sistema de navegación mejorado
- Interfaz unificada y profesional

### v1.0.0
- Funcionalidades básicas de programación
- Sistema de comandos por texto
- Integración con email y clima
- Base de datos PostgreSQL