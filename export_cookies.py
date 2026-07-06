"""
Script para exportar cookies de TikTok desde Chrome
Ejecuta este script si tienes problemas descargando de TikTok
"""

import os
import sys
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import json

# Intenta importar la librería de desencriptación de Windows
try:
    import win32crypt
    from Crypto.Cipher import AES
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    print("NOTA: Para mejor compatibilidad, instala: pip install pycryptodome pywin32")


def get_chrome_cookies_path():
    """Obtiene la ruta de las cookies de Chrome"""
    if sys.platform == 'win32':
        local_app_data = os.environ.get('LOCALAPPDATA', '')
        return Path(local_app_data) / 'Google' / 'Chrome' / 'User Data' / 'Default' / 'Cookies'
    elif sys.platform == 'darwin':  # macOS
        return Path.home() / 'Library' / 'Application Support' / 'Google' / 'Chrome' / 'Default' / 'Cookies'
    else:  # Linux
        return Path.home() / '.config' / 'google-chrome' / 'Default' / 'Cookies'


def export_tiktok_cookies_simple():
    """
    Método simple: usa yt-dlp para extraer cookies
    """
    print("\n=== Método 1: Usando yt-dlp ===")
    print("Este método extrae las cookies directamente de Chrome...\n")

    import subprocess

    cookies_dir = Path("cookies")
    cookies_dir.mkdir(exist_ok=True)
    output_file = cookies_dir / "tiktok_cookies.txt"

    try:
        # Usar yt-dlp para exportar cookies
        cmd = [
            sys.executable, '-m', 'yt_dlp',
            '--cookies-from-browser', 'chrome',
            '--cookies', str(output_file),
            '--skip-download',
            'https://www.tiktok.com'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if output_file.exists() and output_file.stat().st_size > 0:
            print(f"✓ Cookies exportadas a: {output_file}")
            print(f"  Tamaño: {output_file.stat().st_size} bytes")
            return True
        else:
            print("✗ No se pudieron exportar las cookies")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_tiktok_download():
    """
    Prueba si la descarga de TikTok funciona
    """
    print("\n=== Probando Descarga de TikTok ===")

    test_url = "https://www.tiktok.com/@tiktok/video/7000000000000000000"  # URL de prueba

    import subprocess

    cmd = [
        sys.executable, '-m', 'yt_dlp',
        '--cookies-from-browser', 'chrome',
        '--skip-download',
        '--print', 'title',
        test_url
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print("✓ La conexión a TikTok funciona correctamente")
            return True
        else:
            print("✗ Hay problemas con la conexión a TikTok")
            print(f"  Error: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"✗ Error de prueba: {e}")
        return False


def check_chrome_running():
    """Verifica si Chrome está corriendo"""
    import subprocess

    if sys.platform == 'win32':
        result = subprocess.run(['tasklist'], capture_output=True, text=True)
        return 'chrome.exe' in result.stdout.lower()
    else:
        result = subprocess.run(['pgrep', '-x', 'chrome'], capture_output=True)
        return result.returncode == 0


def main():
    print("=" * 50)
    print("  Exportador de Cookies de TikTok para Chrome")
    print("=" * 50)

    # Verificar si Chrome está corriendo
    if check_chrome_running():
        print("\n⚠️  ADVERTENCIA: Chrome está abierto!")
        print("   Para mejores resultados, cierra Chrome primero.")
        input("\n   Presiona Enter para continuar de todos modos...")

    # Verificar que Chrome existe
    cookies_path = get_chrome_cookies_path()
    if not cookies_path.exists():
        print(f"\n✗ No se encontró Chrome en: {cookies_path}")
        print("  Asegúrate de tener Chrome instalado.")
        return

    print(f"\n✓ Chrome encontrado: {cookies_path.parent}")

    # Método 1: Exportar cookies
    success = export_tiktok_cookies_simple()

    if success:
        print("\n" + "=" * 50)
        print("  ¡Cookies exportadas exitosamente!")
        print("=" * 50)
        print("\nAhora puedes:")
        print("1. Reiniciar la aplicación (python app.py)")
        print("2. Intentar descargar el video de TikTok nuevamente")
    else:
        print("\n" + "=" * 50)
        print("  Instrucciones Manuales")
        print("=" * 50)
        print("""
Para exportar cookies manualmente:

1. Abre Chrome y ve a: https://www.tiktok.com
2. Inicia sesión en tu cuenta de TikTok
3. Instala la extensión "Get cookies.txt LOCALLY":
   https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc
4. Haz clic en el ícono de la extensión
5. Exporta las cookies y guárdalas como:
   <raiz-del-proyecto>/cookies/tiktok_cookies.txt
""")

    print("\n¿Necesitas más ayuda? Lee: SOLUCION_TIKTOK.md")


if __name__ == "__main__":
    main()
    input("\nPresiona Enter para salir...")
