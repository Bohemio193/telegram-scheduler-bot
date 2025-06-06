from flask import Flask
from threading import Thread
import time
import requests
import os

app = Flask('')

@app.route('/')
def home():
    return "Bot de Telegram activo y funcionando 24/7", 200

@app.route('/status')
def status():
    return {
        "status": "online",
        "uptime": "24/7",
        "service": "telegram_bot"
    }, 200

def run():
    try:
        app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)
    except Exception as e:
        print(f"Error en servidor Flask: {e}")

def ping_self():
    """Hace ping al propio servidor para mantenerlo activo"""
    while True:
        try:
            time.sleep(300)  # Ping cada 5 minutos
            requests.get("http://localhost:8080/", timeout=10)
        except Exception as e:
            print(f"Error en ping: {e}")

def keep_alive():
    # Iniciar servidor Flask
    flask_thread = Thread(target=run, daemon=True)
    flask_thread.start()
    
    # Iniciar ping automático
    ping_thread = Thread(target=ping_self, daemon=True)
    ping_thread.start()
    
    print("🌐 Keep-alive mejorado iniciado - Bot disponible 24/7")