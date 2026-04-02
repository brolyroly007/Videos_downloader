"""
TikTok Uploader Module
Automatiza la subida de videos a TikTok usando Playwright
Maneja sesiones con cookies para evitar login repetido
"""

import os
import asyncio
import time
from pathlib import Path
from typing import Optional, Dict
from playwright.async_api import async_playwright, Browser, Page
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TikTokUploader:
    """Clase para automatizar la subida de videos a TikTok Web"""

    def __init__(self, cookies_path: str = "cookies"):
        self.cookies_path = Path(cookies_path)
        self.cookies_path.mkdir(parents=True, exist_ok=True)
        self.cookies_file = self.cookies_path / "tiktok_cookies.json"

        # URLs de TikTok
        self.login_url = "https://www.tiktok.com/login"
        self.upload_url = "https://www.tiktok.com/creator-center/upload"

    async def save_cookies(self, page: Page):
        """Guarda las cookies de la sesión"""
        try:
            cookies = await page.context.cookies()
            with open(self.cookies_file, 'w') as f:
                json.dump(cookies, f)
            logger.info(f"Cookies saved to {self.cookies_file}")
        except Exception as e:
            logger.error(f"Error saving cookies: {str(e)}")

    async def load_cookies(self, page: Page) -> bool:
        """Carga las cookies guardadas"""
        try:
            if not self.cookies_file.exists():
                logger.info("No cookies file found")
                return False

            with open(self.cookies_file, 'r') as f:
                cookies = json.load(f)

            await page.context.add_cookies(cookies)
            logger.info("Cookies loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Error loading cookies: {str(e)}")
            return False

    async def wait_for_manual_login(self, page: Page, timeout: int = 300000):
        """
        Espera a que el usuario haga login manualmente

        Args:
            page: Página del navegador
            timeout: Tiempo máximo de espera en milisegundos (default: 5 minutos)
        """
        try:
            logger.info("Please login manually in the browser window...")
            logger.info("Waiting for login completion (checking every 5 seconds)...")

            # Esperar hasta que detectemos que el usuario está logueado
            start_time = asyncio.get_event_loop().time()
            max_wait = timeout / 1000  # Convertir a segundos

            while True:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > max_wait:
                    logger.error("Login timeout reached")
                    return False

                # Verificar si estamos logueados
                try:
                    current_url = page.url
                    logger.info(f"Current URL: {current_url}")

                    # Si estamos en foryou, following, o profile = logueado
                    if any(x in current_url for x in ['/foryou', '/following', '/@', '/upload', '/creator']):
                        logger.info("Detected logged in state!")
                        await asyncio.sleep(2)
                        await self.save_cookies(page)
                        logger.info("Login completed successfully!")
                        return True

                    # Verificar si hay elementos de usuario logueado
                    logged_in_elements = await page.locator('[data-e2e="profile-icon"], [href*="/upload"], .avatar-wrapper').count()
                    if logged_in_elements > 0:
                        logger.info("Detected logged in elements!")
                        await asyncio.sleep(2)
                        await self.save_cookies(page)
                        logger.info("Login completed successfully!")
                        return True

                except Exception as check_err:
                    logger.warning(f"Error checking login status: {check_err}")

                # Esperar 5 segundos antes de volver a verificar
                await asyncio.sleep(5)
                logger.info(f"Still waiting for login... ({int(elapsed)}s / {int(max_wait)}s)")

        except Exception as e:
            logger.error(f"Error during manual login: {str(e)}")
            return False

    async def is_logged_in(self, page: Page) -> bool:
        """Verifica si el usuario está logueado"""
        try:
            # Navegar a la página principal
            await page.goto("https://www.tiktok.com", wait_until="networkidle")

            # Buscar elementos que indican que el usuario está logueado
            # Por ejemplo, el botón de perfil o el botón de upload
            logged_in = await page.locator('[data-e2e="profile-icon"], [href*="/upload"]').count() > 0

            return logged_in

        except Exception as e:
            logger.error(f"Error checking login status: {str(e)}")
            return False

    async def upload_video(
        self,
        video_path: str,
        description: str,
        headless: bool = False,
        auto_login: bool = True
    ) -> Dict[str, any]:
        """
        Sube un video a TikTok

        Args:
            video_path: Ruta del video a subir
            description: Descripción/caption del video
            headless: Si el navegador debe ejecutarse en modo headless
            auto_login: Si debe intentar usar cookies guardadas para login automático

        Returns:
            Dict con el resultado de la operación
        """
        async with async_playwright() as p:
            browser = None
            try:
                # Iniciar navegador
                logger.info("Starting browser...")
                browser = await p.chromium.launch(
                    headless=headless,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                    ]
                )

                # Crear contexto con user agent realista
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    locale='es-ES',
                    # Bypass some bot detection
                    java_script_enabled=True,
                    bypass_csp=True,
                )

                page = await context.new_page()

                # Intentar cargar cookies si auto_login está activado
                logged_in = False
                if auto_login:
                    cookies_loaded = await self.load_cookies(page)
                    if cookies_loaded:
                        logged_in = await self.is_logged_in(page)

                # Si no está logueado, pedir login manual
                if not logged_in:
                    logger.info("User not logged in. Opening login page...")
                    await page.goto(self.login_url)
                    login_success = await self.wait_for_manual_login(page)

                    if not login_success:
                        return {
                            'success': False,
                            'error': 'Login failed or timed out'
                        }

                # Navegar a la página de subida
                logger.info("Navigating to upload page...")
                await page.goto(self.upload_url, wait_until="networkidle")
                await asyncio.sleep(2)

                # Buscar el input de archivo
                logger.info("Looking for file input...")
                file_input = await page.wait_for_selector('input[type="file"]', timeout=10000)

                # Subir el archivo
                logger.info(f"Uploading video: {video_path}")
                await file_input.set_input_files(video_path)

                # Esperar a que el video se cargue
                logger.info("Waiting for video to upload...")
                await asyncio.sleep(5)

                # Buscar el campo de descripción y escribir
                logger.info("Adding description...")
                try:
                    # Diferentes selectores posibles para el campo de caption
                    caption_selectors = [
                        '[data-text="true"]',
                        '.public-DraftEditor-content',
                        '[contenteditable="true"]',
                        'div[role="textbox"]'
                    ]

                    caption_field = None
                    for selector in caption_selectors:
                        try:
                            caption_field = await page.wait_for_selector(selector, timeout=5000)
                            if caption_field:
                                break
                        except:
                            continue

                    if caption_field:
                        await caption_field.click()
                        await asyncio.sleep(0.5)
                        await caption_field.type(description, delay=50)
                        logger.info("Description added successfully")
                    else:
                        logger.warning("Could not find caption field")

                except Exception as e:
                    logger.warning(f"Error adding description: {str(e)}")

                # Esperar un momento para que procese
                await asyncio.sleep(2)

                # Buscar y hacer clic en el botón de publicar
                logger.info("Looking for publish button...")
                publish_selectors = [
                    'button:has-text("Post")',
                    'button:has-text("Publicar")',
                    '[data-e2e="post-button"]',
                    'button[type="submit"]'
                ]

                publish_button = None
                for selector in publish_selectors:
                    try:
                        publish_button = await page.wait_for_selector(selector, timeout=5000)
                        if publish_button and await publish_button.is_visible():
                            break
                    except:
                        continue

                if publish_button:
                    logger.info("Clicking publish button...")
                    await publish_button.click()

                    # Esperar confirmación
                    logger.info("Waiting for upload confirmation...")
                    await asyncio.sleep(5)

                    # Verificar si apareció mensaje de éxito
                    success_indicators = [
                        'text="Your video is being uploaded"',
                        'text="Tu video se está subiendo"',
                        'text="Video uploaded successfully"',
                        'text="Video subido exitosamente"'
                    ]

                    upload_success = False
                    for indicator in success_indicators:
                        try:
                            element = await page.wait_for_selector(indicator, timeout=3000)
                            if element:
                                upload_success = True
                                break
                        except:
                            continue

                    if upload_success:
                        return {
                            'success': True,
                            'message': 'Video uploaded successfully to TikTok!'
                        }
                    else:
                        return {
                            'success': True,
                            'message': 'Video upload initiated (confirmation pending)'
                        }

                else:
                    return {
                        'success': False,
                        'error': 'Could not find publish button'
                    }

            except Exception as e:
                logger.error(f"Error uploading video: {str(e)}")
                return {
                    'success': False,
                    'error': str(e)
                }
            finally:
                if browser:
                    await browser.close()
                    logger.info("Browser closed")

    async def clear_session(self):
        """Elimina las cookies guardadas"""
        try:
            if self.cookies_file.exists():
                os.remove(self.cookies_file)
                logger.info("Session cleared successfully")
                return True
            return False
        except Exception as e:
            logger.error(f"Error clearing session: {str(e)}")
            return False


# Función auxiliar para uso síncrono
def upload_to_tiktok(video_path: str, description: str, headless: bool = False) -> Dict[str, any]:
    """Función auxiliar síncrona para subir videos a TikTok"""
    uploader = TikTokUploader()
    return asyncio.run(uploader.upload_video(video_path, description, headless))


if __name__ == "__main__":
    # Test
    test_video = input("Enter video path to upload: ")
    test_description = input("Enter video description: ")

    result = upload_to_tiktok(test_video, test_description, headless=False)
    print(f"\nResult: {result}")
