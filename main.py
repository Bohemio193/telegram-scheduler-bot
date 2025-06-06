
# ======= Servidor Flask para mantener Render activo =======
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot activo desde Render"

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start()
# ==========================================================


keep_alive()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Bot para programar mensajes automáticamente
Permite agendar mensajes para ser enviados en horarios específicos
"""

from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import logging
import datetime
import threading
import os
import re
import json
import schedule
import time
import pytz
import psycopg2
from psycopg2.extras import RealDictCursor
from keep_alive import keep_alive
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests


# 🔧 Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 🔐 Token del bot desde variables de entorno
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

if not TOKEN:
    logger.error("❌ No se encontró el token del bot. Configura la variable de entorno TELEGRAM_BOT_TOKEN")
    exit(1)

# 📧 Configuración de email
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# 🌤️ Configuración de clima
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

# 📡 URL del PrediceLotoBot para mantenerlo activo
PREDICE_LOTO_URL = "http://127.0.0.1:5000/heartbeat"

# 📦 Estructura para guardar mensajes programados
# Cada elemento: {'mensaje': str, 'hora': str, 'chat_id': int, 'timer': threading.Timer, 'fecha_objetivo': datetime}
mensajes_programados = []

# 👥 Lista de usuarios autorizados (IDs de Telegram)
usuarios_autorizados = {5821178446, 1310838632}  # Usuarios iniciales autorizados

# 🔄 Estructura para mensajes repetitivos
# Cada elemento: {'mensaje': str, 'hora': str, 'intervalo': str, 'chat_id': int, 'activo': bool}
mensajes_repetitivos = []

# 🌍 Configuración de zona horaria
TIMEZONE = pytz.timezone('America/Caracas')  # Venezuela

# 📊 Estadísticas del bot
estadisticas = {
    'mensajes_enviados': 0,
    'mensajes_programados_total': 0,
    'usuarios_activos': set(),
    'inicio_bot': None
}

# 📁 Archivos JSON para persistencia
ARCHIVO_MENSAJES = 'mensajes.json'
ARCHIVO_ESTADISTICAS = 'estadisticas.json'

# 📁 Funciones de persistencia JSON
def cargar_mensajes_json():
    """
    Carga los mensajes desde el archivo JSON
    """
    try:
        if os.path.exists(ARCHIVO_MENSAJES):
            with open(ARCHIVO_MENSAJES, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Crear estructura inicial
            estructura_inicial = {
                "programados": [],
                "repetitivos": [],
                "autorizados": [],
                "configuracion": {
                    "timezone": str(TIMEZONE),
                    "version": "2.0",
                    "creado": datetime.datetime.now(TIMEZONE).isoformat()
                }
            }
            guardar_mensajes_json(estructura_inicial)
            return estructura_inicial
    except Exception as e:
        logger.error(f"Error cargando mensajes JSON: {e}")
        return {"programados": [], "repetitivos": [], "autorizados": [], "configuracion": {}}

def guardar_mensajes_json(data):
    """
    Guarda los mensajes en el archivo JSON
    """
    try:
        with open(ARCHIVO_MENSAJES, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Error guardando mensajes JSON: {e}")

def cargar_estadisticas_json():
    """
    Carga las estadísticas desde el archivo JSON
    """
    try:
        if os.path.exists(ARCHIVO_ESTADISTICAS):
            with open(ARCHIVO_ESTADISTICAS, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {
                "mensajes_enviados": 0,
                "mensajes_programados_total": 0,
                "usuarios_activos": [],
                "acciones": [],
                "inicio_bot": None
            }
    except Exception as e:
        logger.error(f"Error cargando estadísticas JSON: {e}")
        return {}

def guardar_estadisticas_json(stats):
    """
    Guarda las estadísticas en el archivo JSON
    """
    try:
        with open(ARCHIVO_ESTADISTICAS, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Error guardando estadísticas JSON: {e}")

def agregar_mensaje_programado_json(mensaje_data):
    """
    Agrega un mensaje programado al archivo JSON
    """
    try:
        data = cargar_mensajes_json()
        data['programados'].append(mensaje_data)
        guardar_mensajes_json(data)
    except Exception as e:
        logger.error(f"Error agregando mensaje programado JSON: {e}")

def agregar_mensaje_repetitivo_json(mensaje_data):
    """
    Agrega un mensaje repetitivo al archivo JSON
    """
    try:
        data = cargar_mensajes_json()
        data['repetitivos'].append(mensaje_data)
        guardar_mensajes_json(data)
    except Exception as e:
        logger.error(f"Error agregando mensaje repetitivo JSON: {e}")

def actualizar_usuario_autorizado_json(user_id, accion='agregar', username=None):
    """
    Actualiza la lista de usuarios autorizados en JSON
    accion: 'agregar' o 'remover'
    """
    try:
        data = cargar_mensajes_json()
        
        if accion == 'agregar':
            if user_id not in data['autorizados']:
                data['autorizados'].append(user_id)
        elif accion == 'remover':
            if user_id in data['autorizados']:
                data['autorizados'].remove(user_id)
        
        guardar_mensajes_json(data)
        return True
    except Exception as e:
        logger.error(f"Error actualizando usuario autorizado JSON: {e}")
        return False

def registrar_accion_json(user_id, accion, detalles=None):
    """
    Registra una acción en las estadísticas JSON
    """
    try:
        stats = cargar_estadisticas_json()
        
        accion_data = {
            "user_id": user_id,
            "accion": accion,
            "fecha": datetime.datetime.now(TIMEZONE).isoformat(),
            "detalles": detalles
        }
        
        if 'acciones' not in stats:
            stats['acciones'] = []
        
        stats['acciones'].append(accion_data)
        
        # Actualizar contadores
        if accion == 'mensaje_enviado':
            stats['mensajes_enviados'] = stats.get('mensajes_enviados', 0) + 1
        elif accion in ['mensaje_programado', 'mensaje_programado_fecha']:
            stats['mensajes_programados_total'] = stats.get('mensajes_programados_total', 0) + 1
        
        # Actualizar usuarios activos
        if 'usuarios_activos' not in stats:
            stats['usuarios_activos'] = []
        if user_id not in stats['usuarios_activos']:
            stats['usuarios_activos'].append(user_id)
        
        guardar_estadisticas_json(stats)
    except Exception as e:
        logger.error(f"Error registrando acción JSON: {e}")

# 🗄️ Funciones de base de datos (mantener compatibilidad)
def init_database():
    """
    Inicializa las tablas de la base de datos
    """
    try:
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cur = conn.cursor()
        
        # Tabla de usuarios autorizados
        cur.execute('''
            CREATE TABLE IF NOT EXISTS usuarios_autorizados (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                fecha_autorizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de mensajes programados
        cur.execute('''
            CREATE TABLE IF NOT EXISTS mensajes_programados (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                chat_id BIGINT,
                mensaje TEXT,
                fecha_programada TIMESTAMP,
                tipo VARCHAR(50) DEFAULT 'unico',
                intervalo VARCHAR(50),
                activo BOOLEAN DEFAULT TRUE,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de estadísticas
        cur.execute('''
            CREATE TABLE IF NOT EXISTS estadisticas (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                accion VARCHAR(100),
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                detalles JSONB
            )
        ''')
        
        # Tabla de configuración
        cur.execute('''
            CREATE TABLE IF NOT EXISTS configuracion (
                clave VARCHAR(100) PRIMARY KEY,
                valor TEXT,
                fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        cur.close()
        conn.close()
        logger.info("✅ Base de datos inicializada correctamente")
        
    except Exception as e:
        logger.error(f"❌ Error inicializando base de datos: {e}")

def guardar_usuario_autorizado(user_id, username=None):
    """
    Guarda un usuario autorizado en la base de datos
    """
    try:
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cur = conn.cursor()
        
        cur.execute('''
            INSERT INTO usuarios_autorizados (user_id, username) 
            VALUES (%s, %s) 
            ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username
        ''', (user_id, username))
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error guardando usuario autorizado: {e}")

def cargar_usuarios_autorizados():
    """
    Carga la lista de usuarios autorizados desde la base de datos
    """
    try:
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cur = conn.cursor()
        
        cur.execute('SELECT user_id FROM usuarios_autorizados')
        usuarios = {row[0] for row in cur.fetchall()}
        
        cur.close()
        conn.close()
        
        return usuarios
        
    except Exception as e:
        logger.error(f"Error cargando usuarios autorizados: {e}")
        return set()

def registrar_estadistica(user_id, accion, detalles=None):
    """
    Registra una estadística en la base de datos
    """
    try:
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cur = conn.cursor()
        
        cur.execute('''
            INSERT INTO estadisticas (user_id, accion, detalles) 
            VALUES (%s, %s, %s)
        ''', (user_id, accion, json.dumps(detalles) if detalles else None))
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error registrando estadística: {e}")

def es_usuario_autorizado(user_id):
    """
    Verifica si un usuario está autorizado para usar el bot
    Ahora verifica tanto en memoria como en JSON
    """
    # Cargar usuarios desde JSON si la lista en memoria está vacía
    if len(usuarios_autorizados) == 0:
        data = cargar_mensajes_json()
        usuarios_json = data.get('autorizados', [])
        return len(usuarios_json) == 0 or user_id in usuarios_json
    
    return user_id in usuarios_autorizados

def validar_formato_hora(hora_str):
    """
    Valida que la hora tenga el formato HH:MM correcto o formato 12 horas con AM/PM
    """
    try:
        hora_str = hora_str.strip().lower()
        
        # Verificar si es formato AM/PM
        if hora_str.endswith('am') or hora_str.endswith('pm'):
            es_pm = hora_str.endswith('pm')
            hora_str = hora_str[:-2].strip()
            
            if ':' not in hora_str:
                return False
                
            partes = hora_str.split(':')
            if len(partes) != 2:
                return False
                
            hora = int(partes[0])
            minuto = int(partes[1])
            
            # Validar rangos para formato 12 horas
            if not (1 <= hora <= 12 and 0 <= minuto <= 59):
                return False
                
            return True
        else:
            # Formato 24 horas
            if ':' not in hora_str or len(hora_str) < 4 or len(hora_str) > 5:
                return False
                
            partes = hora_str.split(':')
            if len(partes) != 2:
                return False
                
            hora = int(partes[0])
            minuto = int(partes[1])
            
            return 0 <= hora <= 23 and 0 <= minuto <= 59
    except:
        return False

def validar_intervalo(intervalo_str):
    """
    Valida los intervalos para mensajes repetitivos
    """
    intervalos_validos = ['diario', 'semanal', 'mensual']
    return intervalo_str.lower() in intervalos_validos

def procesar_destinatario(destinatario, update):
    """
    Procesa el destinatario y retorna el chat_destino apropiado
    """
    try:
        # Si empieza con @, es un username
        if destinatario.startswith('@'):
            return destinatario
        # Si empieza con +, es un número de teléfono (limitación de Telegram)
        elif destinatario.startswith('+'):
            update.message.reply_text(
                "⚠️ **Limitación de Telegram**\n\n"
                "Los bots no pueden enviar mensajes directamente a números de teléfono.\n\n"
                "**Soluciones:**\n"
                "• La persona debe escribir /start al bot primero\n"
                "• Usa @username en su lugar\n"
                "• Obtén el chat ID después del primer contacto\n\n"
                "Programando para este chat por ahora...",
                parse_mode='Markdown'
            )
            return update.message.chat_id
        # Si es solo números, puede ser chat ID
        elif destinatario.lstrip('-').isdigit():
            return int(destinatario)
        else:
            return destinatario
    except ValueError:
        update.message.reply_text(
            "❌ Destinatario inválido.\n\n"
            "Formatos válidos:\n"
            "• Username: @usuario\n"
            "• Chat ID: 123456789"
        )
        return None

def validar_formato_fecha(fecha_str):
    """
    Valida que la fecha tenga el formato DD/MM/YYYY correcto
    """
    try:
        datetime.datetime.strptime(fecha_str, "%d/%m/%Y")
        return True
    except ValueError:
        return False

def parsear_fecha_hora(fecha_str, hora_str):
    """
    Convierte fecha y hora a datetime con timezone
    """
    try:
        # Si no se proporciona fecha, usar hoy
        if not fecha_str:
            fecha_str = datetime.datetime.now(TIMEZONE).strftime("%d/%m/%Y")
        
        fecha_hora_str = f"{fecha_str} {hora_str}"
        fecha_naive = datetime.datetime.strptime(fecha_hora_str, "%d/%m/%Y %H:%M")
        fecha_con_tz = TIMEZONE.localize(fecha_naive)
        
        return fecha_con_tz
    except ValueError:
        return None

def obtener_clima(ciudad):
    """
    Obtiene información del clima para una ciudad específica
    """
    try:
        if not OPENWEATHER_API_KEY:
            return None, "API key de OpenWeatherMap no configurada"
        
        url = f"http://api.openweathermap.org/data/2.5/weather"
        params = {
            'q': ciudad,
            'appid': OPENWEATHER_API_KEY,
            'units': 'metric',
            'lang': 'es'
        }
        
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            
            clima_info = {
                'ciudad': data['name'],
                'pais': data['sys']['country'],
                'temperatura': data['main']['temp'],
                'sensacion': data['main']['feels_like'],
                'humedad': data['main']['humidity'],
                'descripcion': data['weather'][0]['description'],
                'viento': data['wind']['speed']
            }
            
            return clima_info, None
        else:
            return None, f"Error obteniendo clima: {response.status_code}"
            
    except Exception as e:
        return None, f"Error consultando clima: {str(e)}"

def enviar_email(destinatario, asunto, mensaje):
    """
    Envía un email usando Gmail SMTP
    """
    try:
        if not GMAIL_EMAIL or not GMAIL_APP_PASSWORD:
            return False, "Credenciales de Gmail no configuradas"
        
        # Crear el mensaje
        msg = MIMEMultipart()
        msg['From'] = GMAIL_EMAIL
        msg['To'] = destinatario
        msg['Subject'] = asunto
        
        # Cuerpo del mensaje
        msg.attach(MIMEText(mensaje, 'plain', 'utf-8'))
        
        # Configurar servidor SMTP
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        
        # Enviar email
        text = msg.as_string()
        server.sendmail(GMAIL_EMAIL, destinatario, text)
        server.quit()
        
        logger.info(f"Email enviado exitosamente a {destinatario}")
        return True, "Email enviado exitosamente"
        
    except Exception as e:
        logger.error(f"Error enviando email: {e}")
        return False, f"Error enviando email: {str(e)}"

def exportar_backup():
    """
    Exporta configuración y mensajes a JSON
    """
    try:
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Obtener usuarios autorizados
        cur.execute('SELECT * FROM usuarios_autorizados')
        usuarios = [dict(row) for row in cur.fetchall()]
        
        # Obtener mensajes programados activos
        cur.execute('SELECT * FROM mensajes_programados WHERE activo = TRUE')
        mensajes = [dict(row) for row in cur.fetchall()]
        
        # Obtener estadísticas
        cur.execute('SELECT COUNT(*) as total FROM estadisticas WHERE accion = %s', ('mensaje_enviado',))
        stats = cur.fetchone()
        
        backup = {
            'version': '2.0',
            'fecha_backup': datetime.datetime.now(TIMEZONE).isoformat(),
            'usuarios_autorizados': usuarios,
            'mensajes_programados': mensajes,
            'estadisticas': dict(stats) if stats else {},
            'timezone': str(TIMEZONE)
        }
        
        cur.close()
        conn.close()
        
        return json.dumps(backup, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Error exportando backup: {e}")
        return None

def calcular_tiempo_objetivo(hora_str):
    """
    Calcula el datetime objetivo para el mensaje programado
    Si la hora ya pasó hoy, programa para mañana
    Soporta formato 24h (HH:MM) y 12h (H:MM am/pm)
    """
    try:
        ahora = datetime.datetime.now(TIMEZONE)
        hora_str = hora_str.strip().lower()
        
        # Verificar si es formato AM/PM
        if hora_str.endswith('am') or hora_str.endswith('pm'):
            es_pm = hora_str.endswith('pm')
            hora_str = hora_str[:-2].strip()
            
            # Parsear la hora objetivo
            hora_partes = hora_str.split(':')
            hora_objetivo = int(hora_partes[0])
            minuto_objetivo = int(hora_partes[1])
            
            # Convertir a formato 24 horas
            if es_pm and hora_objetivo != 12:
                hora_objetivo += 12
            elif not es_pm and hora_objetivo == 12:
                hora_objetivo = 0
                
            # Crear time object
            hora_obj = datetime.time(hora_objetivo, minuto_objetivo)
        else:
            # Formato 24 horas
            hora_obj = datetime.datetime.strptime(hora_str, "%H:%M").time()
        
        # Crear datetime objetivo para hoy con timezone
        objetivo_naive = datetime.datetime.combine(ahora.date(), hora_obj)
        objetivo = TIMEZONE.localize(objetivo_naive)
        
        # Si la hora ya pasó hoy, programar para mañana
        if objetivo <= ahora:
            objetivo += datetime.timedelta(days=1)
            
        return objetivo
    except (ValueError, IndexError):
        return None

def ping_predice_loto():
    """
    Envía ping al PrediceLotoBot para mantenerlo activo
    """
    try:
        response = requests.get(PREDICE_LOTO_URL, timeout=5)
        logger.info(f"✅ Ping a PrediceLotoBot enviado. Código: {response.status_code}")
        return True
    except Exception as e:
        logger.warning(f"⚠️ Error al hacer ping a PrediceLotoBot: {e}")
        return False

def enviar_mensaje_programado(chat_id, mensaje, mensaje_id, user_id=None):
    """
    Función auxiliar para enviar el mensaje programado
    y removerlo de la lista de mensajes pendientes
    """
    try:
        # Enviar el mensaje
        updater.bot.send_message(
            chat_id=chat_id, 
            text=f"⏰ Mensaje programado:\n{mensaje}"
        )
        
        # Actualizar estadísticas
        estadisticas['mensajes_enviados'] += 1
        if user_id:
            registrar_estadistica(user_id, 'mensaje_enviado', {
                'mensaje': mensaje,
                'chat_id': chat_id,
                'mensaje_id': mensaje_id
            })
        
        # Remover el mensaje de la lista de programados
        global mensajes_programados
        mensajes_programados = [
            msg for msg in mensajes_programados 
            if not (msg.get('id') == mensaje_id)
        ]
        
        logger.info(f"✅ Mensaje programado enviado exitosamente a chat {chat_id}")
        
        # Notificación de confirmación
        try:
            updater.bot.send_message(
                chat_id=chat_id,
                text=f"✅ **Confirmación de envío**\n\n"
                     f"El mensaje programado #{mensaje_id} se envió correctamente.",
                parse_mode='Markdown'
            )
        except:
            pass  # No fallar si no se puede enviar la confirmación
        
    except Exception as e:
        logger.error(f"❌ Error enviando mensaje programado: {e}")
        
        # Notificar error al usuario
        try:
            updater.bot.send_message(
                chat_id=chat_id,
                text=f"❌ **Error en envío programado**\n\n"
                     f"No se pudo enviar el mensaje #{mensaje_id}: {mensaje}",
                parse_mode='Markdown'
            )
        except:
            pass

def crear_menu_principal_mensajeria():
    """Crea el menú principal con botones interactivos para bot de mensajería"""
    keyboard = [
        [
            InlineKeyboardButton("📝 Programar Mensaje", callback_data='programar'),
            InlineKeyboardButton("📅 Programar Fecha", callback_data='programar_fecha')
        ],
        [
            InlineKeyboardButton("🔄 Mensaje Repetitivo", callback_data='repetir'),
            InlineKeyboardButton("📤 Enviar Ahora", callback_data='enviar')
        ],
        [
            InlineKeyboardButton("📋 Ver Programados", callback_data='listar'),
            InlineKeyboardButton("❌ Cancelar Mensaje", callback_data='cancelar')
        ],
        [
            InlineKeyboardButton("📧 Gestión Email", callback_data='email'),
            InlineKeyboardButton("🌤️ Comandos Clima", callback_data='clima')
        ],
        [
            InlineKeyboardButton("👥 Gestión Usuarios", callback_data='usuarios'),
            InlineKeyboardButton("⚙️ Configuración", callback_data='config')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def start(update: Update, context: CallbackContext):
    """
    Comando /start - Mensaje de bienvenida con menú interactivo
    """
    # Enviar ping al PrediceLotoBot para mantenerlo activo
    ping_predice_loto()
    
    user_id = update.effective_user.id if update.effective_user else 0
    
    if not es_usuario_autorizado(user_id):
        update.message.reply_text(
            f"❌ Acceso denegado.\n\n"
            f"No tienes permisos para usar este bot.\n"
            f"Tu ID de usuario es: {user_id}\n\n"
            f"Para autorizar este usuario, un administrador debe usar:\n"
            f"/agregar {user_id}"
        )
        return
    
    # Obtener estadísticas para el dashboard
    data = cargar_mensajes_json()
    total_programados = len(data.get('programados', []))
    total_repetitivos = len(data.get('repetitivos', []))
    
    mensaje_bienvenida = (
        "🤖 **Bot Programador de Mensajes - Dashboard**\n\n"
        f"👤 Usuario: {update.effective_user.first_name}\n"
        f"📝 Mensajes programados: **{total_programados}**\n"
        f"🔄 Mensajes repetitivos: **{total_repetitivos}**\n"
        f"🕒 Última actualización: {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}\n\n"
        "📈 **Estado del sistema:**\n"
        "🟢 Servidor: Activo\n"
        "🟢 Programador: Funcionando\n"
        "🟢 Keep-alive: Conectado\n\n"
        "Selecciona una opción del menú:"
    )
    
    update.message.reply_text(
        mensaje_bienvenida,
        parse_mode='Markdown',
        reply_markup=crear_menu_principal_mensajeria()
    )
    
    logger.info(f"Usuario {user_id} inició el bot")

def callback_handler_mensajeria(update: Update, context: CallbackContext):
    """Maneja las respuestas de los botones inline del bot de mensajería"""
    query = update.callback_query
    query.answer()
    
    user_id = query.from_user.id
    
    if not es_usuario_autorizado(user_id):
        query.edit_message_text("❌ Acceso denegado.")
        return
    
    data = query.data
    
    if data == 'programar':
        query.edit_message_text(
            "📝 **Programar Mensaje**\n\n"
            "Usa el comando: `/programar \"mensaje\" HH:MM [chat_id]`\n\n"
            "**Ejemplos:**\n"
            "• `/programar \"Reunión en 30 min\" 14:30`\n"
            "• `/programar \"Recordatorio\" 09:00 @username`\n"
            "• `/programar \"Mensaje\" 15:45 123456789`\n\n"
            "💡 Si la hora ya pasó, se programará para mañana",
            parse_mode='Markdown',
            reply_markup=crear_menu_volver_mensajeria()
        )
        
    elif data == 'programar_fecha':
        query.edit_message_text(
            "📅 **Programar para Fecha Específica**\n\n"
            "Usa el comando: `/programar_fecha \"mensaje\" DD/MM/YYYY HH:MM`\n\n"
            "**Ejemplos:**\n"
            "• `/programar_fecha \"Feliz cumpleaños\" 15/06/2025 00:00`\n"
            "• `/programar_fecha \"Recordatorio\" 01/07/2025 09:00`\n\n"
            "📅 Formato de fecha: DD/MM/YYYY\n"
            "🕐 Formato de hora: HH:MM (24 horas)",
            parse_mode='Markdown',
            reply_markup=crear_menu_volver_mensajeria()
        )
        
    elif data == 'repetir':
        query.edit_message_text(
            "🔄 **Mensaje Repetitivo**\n\n"
            "Usa el comando: `/repetir \"mensaje\" HH:MM intervalo [chat_id]`\n\n"
            "**Intervalos disponibles:**\n"
            "• `diario` - Todos los días\n"
            "• `semanal` - Cada semana\n"
            "• `mensual` - Cada mes\n\n"
            "**Ejemplos:**\n"
            "• `/repetir \"Buenos días\" 08:00 diario`\n"
            "• `/repetir \"Reunión semanal\" 14:00 semanal`",
            parse_mode='Markdown',
            reply_markup=crear_menu_volver_mensajeria()
        )
        
    elif data == 'enviar':
        query.edit_message_text(
            "📤 **Enviar Mensaje Inmediato**\n\n"
            "Usa el comando: `/enviar \"mensaje\" [destinatario]`\n\n"
            "**Ejemplos:**\n"
            "• `/enviar \"Hola mundo\"`\n"
            "• `/enviar \"Mensaje urgente\" @username`\n"
            "• `/enviar \"Notificación\" 123456789`\n\n"
            "📨 Si no especificas destinatario, se envía a este chat",
            parse_mode='Markdown',
            reply_markup=crear_menu_volver_mensajeria()
        )
        
    elif data == 'listar':
        # Mostrar mensajes programados
        data_msg = cargar_mensajes_json()
        programados = data_msg.get('programados', [])
        repetitivos = data_msg.get('repetitivos', [])
        
        if not programados and not repetitivos:
            query.edit_message_text(
                "📋 **Mensajes Programados**\n\n"
                "⚠️ No hay mensajes programados.\n\n"
                "Usa los botones del menú para programar nuevos mensajes.",
                parse_mode='Markdown',
                reply_markup=crear_menu_volver_mensajeria()
            )
            return
            
        mensaje = "📋 **Mensajes Programados**\n\n"
        
        if programados:
            mensaje += "📝 **Mensajes únicos:**\n"
            for i, msg in enumerate(programados, 1):
                fecha = msg.get('fecha_objetivo', 'Sin fecha')
                texto = msg.get('mensaje', 'Sin mensaje')[:30] + "..."
                mensaje += f"{i}. {fecha}: {texto}\n"
        
        if repetitivos:
            mensaje += "\n🔄 **Mensajes repetitivos:**\n"
            for i, msg in enumerate(repetitivos, 1):
                hora = msg.get('hora', 'Sin hora')
                intervalo = msg.get('intervalo', 'Sin intervalo')
                texto = msg.get('mensaje', 'Sin mensaje')[:30] + "..."
                mensaje += f"{i}. {hora} ({intervalo}): {texto}\n"
                
        query.edit_message_text(
            mensaje,
            parse_mode='Markdown',
            reply_markup=crear_menu_volver_mensajeria()
        )
        
    elif data == 'cancelar':
        query.edit_message_text(
            "❌ **Cancelar Mensaje**\n\n"
            "Usa el comando: `/cancelar <número>`\n\n"
            "**Pasos:**\n"
            "1. Ve los mensajes con 📋 Ver Programados\n"
            "2. Identifica el número del mensaje\n"
            "3. Usa `/cancelar 1` (ejemplo)\n\n"
            "💡 También puedes usar `/listar` para ver los números",
            parse_mode='Markdown',
            reply_markup=crear_menu_volver_mensajeria()
        )
        
    elif data == 'email':
        # Menú gestión email
        keyboard = [
            [
                InlineKeyboardButton("📧 Enviar Email", callback_data='email_enviar'),
                InlineKeyboardButton("⏰ Email Programado", callback_data='email_programar')
            ],
            [
                InlineKeyboardButton("🌤️ Clima por Email", callback_data='clima_email'),
                InlineKeyboardButton("📋 Estado Email", callback_data='email_status')
            ],
            [InlineKeyboardButton("🔙 Volver", callback_data='menu')]
        ]
        
        query.edit_message_text(
            "📧 **Gestión de Email**\n\n"
            "Administra el envío de emails:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    elif data == 'clima':
        # Menú comandos clima
        keyboard = [
            [
                InlineKeyboardButton("🌤️ Consultar Clima", callback_data='clima_consultar'),
                InlineKeyboardButton("📧 Clima por Email", callback_data='clima_email_cmd')
            ],
            [InlineKeyboardButton("🔙 Volver", callback_data='menu')]
        ]
        
        query.edit_message_text(
            "🌤️ **Comandos de Clima**\n\n"
            "Consulta información meteorológica:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    elif data == 'usuarios':
        # Menú gestión usuarios
        keyboard = [
            [
                InlineKeyboardButton("➕ Agregar Usuario", callback_data='user_add'),
                InlineKeyboardButton("➖ Remover Usuario", callback_data='user_remove')
            ],
            [
                InlineKeyboardButton("👥 Lista Usuarios", callback_data='user_list'),
                InlineKeyboardButton("🆔 Mi Chat ID", callback_data='chat_id')
            ],
            [InlineKeyboardButton("🔙 Volver", callback_data='menu')]
        ]
        
        query.edit_message_text(
            "👥 **Gestión de Usuarios**\n\n"
            "Administra permisos de acceso:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    elif data == 'config':
        # Menú configuración
        keyboard = [
            [
                InlineKeyboardButton("📊 Estadísticas", callback_data='estadisticas'),
                InlineKeyboardButton("💾 Backup", callback_data='backup')
            ],
            [
                InlineKeyboardButton("ℹ️ Ayuda", callback_data='ayuda'),
                InlineKeyboardButton("🔧 Estado Sistema", callback_data='status')
            ],
            [InlineKeyboardButton("🔙 Volver", callback_data='menu')]
        ]
        
        query.edit_message_text(
            "⚙️ **Configuración**\n\n"
            "Gestiona las opciones del bot:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    elif data == 'menu':
        # Volver al menú principal
        data_menu = cargar_mensajes_json()
        total_programados = len(data_menu.get('programados', []))
        total_repetitivos = len(data_menu.get('repetitivos', []))
        
        mensaje_bienvenida = (
            "🤖 **Bot Programador de Mensajes - Dashboard**\n\n"
            f"👤 Usuario: {query.from_user.first_name}\n"
            f"📝 Mensajes programados: **{total_programados}**\n"
            f"🔄 Mensajes repetitivos: **{total_repetitivos}**\n"
            f"🕒 Última actualización: {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}\n\n"
            "📈 **Estado del sistema:**\n"
            "🟢 Servidor: Activo\n"
            "🟢 Programador: Funcionando\n"
            "🟢 Keep-alive: Conectado\n\n"
            "Selecciona una opción del menú:"
        )
        
        query.edit_message_text(
            mensaje_bienvenida,
            parse_mode='Markdown',
            reply_markup=crear_menu_principal_mensajeria()
        )
        
    # Submenús detallados
    elif data == 'email_enviar':
        query.edit_message_text(
            "📧 **Enviar Email Inmediato**\n\n"
            "Usa el comando: `/email \"asunto\" \"mensaje\" destinatario@email.com`\n\n"
            "**Ejemplo:**\n"
            "• `/email \"Recordatorio\" \"No olvides la reunión\" usuario@gmail.com`\n\n"
            "📨 El email se enviará inmediatamente",
            parse_mode='Markdown',
            reply_markup=crear_menu_volver_mensajeria()
        )
        
    elif data == 'email_programar':
        query.edit_message_text(
            "⏰ **Email Programado**\n\n"
            "Usa el comando: `/programar_email \"asunto\" \"mensaje\" HH:MM destinatario@email.com`\n\n"
            "**Ejemplo:**\n"
            "• `/programar_email \"Reunión\" \"Recordatorio de reunión\" 14:30 jefe@empresa.com`\n\n"
            "📅 Si la hora ya pasó, se programará para mañana",
            parse_mode='Markdown',
            reply_markup=crear_menu_volver_mensajeria()
        )
        
    elif data == 'clima_consultar':
        query.edit_message_text(
            "🌤️ **Consultar Clima**\n\n"
            "Usa el comando: `/clima ciudad`\n\n"
            "**Ejemplos:**\n"
            "• `/clima Madrid`\n"
            "• `/clima Nueva York`\n"
            "• `/clima La Habana`\n\n"
            "🌍 Funciona con cualquier ciudad del mundo",
            parse_mode='Markdown',
            reply_markup=crear_menu_volver_mensajeria()
        )
        
    elif data == 'clima_email_cmd':
        query.edit_message_text(
            "📧 **Clima por Email**\n\n"
            "Usa el comando: `/clima_email ciudad destinatario@email.com`\n\n"
            "**Ejemplo:**\n"
            "• `/clima_email Barcelona usuario@gmail.com`\n\n"
            "🌤️ Envía el reporte meteorológico por email",
            parse_mode='Markdown',
            reply_markup=crear_menu_volver_mensajeria()
        )
        
    elif data == 'user_add':
        query.edit_message_text(
            "➕ **Agregar Usuario**\n\n"
            "Usa el comando: `/agregar <user_id>`\n\n"
            "**Pasos:**\n"
            "1. El usuario debe enviarte un mensaje primero\n"
            "2. Copia su ID de usuario del log\n"
            "3. Usa `/agregar 123456789`\n\n"
            "👤 Solo administradores pueden agregar usuarios",
            parse_mode='Markdown',
            reply_markup=crear_menu_volver_mensajeria()
        )
        
    elif data == 'user_remove':
        query.edit_message_text(
            "➖ **Remover Usuario**\n\n"
            "Usa el comando: `/remover <user_id>`\n\n"
            "**Ejemplo:**\n"
            "• `/remover 123456789`\n\n"
            "⚠️ El usuario perderá acceso al bot inmediatamente",
            parse_mode='Markdown',
            reply_markup=crear_menu_volver_mensajeria()
        )
        
    elif data == 'user_list':
        # Mostrar usuarios autorizados
        try:
            usuarios = cargar_usuarios_autorizados()
            if usuarios:
                mensaje = "👥 **Usuarios Autorizados:**\n\n"
                for usuario in usuarios:
                    user_id = usuario.get('user_id', 'Sin ID')
                    username = usuario.get('username', 'Sin username')
                    mensaje += f"• ID: {user_id} (@{username})\n"
            else:
                mensaje = "👥 **Usuarios Autorizados:**\n\n⚠️ No hay usuarios registrados"
        except:
            mensaje = "👥 **Usuarios Autorizados:**\n\n❌ Error al cargar la lista"
            
        query.edit_message_text(
            mensaje,
            parse_mode='Markdown',
            reply_markup=crear_menu_volver_mensajeria()
        )
        
    elif data == 'chat_id':
        chat_id = query.message.chat_id
        query.edit_message_text(
            f"🆔 **Información del Chat**\n\n"
            f"**Chat ID:** `{chat_id}`\n"
            f"**Usuario ID:** `{user_id}`\n"
            f"**Username:** @{query.from_user.username or 'Sin username'}\n"
            f"**Nombre:** {query.from_user.first_name}\n\n"
            "💡 Usa estos IDs para enviar mensajes específicos",
            parse_mode='Markdown',
            reply_markup=crear_menu_volver_mensajeria()
        )
        
    elif data == 'estadisticas':
        try:
            stats = cargar_estadisticas_json()
            total_acciones = len(stats.get('acciones', []))
            usuarios_activos = len(set(accion.get('user_id') for accion in stats.get('acciones', [])))
            
            mensaje = (
                "📊 **Estadísticas del Bot**\n\n"
                f"📈 Total de acciones: **{total_acciones}**\n"
                f"👥 Usuarios activos: **{usuarios_activos}**\n"
                f"📅 Fecha: {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}\n\n"
                "📋 **Acciones recientes:**\n"
            )
            
            # Mostrar últimas 5 acciones
            for accion in stats.get('acciones', [])[-5:]:
                fecha = accion.get('timestamp', 'Sin fecha')
                comando = accion.get('accion', 'Sin acción')
                mensaje += f"• {fecha}: {comando}\n"
                
        except:
            mensaje = "📊 **Estadísticas del Bot**\n\n❌ Error al cargar estadísticas"
            
        query.edit_message_text(
            mensaje,
            parse_mode='Markdown',
            reply_markup=crear_menu_volver_mensajeria()
        )
        
    elif data == 'backup':
        query.edit_message_text(
            "💾 **Backup de Configuración**\n\n"
            "Usa el comando: `/backup`\n\n"
            "📋 **El backup incluye:**\n"
            "• Lista de mensajes programados\n"
            "• Mensajes repetitivos\n"
            "• Usuarios autorizados\n"
            "• Estadísticas del bot\n\n"
            "📁 Se genera un archivo JSON para descargar",
            parse_mode='Markdown',
            reply_markup=crear_menu_volver_mensajeria()
        )
        
    elif data == 'ayuda':
        query.edit_message_text(
            "ℹ️ **Ayuda del Bot**\n\n"
            "Usa el comando: `/ayuda`\n\n"
            "📖 **Información disponible:**\n"
            "• Limitaciones del bot\n"
            "• Mejores prácticas\n"
            "• Solución de problemas\n"
            "• Formatos de hora y fecha\n\n"
            "💡 Consulta la ayuda completa con el comando",
            parse_mode='Markdown',
            reply_markup=crear_menu_volver_mensajeria()
        )
        
    elif data == 'status':
        # Estado del sistema
        data_status = cargar_mensajes_json()
        programados = len(data_status.get('programados', []))
        repetitivos = len(data_status.get('repetitivos', []))
        
        query.edit_message_text(
            "🔧 **Estado del Sistema**\n\n"
            "📊 **Métricas actuales:**\n"
            f"• Mensajes programados: {programados}\n"
            f"• Mensajes repetitivos: {repetitivos}\n"
            f"• Hora del servidor: {datetime.datetime.now(TIMEZONE).strftime('%H:%M:%S')}\n"
            f"• Fecha: {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y')}\n\n"
            "🟢 **Servicios:**\n"
            "• Bot de Telegram: Activo\n"
            "• Programador: Funcionando\n"
            "• Keep-alive: Conectado\n"
            "• Base de datos: Operativa",
            parse_mode='Markdown',
            reply_markup=crear_menu_volver_mensajeria()
        )

def crear_menu_volver_mensajeria():
    """Crea un botón para volver al menú principal del bot de mensajería"""
    keyboard = [[InlineKeyboardButton("🔙 Volver al Menú", callback_data='menu')]]
    return InlineKeyboardMarkup(keyboard)

def enviar(update: Update, context: CallbackContext):
    """
    Comando /enviar - Envía un mensaje inmediatamente
    Formato: /enviar "mensaje"
    """
    # Enviar ping al PrediceLotoBot para mantenerlo activo
    ping_predice_loto()
    
    user_id = update.effective_user.id if update.effective_user else 0
    
    if not es_usuario_autorizado(user_id):
        update.message.reply_text(
            "❌ **Acceso denegado.**\n\n"
            "No tienes permisos para usar este bot.",
            parse_mode='Markdown'
        )
        return
    
    try:
        if not context.args or len(context.args) < 1:
            update.message.reply_text(
                "❌ **Formato incorrecto.**\n\n"
                "**Uso correcto:** `/enviar \"mensaje\"`\n"
                "**Ejemplo:** `/enviar \"Mensaje urgente\"`",
                parse_mode='Markdown'
            )
            return

        # Procesar argumentos del comando /enviar
        if len(context.args) == 1:
            # Solo un argumento, es el mensaje completo
            mensaje = context.args[0].strip('"\'')
            chat_destino = update.message.chat_id
        else:
            # Múltiples argumentos - verificar si el último es un chat ID
            ultimo_arg = context.args[-1]
            if ultimo_arg.isdigit() or ultimo_arg.startswith('@') or ultimo_arg.startswith('+'):
                # El último argumento parece ser un destinatario
                mensaje = ' '.join(context.args[:-1]).strip('"\'')
                destinatario = ultimo_arg
                chat_destino = procesar_destinatario(destinatario, update)
                if chat_destino is None:
                    return
            else:
                # Todos los argumentos son parte del mensaje
                mensaje = ' '.join(context.args).strip('"\'')
                chat_destino = update.message.chat_id
        
        try:
            # Enviar el mensaje al destinatario especificado
            if chat_destino != update.message.chat_id:
                # Enviar a otro chat
                updater.bot.send_message(
                    chat_id=chat_destino,
                    text=f"📨 {mensaje}"
                )
                # Confirmar al usuario que envió
                update.message.reply_text(
                    f"✅ **Mensaje enviado exitosamente**\n\n"
                    f"📝 **Mensaje:** {mensaje}\n"
                    f"🎯 **Destinatario:** {chat_destino}",
                    parse_mode='Markdown'
                )
            else:
                # Enviar al chat actual
                update.message.reply_text(
                    f"📨 **Mensaje enviado:**\n{mensaje}",
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            update.message.reply_text(
                f"❌ **Error enviando mensaje:**\n\n"
                f"No se pudo enviar a {chat_destino}. Posibles causas:\n"
                f"• El usuario no escribió /start al bot\n"
                f"• El chat ID no existe\n"
                f"• El bot no tiene permisos\n\n"
                f"**Error técnico:** {str(e)}",
                parse_mode='Markdown'
            )
            logger.error(f"Error enviando mensaje a {chat_destino}: {e}")
            return
        
        logger.info(f"Usuario {user_id} envió mensaje inmediato: {mensaje}")
        
    except Exception as e:
        update.message.reply_text(
            f"❌ **Error inesperado:** {str(e)}",
            parse_mode='Markdown'
        )
        logger.error(f"Error en comando enviar: {e}")

def programar(update: Update, context: CallbackContext):
    """
    Comando /programar - Programa un mensaje para ser enviado automáticamente
    Formato: /programar "mensaje" HH:MM [chat_id]
    """
    user_id = update.effective_user.id if update.effective_user else 0
    
    if not es_usuario_autorizado(user_id):
        update.message.reply_text(
            "❌ Acceso denegado.\n\n"
            "No tienes permisos para usar este bot."
        )
        return
    
    try:
        # Validar que se proporcionaron los argumentos necesarios
        if not context.args or len(context.args) < 2:
            update.message.reply_text(
                "❌ Formato incorrecto.\n\n"
                "Uso correcto: /programar \"mensaje\" HH:MM [@usuario o número]\n"
                "Ejemplos:\n"
                "• /programar \"Recordatorio\" 14:30\n"
                "• /programar \"Hola\" 15:00 @raul123\n"
                "• /programar \"Reunión\" 16:30 +584121234567"
            )
            return

        # Reconstruir el mensaje desde las comillas
        texto_completo = ' '.join(context.args)
        
        # Extraer mensaje entre comillas
        if texto_completo.startswith('"') and '"' in texto_completo[1:]:
            fin_mensaje = texto_completo.index('"', 1)
            mensaje = texto_completo[1:fin_mensaje]
            resto_args = texto_completo[fin_mensaje+1:].strip().split()
        else:
            # Fallback si no hay comillas
            mensaje = context.args[0].strip('"\'')
            resto_args = context.args[1:]
        
        if len(resto_args) < 1:
            update.message.reply_text(
                "❌ Formato incorrecto.\n\n"
                "Uso correcto: /programar \"mensaje\" HH:MM [@usuario o número]\n"
                "Ejemplos:\n"
                "• /programar \"Recordatorio\" 14:30\n"
                "• /programar \"Hola\" 3:00pm @raul123\n"
                "• /programar \"Reunión\" 16:30 +584121234567"
            )
            return
            
        hora = resto_args[0]
        
        # Extraer destinatario si se proporciona
        chat_destino = update.effective_chat.id if update.effective_chat else update.message.chat_id  # Por defecto, el chat actual
        if len(resto_args) > 1:
            destinatario = resto_args[1]
            chat_destino = procesar_destinatario(destinatario, update)
            if chat_destino is None:
                return
        
        # Validar formato de hora
        if not validar_formato_hora(hora):
            update.message.reply_text(
                "❌ **Formato de hora incorrecto.**\n\n"
                "**Formatos válidos:**\n"
                "• **24 horas:** HH:MM (ejemplo: 14:30)\n"
                "• **12 horas:** H:MMam/pm (ejemplo: 2:30pm)",
                parse_mode='Markdown'
            )
            return

        # Calcular tiempo objetivo
        objetivo = calcular_tiempo_objetivo(hora)
        if objetivo is None:
            update.message.reply_text("❌ Error procesando la hora proporcionada.")
            return

        # Calcular delay en segundos
        ahora = datetime.datetime.now()
        delay = (objetivo - ahora).total_seconds()
        
        # Crear ID único para el mensaje
        mensaje_id = len(mensajes_programados) + 1
        
        # Crear y iniciar timer
        timer = threading.Timer(
            delay, 
            enviar_mensaje_programado, 
            args=(chat_destino, mensaje, mensaje_id, user_id)
        )
        timer.start()

        # Guardar información del mensaje programado
        username = "Usuario"
        if update.effective_user:
            username = update.effective_user.username or update.effective_user.first_name or "Usuario"
            
        mensaje_programado = {
            'id': mensaje_id,
            'mensaje': mensaje,
            'hora': hora,
            'chat_id': chat_destino,
            'timer': timer,
            'fecha_objetivo': objetivo,
            'usuario': username
        }
        
        mensajes_programados.append(mensaje_programado)
        
        # Guardar en JSON
        mensaje_json = {
            "id": mensaje_id,
            "mensaje": mensaje,
            "hora": hora,
            "fecha": objetivo.strftime("%Y-%m-%d") if objetivo.date() != ahora.date() else None,
            "repetir": False,
            "intervalo_horas": None,
            "usuarios": [user_id],
            "tipo": "una_vez",
            "chat_id": chat_destino,
            "fecha_creacion": ahora.isoformat(),
            "fecha_objetivo": objetivo.isoformat(),
            "usuario": username,
            "activo": True
        }
        agregar_mensaje_programado_json(mensaje_json)
        
        # Actualizar estadísticas
        estadisticas['mensajes_programados_total'] += 1
        estadisticas['usuarios_activos'].add(user_id)
        registrar_estadistica(user_id, 'mensaje_programado', {
            'mensaje': mensaje,
            'hora': hora,
            'fecha_objetivo': objetivo.isoformat()
        })
        registrar_accion_json(user_id, 'mensaje_programado', {
            'mensaje': mensaje,
            'hora': hora,
            'fecha_objetivo': objetivo.isoformat()
        })
        
        # Confirmar programación
        fecha_str = objetivo.strftime("%d/%m/%Y")
        if objetivo.date() == ahora.date():
            fecha_info = "hoy"
        else:
            fecha_info = f"mañana ({fecha_str})"
            
        update.message.reply_text(
            f"✅ **Mensaje programado exitosamente**\n\n"
            f"📝 **Mensaje:** {mensaje}\n"
            f"⏰ **Hora:** {hora} ({fecha_info})\n"
            f"🔢 **ID:** #{mensaje_id}\n"
            f"🌍 **Zona horaria:** {TIMEZONE}",
            parse_mode='Markdown'
        )
        
        logger.info(f"Mensaje programado por usuario {user_id} para {objetivo}")
        
    except IndexError:
        update.message.reply_text(
            "❌ **Argumentos insuficientes.**\n\n"
            "**Uso:** /programar \"mensaje\" HH:MM\n"
            "**Ejemplo:** /programar \"Tomar medicamento\" 20:00",
            parse_mode='Markdown'
        )
    except Exception as e:
        update.message.reply_text(
            f"❌ **Error inesperado:** {str(e)}\n\n"
            "Verifica el formato: /programar \"mensaje\" HH:MM",
            parse_mode='Markdown'
        )
        logger.error(f"Error en comando programar: {e}")

def repetir(update: Update, context: CallbackContext):
    """
    Comando /repetir - Programa un mensaje repetitivo
    Formato: /repetir "mensaje" HH:MM intervalo
    """
    user_id = update.effective_user.id if update.effective_user else 0
    
    if not es_usuario_autorizado(user_id):
        update.message.reply_text(
            "❌ **Acceso denegado.**\n\n"
            "No tienes permisos para usar este bot.",
            parse_mode='Markdown'
        )
        return
    
    try:
        if not context.args or len(context.args) < 3:
            update.message.reply_text(
                "❌ **Formato incorrecto.**\n\n"
                "**Uso correcto:** `/repetir \"mensaje\" HH:MM intervalo [@usuario o número]`\n"
                "**Ejemplos:**\n"
                "• `/repetir \"Buenos días\" 08:00 diario`\n"
                "• `/repetir \"Recordatorio\" 17:40 diario @raul123`\n"
                "• `/repetir \"Aviso\" 12:00 semanal +584121234567`\n"
                "**Intervalos válidos:** diario, semanal, mensual",
                parse_mode='Markdown'
            )
            return

        # Reconstruir el mensaje desde las comillas
        texto_completo = ' '.join(context.args)
        
        # Extraer mensaje entre comillas
        if texto_completo.startswith('"') and '"' in texto_completo[1:]:
            fin_mensaje = texto_completo.index('"', 1)
            mensaje = texto_completo[1:fin_mensaje]
            resto_args = texto_completo[fin_mensaje+1:].strip().split()
        else:
            # Fallback si no hay comillas
            mensaje = context.args[0].strip('"\'')
            resto_args = context.args[1:]
        
        if len(resto_args) < 2:
            update.message.reply_text(
                "❌ **Formato incorrecto.**\n\n"
                "**Uso correcto:** `/repetir \"mensaje\" HH:MM intervalo [@usuario o número]`\n"
                "**Ejemplo:** `/repetir \"Buenos días\" 08:00 diario`",
                parse_mode='Markdown'
            )
            return
            
        hora = resto_args[0]
        intervalo = resto_args[1].lower()
        
        # Extraer destinatario si se proporciona (opcional)
        chat_destino = update.message.chat_id  # Por defecto, el chat actual
        if len(resto_args) > 2:
            destinatario = resto_args[2]
            chat_destino = procesar_destinatario(destinatario, update)
            if chat_destino is None:
                return
        
        if not validar_formato_hora(hora):
            update.message.reply_text(
                "❌ **Formato de hora incorrecto.**\n\n"
                "**Formato válido:** HH:MM (ejemplo: 14:30)",
                parse_mode='Markdown'
            )
            return
            
        if not validar_intervalo(intervalo):
            update.message.reply_text(
                "❌ **Intervalo inválido.**\n\n"
                "**Intervalos válidos:** diario, semanal, mensual",
                parse_mode='Markdown'
            )
            return
        
        mensaje_repetitivo = {
            'id': len(mensajes_repetitivos) + 1,
            'mensaje': mensaje,
            'hora': hora,
            'intervalo': intervalo,
            'chat_id': chat_destino,
            'activo': True,
            'usuario': user_id
        }
        
        mensajes_repetitivos.append(mensaje_repetitivo)
        
        # Guardar en JSON
        intervalo_horas = 24 if intervalo == 'diario' else (168 if intervalo == 'semanal' else 720)  # mensual
        mensaje_repetitivo_json = {
            "id": mensaje_repetitivo['id'],
            "mensaje": mensaje,
            "hora": hora,
            "fecha": None,
            "repetir": True,
            "intervalo_horas": intervalo_horas,
            "usuarios": [user_id],
            "tipo": intervalo,
            "chat_id": chat_destino,
            "fecha_creacion": datetime.datetime.now(TIMEZONE).isoformat(),
            "usuario": user_id,
            "activo": True
        }
        agregar_mensaje_repetitivo_json(mensaje_repetitivo_json)
        registrar_accion_json(user_id, 'mensaje_repetitivo_programado', {
            'mensaje': mensaje,
            'hora': hora,
            'intervalo': intervalo
        })
        
        update.message.reply_text(
            f"✅ **Mensaje repetitivo programado**\n\n"
            f"📝 **Mensaje:** {mensaje}\n"
            f"⏰ **Hora:** {hora}\n"
            f"🔄 **Intervalo:** {intervalo}\n"
            f"🔢 **ID:** #{mensaje_repetitivo['id']}",
            parse_mode='Markdown'
        )
        
        logger.info(f"Usuario {user_id} programó mensaje repetitivo: {mensaje}")
        
    except Exception as e:
        update.message.reply_text(f"❌ **Error:** {str(e)}")
        logger.error(f"Error en comando repetir: {e}")

def listar(update: Update, context: CallbackContext):
    """
    Comando /listar - Muestra todos los mensajes programados pendientes
    """
    user_id = update.effective_user.id if update.effective_user else 0
    
    if not es_usuario_autorizado(user_id):
        update.message.reply_text(
            "❌ **Acceso denegado.**\n\n"
            "No tienes permisos para usar este bot.",
            parse_mode='Markdown'
        )
        return
    
    # Filtrar mensajes activos (timers que no han expirado)
    mensajes_activos = [
        msg for msg in mensajes_programados 
        if msg['timer'].is_alive()
    ]
    
    # Filtrar mensajes repetitivos activos
    repetitivos_activos = [
        msg for msg in mensajes_repetitivos
        if msg['activo']
    ]
    
    if not mensajes_activos and not repetitivos_activos:
        update.message.reply_text(
            "📭 **No hay mensajes programados pendientes.**\n\n"
            "Usa `/programar \"mensaje\" HH:MM` para agendar uno único.\n"
            "Usa `/repetir \"mensaje\" HH:MM intervalo` para uno repetitivo.",
            parse_mode='Markdown'
        )
        return

    # Construir lista de mensajes
    texto = "📋 **Mensajes programados:**\n\n"
    ahora = datetime.datetime.now()
    
    # Mensajes únicos
    if mensajes_activos:
        texto += "🔸 **Mensajes únicos:**\n"
        for msg in mensajes_activos:
            fecha_objetivo = msg['fecha_objetivo']
            
            # Calcular tiempo restante
            tiempo_restante = fecha_objetivo - ahora
            horas_restantes = int(tiempo_restante.total_seconds() // 3600)
            minutos_restantes = int((tiempo_restante.total_seconds() % 3600) // 60)
            
            # Determinar si es hoy o mañana
            if fecha_objetivo.date() == ahora.date():
                fecha_info = "hoy"
            else:
                fecha_info = f"{fecha_objetivo.strftime('%d/%m/%Y')}"
            
            texto += (
                f"**#{msg['id']}** - {msg['mensaje']}\n"
                f"⏰ {msg['hora']} ({fecha_info})\n"
                f"⌛ Faltan {horas_restantes}h {minutos_restantes}m\n\n"
            )
    
    # Mensajes repetitivos
    if repetitivos_activos:
        texto += "🔄 **Mensajes repetitivos:**\n"
        for msg in repetitivos_activos:
            texto += (
                f"**#R{msg['id']}** - {msg['mensaje']}\n"
                f"⏰ {msg['hora']} ({msg['intervalo']})\n\n"
            )
    
    total = len(mensajes_activos) + len(repetitivos_activos)
    texto += f"📊 **Total:** {total} mensaje(s) pendiente(s)"
    
    update.message.reply_text(texto, parse_mode='Markdown')
    logger.info(f"Usuario {user_id} consultó lista de mensajes")

def cancelar(update: Update, context: CallbackContext):
    """
    Comando /cancelar - Cancela un mensaje programado por su ID
    """
    user_id = update.effective_user.id if update.effective_user else 0
    
    if not es_usuario_autorizado(user_id):
        update.message.reply_text(
            "❌ **Acceso denegado.**\n\n"
            "No tienes permisos para usar este bot.",
            parse_mode='Markdown'
        )
        return
    
    try:
        if not context.args or len(context.args) != 1:
            update.message.reply_text(
                "❌ **Formato incorrecto.**\n\n"
                "**Uso:** `/cancelar <número>`\n"
                "**Ejemplo:** `/cancelar 1` o `/cancelar R2`\n\n"
                "Usa `/listar` para ver los IDs disponibles.",
                parse_mode='Markdown'
            )
            return
        
        arg = context.args[0]
        
        # Verificar si es un mensaje repetitivo (formato R#)
        if arg.upper().startswith('R'):
            try:
                mensaje_id = int(arg[1:])
                # Buscar mensaje repetitivo
                mensaje_encontrado = None
                for msg in mensajes_repetitivos:
                    if msg['id'] == mensaje_id and msg['activo']:
                        mensaje_encontrado = msg
                        break
                
                if not mensaje_encontrado:
                    update.message.reply_text(
                        f"❌ **Mensaje repetitivo #R{mensaje_id} no encontrado.**\n\n"
                        "Usa `/listar` para ver los mensajes pendientes.",
                        parse_mode='Markdown'
                    )
                    return
                
                # Desactivar mensaje repetitivo
                mensaje_encontrado['activo'] = False
                
                update.message.reply_text(
                    f"✅ **Mensaje repetitivo #R{mensaje_id} cancelado**\n\n"
                    f"📝 **Mensaje:** {mensaje_encontrado['mensaje']}\n"
                    f"⏰ **Hora:** {mensaje_encontrado['hora']}\n"
                    f"🔄 **Intervalo:** {mensaje_encontrado['intervalo']}",
                    parse_mode='Markdown'
                )
                
                logger.info(f"Usuario {user_id} canceló mensaje repetitivo #R{mensaje_id}")
                
            except ValueError:
                update.message.reply_text(
                    "❌ **ID de mensaje repetitivo inválido.**\n\n"
                    "Formato correcto: R seguido de número (ejemplo: R1)",
                    parse_mode='Markdown'
                )
        else:
            # Mensaje único
            mensaje_id = int(arg)
            
            # Buscar el mensaje por ID
            mensaje_encontrado = None
            for msg in mensajes_programados:
                if msg['id'] == mensaje_id and msg['timer'].is_alive():
                    mensaje_encontrado = msg
                    break
            
            if not mensaje_encontrado:
                update.message.reply_text(
                    f"❌ **Mensaje #{mensaje_id} no encontrado o ya expirado.**\n\n"
                    "Usa `/listar` para ver los mensajes pendientes.",
                    parse_mode='Markdown'
                )
                return
            
            # Cancelar el timer
            mensaje_encontrado['timer'].cancel()
            
            # Remover de la lista
            mensajes_programados.remove(mensaje_encontrado)
            
            update.message.reply_text(
                f"✅ **Mensaje #{mensaje_id} cancelado exitosamente**\n\n"
                f"📝 **Mensaje cancelado:** {mensaje_encontrado['mensaje']}\n"
                f"⏰ **Hora programada:** {mensaje_encontrado['hora']}",
                parse_mode='Markdown'
            )
            
            logger.info(f"Usuario {user_id} canceló mensaje #{mensaje_id}")
        
    except ValueError:
        update.message.reply_text(
            "❌ **ID inválido.**\n\n"
            "El ID debe ser un número. Usa `/listar` para ver los IDs válidos.",
            parse_mode='Markdown'
        )
    except Exception as e:
        update.message.reply_text(f"❌ **Error:** {str(e)}")
        logger.error(f"Error en comando cancelar: {e}")

def agregar(update: Update, context: CallbackContext):
    """
    Comando /agregar - Autoriza un usuario para usar el bot
    """
    user_id = update.effective_user.id if update.effective_user else 0
    
    # Solo usuarios ya autorizados pueden agregar otros
    if not es_usuario_autorizado(user_id):
        update.message.reply_text(
            "❌ **Acceso denegado.**\n\n"
            "No tienes permisos para usar este bot.",
            parse_mode='Markdown'
        )
        return
    
    try:
        if not context.args or len(context.args) != 1:
            update.message.reply_text(
                "❌ **Formato incorrecto.**\n\n"
                "**Uso:** `/agregar <user_id>`\n"
                "**Ejemplo:** `/agregar 123456789`",
                parse_mode='Markdown'
            )
            return
        
        nuevo_user_id = int(context.args[0])
        
        if nuevo_user_id in usuarios_autorizados:
            update.message.reply_text(
                f"⚠️ **Usuario {nuevo_user_id} ya está autorizado.**",
                parse_mode='Markdown'
            )
            return
        
        usuarios_autorizados.add(nuevo_user_id)
        
        # Guardar en JSON
        actualizar_usuario_autorizado_json(nuevo_user_id, 'agregar')
        registrar_accion_json(user_id, 'usuario_autorizado', {
            'nuevo_user_id': nuevo_user_id,
            'accion': 'agregar'
        })
        
        update.message.reply_text(
            f"✅ **Usuario {nuevo_user_id} autorizado exitosamente.**\n\n"
            f"Ahora puede usar todos los comandos del bot.",
            parse_mode='Markdown'
        )
        
        logger.info(f"Usuario {user_id} autorizó a usuario {nuevo_user_id}")
        
    except ValueError:
        update.message.reply_text(
            "❌ **ID de usuario inválido.**\n\n"
            "El ID debe ser un número.",
            parse_mode='Markdown'
        )
    except Exception as e:
        update.message.reply_text(f"❌ **Error:** {str(e)}")
        logger.error(f"Error en comando agregar: {e}")

def remover(update: Update, context: CallbackContext):
    """
    Comando /remover - Desautoriza un usuario del bot
    """
    user_id = update.effective_user.id if update.effective_user else 0
    
    if not es_usuario_autorizado(user_id):
        update.message.reply_text(
            "❌ **Acceso denegado.**\n\n"
            "No tienes permisos para usar este bot.",
            parse_mode='Markdown'
        )
        return
    
    try:
        if not context.args or len(context.args) != 1:
            update.message.reply_text(
                "❌ **Formato incorrecto.**\n\n"
                "**Uso:** `/remover <user_id>`\n"
                "**Ejemplo:** `/remover 123456789`",
                parse_mode='Markdown'
            )
            return
        
        target_user_id = int(context.args[0])
        
        if target_user_id == user_id:
            update.message.reply_text(
                "❌ **No puedes removerte a ti mismo.**",
                parse_mode='Markdown'
            )
            return
        
        if target_user_id not in usuarios_autorizados:
            update.message.reply_text(
                f"⚠️ **Usuario {target_user_id} no está autorizado.**",
                parse_mode='Markdown'
            )
            return
        
        usuarios_autorizados.remove(target_user_id)
        
        # Guardar en JSON
        actualizar_usuario_autorizado_json(target_user_id, 'remover')
        registrar_accion_json(user_id, 'usuario_desautorizado', {
            'target_user_id': target_user_id,
            'accion': 'remover'
        })
        
        update.message.reply_text(
            f"✅ **Usuario {target_user_id} desautorizado exitosamente.**\n\n"
            f"Ya no puede usar los comandos del bot.",
            parse_mode='Markdown'
        )
        
        logger.info(f"Usuario {user_id} desautorizó a usuario {target_user_id}")
        
    except ValueError:
        update.message.reply_text(
            "❌ **ID de usuario inválido.**\n\n"
            "El ID debe ser un número.",
            parse_mode='Markdown'
        )
    except Exception as e:
        update.message.reply_text(f"❌ **Error:** {str(e)}")
        logger.error(f"Error en comando remover: {e}")

def programar_fecha(update: Update, context: CallbackContext):
    """
    Comando /programar_fecha - Programa un mensaje para fecha y hora específicas
    Formato: /programar_fecha "mensaje" DD/MM/YYYY HH:MM
    """
    user_id = update.effective_user.id if update.effective_user else 0
    
    if not es_usuario_autorizado(user_id):
        update.message.reply_text(
            "❌ **Acceso denegado.**\n\n"
            "No tienes permisos para usar este bot.",
            parse_mode='Markdown'
        )
        return
    
    try:
        if not context.args or len(context.args) < 3:
            update.message.reply_text(
                "❌ **Formato incorrecto.**\n\n"
                "**Uso:** `/programar_fecha \"mensaje\" DD/MM/YYYY HH:MM`\n"
                "**Ejemplo:** `/programar_fecha \"Feliz Año Nuevo\" 01/01/2025 00:00`",
                parse_mode='Markdown'
            )
            return

        mensaje = context.args[0].strip('"\'')
        fecha = context.args[1]
        hora = context.args[2]
        
        if not validar_formato_fecha(fecha):
            update.message.reply_text(
                "❌ **Formato de fecha incorrecto.**\n\n"
                "**Formato válido:** DD/MM/YYYY (ejemplo: 25/12/2024)",
                parse_mode='Markdown'
            )
            return
            
        if not validar_formato_hora(hora):
            update.message.reply_text(
                "❌ **Formato de hora incorrecto.**\n\n"
                "**Formato válido:** HH:MM (ejemplo: 14:30)",
                parse_mode='Markdown'
            )
            return

        # Parsear fecha y hora con timezone
        objetivo = parsear_fecha_hora(fecha, hora)
        if objetivo is None:
            update.message.reply_text("❌ Error procesando la fecha y hora proporcionadas.")
            return

        # Verificar que no sea en el pasado
        ahora = datetime.datetime.now(TIMEZONE)
        if objetivo <= ahora:
            update.message.reply_text(
                "❌ **Fecha y hora en el pasado.**\n\n"
                "La fecha y hora programada debe ser futura.",
                parse_mode='Markdown'
            )
            return

        # Calcular delay en segundos
        delay = (objetivo - ahora).total_seconds()
        
        # Crear ID único para el mensaje
        mensaje_id = len(mensajes_programados) + 1
        
        # Crear y iniciar timer
        timer = threading.Timer(
            delay, 
            enviar_mensaje_programado, 
            args=(update.message.chat_id, mensaje, mensaje_id, user_id)
        )
        timer.start()

        # Guardar información del mensaje programado
        username = "Usuario"
        if update.effective_user:
            username = update.effective_user.username or update.effective_user.first_name or "Usuario"
            
        mensaje_programado = {
            'id': mensaje_id,
            'mensaje': mensaje,
            'fecha': fecha,
            'hora': hora,
            'chat_id': update.message.chat_id,
            'timer': timer,
            'fecha_objetivo': objetivo,
            'usuario': username,
            'tipo': 'fecha_especifica'
        }
        
        mensajes_programados.append(mensaje_programado)
        
        # Actualizar estadísticas
        estadisticas['mensajes_programados_total'] += 1
        estadisticas['usuarios_activos'].add(user_id)
        registrar_estadistica(user_id, 'mensaje_programado_fecha', {
            'mensaje': mensaje,
            'fecha': fecha,
            'hora': hora,
            'fecha_objetivo': objetivo.isoformat()
        })
        
        update.message.reply_text(
            f"✅ **Mensaje programado para fecha específica**\n\n"
            f"📝 **Mensaje:** {mensaje}\n"
            f"📅 **Fecha:** {fecha}\n"
            f"⏰ **Hora:** {hora}\n"
            f"🔢 **ID:** #{mensaje_id}",
            parse_mode='Markdown'
        )
        
        logger.info(f"Mensaje programado por usuario {user_id} para {objetivo}")
        
    except Exception as e:
        update.message.reply_text(f"❌ **Error:** {str(e)}")
        logger.error(f"Error en comando programar_fecha: {e}")

def estadisticas_bot(update: Update, context: CallbackContext):
    """
    Comando /estadisticas - Muestra estadísticas del bot
    """
    user_id = update.effective_user.id if update.effective_user else 0
    
    if not es_usuario_autorizado(user_id):
        update.message.reply_text(
            "❌ **Acceso denegado.**\n\n"
            "No tienes permisos para usar este bot.",
            parse_mode='Markdown'
        )
        return
    
    try:
        # Obtener estadísticas de la base de datos
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cur = conn.cursor()
        
        # Mensajes enviados
        cur.execute("SELECT COUNT(*) FROM estadisticas WHERE accion = 'mensaje_enviado'")
        result = cur.fetchone()
        mensajes_enviados_db = result[0] if result else 0
        
        # Mensajes programados
        cur.execute("SELECT COUNT(*) FROM estadisticas WHERE accion IN ('mensaje_programado', 'mensaje_programado_fecha')")
        result = cur.fetchone()
        mensajes_programados_db = result[0] if result else 0
        
        # Usuarios únicos
        cur.execute("SELECT COUNT(DISTINCT user_id) FROM estadisticas")
        result = cur.fetchone()
        usuarios_unicos = result[0] if result else 0
        
        # Usuarios autorizados
        cur.execute("SELECT COUNT(*) FROM usuarios_autorizados")
        result = cur.fetchone()
        usuarios_autorizados_total = result[0] if result else 0
        
        cur.close()
        conn.close()
        
        # Mensajes activos actuales
        mensajes_activos = len([msg for msg in mensajes_programados if msg.get('timer', {}).is_alive()])
        repetitivos_activos = len([msg for msg in mensajes_repetitivos if msg.get('activo', False)])
        
        # Tiempo de actividad
        tiempo_actividad = "No disponible"
        if estadisticas.get('inicio_bot'):
            delta = datetime.datetime.now(TIMEZONE) - estadisticas['inicio_bot']
            dias = delta.days
            horas = delta.seconds // 3600
            tiempo_actividad = f"{dias} días, {horas} horas"
        
        texto_estadisticas = (
            f"📊 **Estadísticas del Bot**\n\n"
            f"📨 **Mensajes enviados:** {mensajes_enviados_db}\n"
            f"📅 **Mensajes programados (total):** {mensajes_programados_db}\n"
            f"📋 **Mensajes pendientes:** {mensajes_activos}\n"
            f"🔄 **Mensajes repetitivos activos:** {repetitivos_activos}\n\n"
            f"👥 **Usuarios únicos que han usado el bot:** {usuarios_unicos}\n"
            f"🔐 **Usuarios autorizados:** {usuarios_autorizados_total}\n\n"
            f"⏱️ **Tiempo de actividad:** {tiempo_actividad}\n"
            f"🌍 **Zona horaria:** {TIMEZONE}"
        )
        
        update.message.reply_text(texto_estadisticas, parse_mode='Markdown')
        logger.info(f"Usuario {user_id} consultó estadísticas")
        
    except Exception as e:
        update.message.reply_text(f"❌ **Error obteniendo estadísticas:** {str(e)}")
        logger.error(f"Error en comando estadisticas: {e}")

def chat_info(update: Update, context: CallbackContext):
    """
    Comando /chat_info - Obtiene información del chat actual
    """
    user_id = update.effective_user.id if update.effective_user else 0
    
    if not es_usuario_autorizado(user_id):
        update.message.reply_text(
            "❌ Acceso denegado.\n\n"
            "No tienes permisos para usar este bot."
        )
        return
    
    try:
        chat = update.effective_chat
        chat_id = chat.id
        chat_type = chat.type
        chat_title = getattr(chat, 'title', 'Sin título')
        
        if chat_type == 'private':
            info_text = (
                f"💬 Información del Chat\n\n"
                f"📋 ID del chat: {chat_id}\n"
                f"🔒 Tipo: Chat privado\n"
                f"👤 Usuario: {update.effective_user.first_name or 'Usuario'}\n\n"
                f"Para enviar mensajes a este chat usa:\n"
                f"/programar \"mensaje\" HH:MM {chat_id}"
            )
        else:
            info_text = (
                f"💬 Información del Chat\n\n"
                f"📋 ID del chat: {chat_id}\n"
                f"🔒 Tipo: {chat_type}\n"
                f"📝 Título: {chat_title}\n\n"
                f"Para enviar mensajes a este chat usa:\n"
                f"/programar \"mensaje\" HH:MM {chat_id}"
            )
        
        update.message.reply_text(info_text)
        logger.info(f"Usuario {user_id} consultó información del chat {chat_id}")
        
    except Exception as e:
        update.message.reply_text(f"❌ Error obteniendo información del chat: {str(e)}")
        logger.error(f"Error en comando chat_info: {e}")

def ayuda(update: Update, context: CallbackContext):
    """
    Comando /ayuda - Información detallada sobre limitaciones y uso
    """
    user_id = update.effective_user.id if update.effective_user else 0
    
    if not es_usuario_autorizado(user_id):
        update.message.reply_text(
            "❌ **Acceso denegado.**\n\n"
            "No tienes permisos para usar este bot.",
            parse_mode='Markdown'
        )
        return
    
    # Enviar información en múltiples mensajes para evitar límites de Telegram
    mensaje1 = (
        "🆘 **Guía de Uso del Bot**\n\n"
        "📋 **COMANDOS DISPONIBLES:**\n\n"
        "🔹 **MENSAJERÍA:**\n"
        "• /enviar \"mensaje\" - Envía mensaje inmediato\n"
        "• /programar \"mensaje\" HH:MM - Programa mensaje\n"
        "• /repetir \"mensaje\" HH:MM intervalo - Mensaje repetitivo\n\n"
        "🔹 **EMAIL:**\n"
        "• /email \"asunto\" \"mensaje\" email@dominio.com - Email inmediato\n"
        "• /programar_email \"asunto\" \"mensaje\" HH:MM email@dominio.com - Email programado"
    )
    
    mensaje2 = (
        "🔹 **CLIMA:**\n"
        "• /clima ciudad - Consulta clima actual\n"
        "• /clima_email ciudad email@dominio.com - Reporte del clima por email\n\n"
        "🔹 **ADMINISTRACIÓN:**\n"
        "• /agregar user_id - Autorizar usuario\n"
        "• /remover user_id - Desautorizar usuario\n"
        "• /listar - Ver mensajes programados\n"
        "• /cancelar ID - Cancelar mensaje programado\n"
        "• /estadisticas - Ver uso del bot\n"
        "• /backup - Exportar configuración\n\n"
        "🔹 **INFORMACIÓN:**\n"
        "• /chat_info - Ver ID del chat\n"
        "• /ayuda - Esta guía"
    )
    
    mensaje3 = (
        "⚠️ **LIMITACIONES IMPORTANTES DE TELEGRAM:**\n\n"
        "🚫 **NO PUEDO ENVIAR A:**\n"
        "• Números de teléfono directamente (+58412...)\n"
        "• Usuarios que nunca escribieron /start al bot\n"
        "• Usernames que no me han contactado primero\n\n"
        "✅ **SÍ PUEDO ENVIAR A:**\n"
        "• El chat actual (donde escribes el comando)\n"
        "• Usuarios que escribieron /start al bot (usa su chat ID)\n"
        "• Grupos donde el bot está agregado"
    )
    
    mensaje4 = (
        "📋 **CÓMO OBTENER CHAT IDs:**\n"
        "1. Pide a la persona escribir /start al bot\n"
        "2. En ese chat, usa /chat_info\n"
        "3. Copia el Chat ID mostrado\n"
        "4. Úsalo en tus comandos: /programar \"mensaje\" 14:30 123456789\n\n"
        "🕐 **FORMATOS DE HORA:**\n"
        "• 24 horas: 14:30, 08:15, 23:45\n"
        "• 12 horas: 2:30pm, 8:15am"
    )
    
    mensaje5 = (
        "📅 **INTERVALOS VÁLIDOS:**\n"
        "• diario - cada 24 horas\n"
        "• semanal - cada 7 días\n"
        "• mensual - cada 30 días\n\n"
        "💡 **EJEMPLOS PRÁCTICOS:**\n"
        "- /programar \"Reunión a las 3\" 15:00\n"
        "- /repetir \"Buenos días\" 8:30am diario\n"
        "- /enviar \"Mensaje inmediato\"\n"
        "- /chat_info (para ver el chat ID)\n\n"
        "❓ **¿Por qué no llega mi mensaje?**\n"
        "- La persona no escribió /start al bot\n"
        "- El username no existe o cambió\n"
        "- El bot no está en ese grupo\n"
        "- Usaste número de teléfono (no funciona)"
    )
    
    # Enviar los mensajes por separado
    try:
        update.message.reply_text(mensaje1, parse_mode='Markdown')
        time.sleep(1)
        update.message.reply_text(mensaje2, parse_mode='Markdown')
        time.sleep(1)
        update.message.reply_text(mensaje3, parse_mode='Markdown')
        time.sleep(1)
        update.message.reply_text(mensaje4, parse_mode='Markdown')
        time.sleep(1)
        update.message.reply_text(mensaje5, parse_mode='Markdown')
    except Exception as e:
        # Si hay problemas con Markdown, enviar sin formato
        update.message.reply_text(mensaje1.replace('**', '').replace('*', ''))
        time.sleep(1)
        update.message.reply_text(mensaje2.replace('**', '').replace('*', ''))
        time.sleep(1)
        update.message.reply_text(mensaje3.replace('**', '').replace('*', ''))
        time.sleep(1)
        update.message.reply_text(mensaje4.replace('**', '').replace('*', ''))
        time.sleep(1)
        update.message.reply_text(mensaje5.replace('**', '').replace('*', ''))
    
    registrar_estadistica(user_id, 'comando_ayuda')
    logger.info(f"Usuario {user_id} consultó ayuda")

def email_comando(update: Update, context: CallbackContext):
    """
    Comando /email - Envía un email inmediatamente
    Formato: /email "asunto" "mensaje" destinatario@email.com
    """
    user_id = update.effective_user.id if update.effective_user else 0
    
    if not es_usuario_autorizado(user_id):
        update.message.reply_text(
            "❌ **Acceso denegado.**\n\n"
            "No tienes permisos para usar este bot.",
            parse_mode='Markdown'
        )
        return
    
    try:
        # Verificar argumentos
        if len(context.args) < 3:
            update.message.reply_text(
                "❌ **Uso correcto:**\n\n"
                "/email \"asunto\" \"mensaje\" destinatario@email.com\n\n"
                "**Ejemplo:**\n"
                "/email \"Recordatorio\" \"No olvides la reunión\" persona@gmail.com",
                parse_mode='Markdown'
            )
            return
        
        # Extraer argumentos usando regex para manejar comillas
        texto_completo = ' '.join(context.args)
        
        # Buscar las dos cadenas entre comillas y el email
        patron = r'"([^"]*?)"\s+"([^"]*?)"\s+(\S+@\S+\.\S+)'
        match = re.search(patron, texto_completo)
        
        if not match:
            update.message.reply_text(
                "❌ **Formato incorrecto.**\n\n"
                "Usa comillas para el asunto y mensaje:\n"
                "/email \"asunto\" \"mensaje\" email@dominio.com",
                parse_mode='Markdown'
            )
            return
        
        asunto = match.group(1).strip()
        mensaje = match.group(2).strip()
        destinatario = match.group(3).strip()
        
        # Validar email
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', destinatario):
            update.message.reply_text(
                "❌ **Email inválido.**\n\n"
                "Verifica que el formato sea correcto:\n"
                "ejemplo@dominio.com"
            )
            return
        
        # Verificar credenciales
        if not GMAIL_EMAIL or not GMAIL_APP_PASSWORD:
            update.message.reply_text(
                "❌ **Credenciales de Gmail no configuradas.**\n\n"
                "Contacta al administrador del bot."
            )
            return
        
        # Enviar email
        exito, resultado = enviar_email(destinatario, asunto, mensaje)
        
        if exito:
            update.message.reply_text(
                f"✅ **Email enviado exitosamente**\n\n"
                f"📧 **Para:** {destinatario}\n"
                f"📝 **Asunto:** {asunto}\n"
                f"📄 **Mensaje:** {mensaje[:100]}{'...' if len(mensaje) > 100 else ''}",
                parse_mode='Markdown'
            )
            registrar_estadistica(user_id, 'email_enviado', {
                'destinatario': destinatario,
                'asunto': asunto
            })
            logger.info(f"Usuario {user_id} envió email a {destinatario}")
        else:
            update.message.reply_text(
                f"❌ **Error enviando email:**\n\n{resultado}",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        update.message.reply_text(f"❌ **Error:** {str(e)}")
        logger.error(f"Error en comando email: {e}")

def programar_email_comando(update: Update, context: CallbackContext):
    """
    Comando /programar_email - Programa un email para ser enviado automáticamente
    Formato: /programar_email "asunto" "mensaje" HH:MM destinatario@email.com
    """
    user_id = update.effective_user.id if update.effective_user else 0
    
    if not es_usuario_autorizado(user_id):
        update.message.reply_text(
            "❌ **Acceso denegado.**\n\n"
            "No tienes permisos para usar este bot.",
            parse_mode='Markdown'
        )
        return
    
    try:
        # Verificar argumentos
        if len(context.args) < 4:
            update.message.reply_text(
                "❌ **Uso correcto:**\n\n"
                "/programar_email \"asunto\" \"mensaje\" HH:MM email@dominio.com\n\n"
                "**Ejemplo:**\n"
                "/programar_email \"Reunión\" \"Recordatorio de reunión\" 14:30 persona@gmail.com",
                parse_mode='Markdown'
            )
            return
        
        # Extraer argumentos del comando completo
        texto_completo = update.message.text
        
        # Buscar asunto, mensaje, hora y email después del comando
        patron = r'/programar_email\s+"([^"]*?)"\s+"([^"]*?)"\s+(\d{1,2}:\d{2}(?:am|pm)?)\s+(\S+@\S+\.\S+)'
        match = re.search(patron, texto_completo, re.IGNORECASE)
        
        if not match:
            update.message.reply_text(
                "❌ **Formato incorrecto.**\n\n"
                "Usa comillas para asunto y mensaje:\n"
                "/programar_email \"asunto\" \"mensaje\" 14:30 email@dominio.com",
                parse_mode='Markdown'
            )
            return
        
        asunto = match.group(1).strip()
        mensaje = match.group(2).strip()
        hora_str = match.group(3).strip()
        destinatario = match.group(4).strip()
        
        # Validar email
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', destinatario):
            update.message.reply_text("❌ **Email inválido.**")
            return
        
        # Validar formato de hora
        if not validar_formato_hora(hora_str):
            update.message.reply_text(
                "❌ **Formato de hora inválido.**\n\n"
                "Formatos válidos:\n"
                "• 24h: 14:30, 08:15\n"
                "• 12h: 2:30pm, 8:15am"
            )
            return
        
        # Verificar credenciales
        if not GMAIL_EMAIL or not GMAIL_APP_PASSWORD:
            update.message.reply_text(
                "❌ **Credenciales de Gmail no configuradas.**\n\n"
                "Contacta al administrador del bot."
            )
            return
        
        # Calcular tiempo objetivo
        tiempo_objetivo = calcular_tiempo_objetivo(hora_str)
        
        if tiempo_objetivo <= datetime.datetime.now(TIMEZONE):
            update.message.reply_text("❌ **La hora especificada ya pasó.**")
            return
        
        # Crear ID único para el mensaje
        mensaje_id = f"email_{int(time.time())}_{user_id}"
        
        # Función para enviar el email programado
        def enviar_email_programado():
            try:
                exito, resultado = enviar_email(destinatario, asunto, mensaje)
                if exito:
                    logger.info(f"Email programado enviado exitosamente a {destinatario}")
                    registrar_estadistica(user_id, 'email_programado_enviado', {
                        'destinatario': destinatario,
                        'asunto': asunto
                    })
                else:
                    logger.error(f"Error enviando email programado: {resultado}")
            except Exception as e:
                logger.error(f"Error en email programado: {e}")
        
        # Calcular segundos hasta el envío
        segundos_hasta_envio = (tiempo_objetivo - datetime.datetime.now(TIMEZONE)).total_seconds()
        
        # Crear timer
        timer = threading.Timer(segundos_hasta_envio, enviar_email_programado)
        timer.start()
        
        # Guardar en lista de mensajes programados
        mensaje_data = {
            'id': mensaje_id,
            'tipo': 'email',
            'asunto': asunto,
            'mensaje': mensaje,
            'destinatario': destinatario,
            'hora': hora_str,
            'timer': timer,
            'fecha_objetivo': tiempo_objetivo,
            'user_id': user_id
        }
        
        mensajes_programados.append(mensaje_data)
        
        # Respuesta de confirmación
        update.message.reply_text(
            f"📧 Email programado exitosamente\n\n"
            f"📝 Asunto: {asunto}\n"
            f"📄 Mensaje: {mensaje[:100]}{'...' if len(mensaje) > 100 else ''}\n"
            f"📧 Destinatario: {destinatario}\n"
            f"⏰ Hora: {tiempo_objetivo.strftime('%d/%m/%Y %H:%M')} ({TIMEZONE})\n"
            f"🆔 ID: {mensaje_id}"
        )
        
        registrar_estadistica(user_id, 'email_programado', {
            'destinatario': destinatario,
            'asunto': asunto,
            'hora': hora_str
        })
        logger.info(f"Usuario {user_id} programó email para {destinatario} a las {hora_str}")
        
    except Exception as e:
        update.message.reply_text(f"❌ **Error:** {str(e)}")
        logger.error(f"Error en comando programar_email: {e}")

def clima_comando(update: Update, context: CallbackContext):
    """
    Comando /clima - Consulta el clima actual de una ciudad
    Formato: /clima ciudad
    """
    user_id = update.effective_user.id if update.effective_user else 0
    
    if not es_usuario_autorizado(user_id):
        update.message.reply_text(
            "❌ Acceso denegado.\n\n"
            "No tienes permisos para usar este bot."
        )
        return
    
    try:
        if len(context.args) < 1:
            update.message.reply_text(
                "❌ Uso correcto:\n\n"
                "/clima ciudad\n\n"
                "Ejemplo:\n"
                "/clima caracas\n"
                "/clima bogota"
            )
            return
        
        ciudad = ' '.join(context.args)
        clima_info, error = obtener_clima(ciudad)
        
        if error:
            update.message.reply_text(f"❌ {error}")
            return
        
        if clima_info:
            mensaje_clima = (
                f"🌤️ Clima en {clima_info['ciudad']}, {clima_info['pais']}\n\n"
                f"🌡️ Temperatura: {clima_info['temperatura']:.1f}°C\n"
                f"🤔 Sensación térmica: {clima_info['sensacion']:.1f}°C\n"
                f"☁️ Condición: {clima_info['descripcion'].title()}\n"
                f"💧 Humedad: {clima_info['humedad']}%\n"
                f"💨 Viento: {clima_info['viento']} m/s"
            )
            
            update.message.reply_text(mensaje_clima)
            registrar_estadistica(user_id, 'consulta_clima', {'ciudad': ciudad})
            logger.info(f"Usuario {user_id} consultó clima de {ciudad}")
        else:
            update.message.reply_text("❌ No se pudo obtener información del clima")
            
    except Exception as e:
        update.message.reply_text(f"❌ Error: {str(e)}")
        logger.error(f"Error en comando clima: {e}")

def clima_email_comando(update: Update, context: CallbackContext):
    """
    Comando /clima_email - Envía el clima por email
    Formato: /clima_email ciudad destinatario@email.com
    """
    user_id = update.effective_user.id if update.effective_user else 0
    
    if not es_usuario_autorizado(user_id):
        update.message.reply_text(
            "❌ Acceso denegado.\n\n"
            "No tienes permisos para usar este bot."
        )
        return
    
    try:
        if len(context.args) < 2:
            update.message.reply_text(
                "❌ Uso correcto:\n\n"
                "/clima_email ciudad email@dominio.com\n\n"
                "Ejemplo:\n"
                "/clima_email caracas persona@gmail.com"
            )
            return
        
        # El último argumento es el email, el resto es la ciudad
        destinatario = context.args[-1]
        ciudad = ' '.join(context.args[:-1])
        
        # Validar email
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', destinatario):
            update.message.reply_text("❌ Email inválido.")
            return
        
        # Verificar credenciales de email
        if not GMAIL_EMAIL or not GMAIL_APP_PASSWORD:
            update.message.reply_text(
                "❌ Credenciales de Gmail no configuradas.\n\n"
                "Contacta al administrador del bot."
            )
            return
        
        # Obtener información del clima
        clima_info, error = obtener_clima(ciudad)
        
        if error:
            update.message.reply_text(f"❌ {error}")
            return
        
        if clima_info:
            # Crear contenido del email
            asunto = f"Reporte del Clima - {clima_info['ciudad']}"
            mensaje_email = (
                f"Reporte del Clima\n\n"
                f"Ciudad: {clima_info['ciudad']}, {clima_info['pais']}\n"
                f"Temperatura: {clima_info['temperatura']:.1f}°C\n"
                f"Sensación térmica: {clima_info['sensacion']:.1f}°C\n"
                f"Condición: {clima_info['descripcion'].title()}\n"
                f"Humedad: {clima_info['humedad']}%\n"
                f"Viento: {clima_info['viento']} m/s\n\n"
                f"Enviado desde tu Bot de Telegram"
            )
            
            # Enviar email
            exito, resultado = enviar_email(destinatario, asunto, mensaje_email)
            
            if exito:
                update.message.reply_text(
                    f"✅ Reporte del clima enviado exitosamente\n\n"
                    f"🌤️ Ciudad: {clima_info['ciudad']}\n"
                    f"📧 Destinatario: {destinatario}\n"
                    f"🌡️ Temperatura: {clima_info['temperatura']:.1f}°C"
                )
                registrar_estadistica(user_id, 'clima_email_enviado', {
                    'ciudad': ciudad,
                    'destinatario': destinatario
                })
                logger.info(f"Usuario {user_id} envió clima de {ciudad} por email a {destinatario}")
            else:
                update.message.reply_text(f"❌ Error enviando email: {resultado}")
        else:
            update.message.reply_text("❌ No se pudo obtener información del clima")
            
    except Exception as e:
        update.message.reply_text(f"❌ Error: {str(e)}")
        logger.error(f"Error en comando clima_email: {e}")

def backup(update: Update, context: CallbackContext):
    """
    Comando /backup - Exporta backup de configuración
    """
    user_id = update.effective_user.id if update.effective_user else 0
    
    if not es_usuario_autorizado(user_id):
        update.message.reply_text(
            "❌ **Acceso denegado.**\n\n"
            "No tienes permisos para usar este bot.",
            parse_mode='Markdown'
        )
        return
    
    try:
        backup_data = exportar_backup()
        
        if backup_data:
            # Crear archivo temporal
            filename = f"backup_bot_{datetime.datetime.now(TIMEZONE).strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(backup_data)
            
            # Enviar archivo
            with open(filename, 'rb') as f:
                update.message.reply_document(
                    document=f,
                    filename=filename,
                    caption="📦 **Backup del bot generado exitosamente**\n\n"
                           "Este archivo contiene la configuración completa del bot.",
                    parse_mode='Markdown'
                )
            
            # Eliminar archivo temporal
            os.remove(filename)
            
            registrar_estadistica(user_id, 'backup_exportado', {'filename': filename})
            logger.info(f"Usuario {user_id} exportó backup")
            
        else:
            update.message.reply_text("❌ **Error generando backup.**")
            
    except Exception as e:
        update.message.reply_text(f"❌ **Error:** {str(e)}")
        logger.error(f"Error en comando backup: {e}")

def error_handler(update: Update, context: CallbackContext):
    """
    Maneja errores globales del bot con reconexión automática
    """
    error = context.error
    
    # Errores de conexión que requieren reconexión
    connection_errors = [
        'Connection aborted',
        'RemoteDisconnected',
        'urllib3 HTTPError',
        'Network is unreachable',
        'Timeout',
        'Connection reset'
    ]
    
    error_str = str(error)
    
    # Si es un error de conexión, intentar reconectar
    if any(conn_error in error_str for conn_error in connection_errors):
        logger.warning(f'Error de conexión detectado: {error_str}')
        logger.info('Intentando reconexión automática en 5 segundos...')
        
        # Esperar antes de reconectar
        time.sleep(5)
        
        try:
            # Reiniciar el updater
            global updater
            if updater and updater.running:
                logger.info('Reiniciando conexión del bot...')
                updater.stop()
                time.sleep(2)
                updater.start_polling()
                logger.info('Bot reconectado exitosamente')
        except Exception as e:
            logger.error(f'Error durante reconexión: {e}')
    else:
        logger.warning(f'Update {update} causó error {error_str}')

def main():
    """
    Función principal que configura e inicia el bot
    """
    global updater
    
    try:
        # Crear updater y dispatcher con configuraciones de estabilidad optimizada
        updater = Updater(
            TOKEN, 
            use_context=True,
            request_kwargs={
                'read_timeout': 10,
                'connect_timeout': 8
            }
        )
        dispatcher = updater.dispatcher

        # Registrar comandos
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("enviar", enviar))
        dispatcher.add_handler(CommandHandler("programar", programar))
        dispatcher.add_handler(CommandHandler("programar_fecha", programar_fecha))
        dispatcher.add_handler(CommandHandler("repetir", repetir))
        dispatcher.add_handler(CommandHandler("listar", listar))
        dispatcher.add_handler(CommandHandler("cancelar", cancelar))
        dispatcher.add_handler(CommandHandler("agregar", agregar))
        dispatcher.add_handler(CommandHandler("remover", remover))
        dispatcher.add_handler(CommandHandler("estadisticas", estadisticas_bot))
        dispatcher.add_handler(CommandHandler("backup", backup))
        dispatcher.add_handler(CommandHandler("chat_info", chat_info))
        dispatcher.add_handler(CommandHandler("ayuda", ayuda))
        dispatcher.add_handler(CommandHandler("email", email_comando))
        dispatcher.add_handler(CommandHandler("programar_email", programar_email_comando))
        dispatcher.add_handler(CommandHandler("clima", clima_comando))
        dispatcher.add_handler(CommandHandler("clima_email", clima_email_comando))
        
        # Registrar manejador de callbacks para botones interactivos
        dispatcher.add_handler(CallbackQueryHandler(callback_handler_mensajeria))
        
        # Registrar manejador de errores
        dispatcher.add_error_handler(error_handler)

        # Inicializar sistemas de persistencia
        init_database()
        
        # Cargar datos desde JSON
        global usuarios_autorizados
        data_json = cargar_mensajes_json()
        usuarios_autorizados = set(data_json.get('autorizados', []))
        
        # Cargar estadísticas desde JSON
        stats_json = cargar_estadisticas_json()
        if stats_json.get('inicio_bot'):
            estadisticas['inicio_bot'] = datetime.datetime.fromisoformat(stats_json['inicio_bot'])
        else:
            estadisticas['inicio_bot'] = datetime.datetime.now(TIMEZONE)
            stats_json['inicio_bot'] = estadisticas['inicio_bot'].isoformat()
            guardar_estadisticas_json(stats_json)
        
        logger.info(f"✅ Datos cargados desde JSON - {len(usuarios_autorizados)} usuarios autorizados")
        
        # Iniciar keep-alive para mantener el bot activo 24/7
        keep_alive()
        logger.info("🌐 Keep-alive iniciado - Bot disponible 24/7")
        
        # Iniciar el bot con reintentos automáticos
        logger.info("🚀 Iniciando bot de mensajes programados...")
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                logger.info("✅ Bot iniciado exitosamente. Presiona Ctrl+C para detener.")
                updater.start_polling(
                    poll_interval=0.5,
                    timeout=10,
                    drop_pending_updates=True,
                    bootstrap_retries=5,
                    read_latency=1.0
                )
                updater.idle()
                break
            except Exception as polling_error:
                retry_count += 1
                logger.error(f"Error en polling (intento {retry_count}/{max_retries}): {polling_error}")
                
                if retry_count < max_retries:
                    logger.info(f"Reintentando en 3 segundos...")
                    time.sleep(3)
                else:
                    logger.error("Máximo de reintentos alcanzado")
                    raise polling_error
        
    except Exception as e:
        logger.error(f"❌ Error crítico iniciando el bot: {e}")
        exit(1)

if __name__ == '__main__':
    from keep_alive import keep_alive
    keep_alive()  # Esto debe estar antes de application.run_polling()
    main()
