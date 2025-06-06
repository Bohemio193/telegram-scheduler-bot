#!/usr/bin/env python3
"""
Script de backup para Telegram Scheduler Bot
Genera backup completo de configuración y datos
"""

import json
import os
import datetime
import shutil
import zipfile

def crear_backup():
    """Crea un backup completo del bot"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"backup_{timestamp}"
    
    # Crear directorio de backup
    os.makedirs(backup_dir, exist_ok=True)
    
    archivos_backup = [
        "mensajes.json",
        "estadisticas.json",
        ".env",
        "main.py",
        "keep_alive.py"
    ]
    
    # Copiar archivos importantes
    for archivo in archivos_backup:
        if os.path.exists(archivo):
            shutil.copy2(archivo, backup_dir)
            print(f"✅ Copiado: {archivo}")
    
    # Crear archivo ZIP
    with zipfile.ZipFile(f"{backup_dir}.zip", 'w') as zipf:
        for root, dirs, files in os.walk(backup_dir):
            for file in files:
                zipf.write(os.path.join(root, file), file)
    
    # Limpiar directorio temporal
    shutil.rmtree(backup_dir)
    
    print(f"📦 Backup creado: {backup_dir}.zip")
    return f"{backup_dir}.zip"

def restaurar_backup(archivo_zip):
    """Restaura un backup del bot"""
    if not os.path.exists(archivo_zip):
        print(f"❌ Archivo de backup no encontrado: {archivo_zip}")
        return False
    
    with zipfile.ZipFile(archivo_zip, 'r') as zipf:
        zipf.extractall(".")
    
    print(f"✅ Backup restaurado desde: {archivo_zip}")
    return True

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "restore" and len(sys.argv) > 2:
            restaurar_backup(sys.argv[2])
        else:
            print("Uso: python backup_script.py [restore archivo.zip]")
    else:
        crear_backup()