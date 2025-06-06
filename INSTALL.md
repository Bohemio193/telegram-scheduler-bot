# Guía de Instalación Rápida

## Método 1: Instalación Manual

### Paso 1: Clonar el repositorio
```bash
git clone https://github.com/tu-usuario/telegram-scheduler-bot.git
cd telegram-scheduler-bot
```

### Paso 2: Instalar dependencias
```bash
pip install -r telegram-bot-requirements.txt
```

### Paso 3: Configurar variables de entorno
```bash
cp .env.example .env
# Editar .env con tus credenciales
```

### Paso 4: Preparar archivos de datos
```bash
cp mensajes-example.json mensajes.json
cp estadisticas-example.json estadisticas.json
```

### Paso 5: Ejecutar el bot
```bash
python main.py
```

## Método 2: Docker Compose (Recomendado)

### Requisitos previos
- Docker
- Docker Compose

### Instalación
```bash
git clone https://github.com/tu-usuario/telegram-scheduler-bot.git
cd telegram-scheduler-bot
cp .env.example .env
# Configurar variables en .env
docker-compose up -d
```

## Configuración de Telegram Bot

1. Abrir Telegram y buscar @BotFather
2. Enviar `/newbot`
3. Seguir las instrucciones para nombrar tu bot
4. Copiar el token proporcionado
5. Añadir el token a tu archivo `.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   ```

## Obtener tu User ID

1. Abrir Telegram y buscar @userinfobot
2. Enviar `/start`
3. Copiar tu User ID
4. Añadirlo al archivo `.env`:
   ```
   USUARIO_AUTORIZADO_ID=123456789
   ```

## Configuración Opcional

### Email (Gmail)
1. Habilitar autenticación de 2 factores
2. Generar contraseña de aplicación
3. Configurar en `.env`:
   ```
   GMAIL_EMAIL=tu_email@gmail.com
   GMAIL_APP_PASSWORD=tu_contraseña_app
   ```

### API del Clima
1. Registrarse en openweathermap.org
2. Obtener API key gratuita
3. Configurar en `.env`:
   ```
   OPENWEATHER_API_KEY=tu_api_key
   ```

## Verificar Instalación

1. Enviar `/start` a tu bot en Telegram
2. Deberías ver el dashboard interactivo
3. Verificar que los botones respondan correctamente

## Resolución de Problemas

### Bot no responde
- Verificar que el token sea correcto
- Confirmar que el bot esté iniciado
- Revisar logs en la consola

### Error de base de datos
- Verificar configuración de PostgreSQL
- Confirmar que DATABASE_URL sea correcta
- Revisar permisos de usuario de BD

### Keep-alive no funciona
- Verificar que el puerto 8080 esté disponible
- Confirmar configuración de red
- Revisar logs del servidor Flask