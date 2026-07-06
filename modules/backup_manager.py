"""
Backup Manager Module
Sistema de backup automático para bases de datos y archivos importantes
"""

import os
import shutil
import sqlite3
import json
import logging
import asyncio
import zipfile
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import threading
import schedule
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BackupManager:
    """Manager de backups automáticos"""

    def __init__(self, backup_dir: str = "backups", max_backups: int = 7):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        self.max_backups = max_backups

        # Archivos a respaldar
        self.db_files = [
            "automation.db",
            "analytics.db",
            "queue.db",
            "hashtags.db",
            "auth.db"
        ]

        self.important_dirs = [
            "cookies",
            "processed"  # Opcional, puede ser muy grande
        ]

        self._scheduler_thread = None
        self._running = False

    def create_backup(self, include_videos: bool = False) -> Dict:
        """Crea un backup completo"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}"
        backup_path = self.backup_dir / backup_name

        try:
            backup_path.mkdir(exist_ok=True)
            backed_up = []
            errors = []

            # Respaldar bases de datos
            for db_file in self.db_files:
                if os.path.exists(db_file):
                    try:
                        # Usar backup de SQLite para consistencia
                        self._backup_sqlite(db_file, backup_path / db_file)
                        backed_up.append(db_file)
                        logger.info(f"Backed up: {db_file}")
                    except Exception as e:
                        errors.append(f"{db_file}: {str(e)}")
                        logger.error(f"Error backing up {db_file}: {e}")

            # Respaldar directorios importantes
            for dir_name in self.important_dirs:
                if dir_name == "processed" and not include_videos:
                    continue

                if os.path.exists(dir_name):
                    try:
                        dest = backup_path / dir_name
                        if os.path.isdir(dir_name):
                            shutil.copytree(dir_name, dest, ignore=shutil.ignore_patterns('*.mp4', '*.mov') if not include_videos else None)
                        else:
                            shutil.copy2(dir_name, dest)
                        backed_up.append(dir_name)
                        logger.info(f"Backed up directory: {dir_name}")
                    except Exception as e:
                        errors.append(f"{dir_name}: {str(e)}")
                        logger.error(f"Error backing up {dir_name}: {e}")

            # Crear archivo de metadatos
            metadata = {
                "created_at": datetime.now().isoformat(),
                "backup_name": backup_name,
                "files_backed_up": backed_up,
                "errors": errors,
                "include_videos": include_videos
            }

            with open(backup_path / "metadata.json", "w") as f:
                json.dump(metadata, f, indent=2)

            # Comprimir backup
            zip_path = self._compress_backup(backup_path)

            # Eliminar directorio sin comprimir
            shutil.rmtree(backup_path)

            # Limpiar backups antiguos
            self._cleanup_old_backups()

            return {
                "success": True,
                "backup_name": backup_name,
                "backup_path": str(zip_path),
                "size_mb": os.path.getsize(zip_path) / (1024 * 1024),
                "files_backed_up": backed_up,
                "errors": errors
            }

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _backup_sqlite(self, source: str, dest: str):
        """Hace backup seguro de SQLite"""
        source_conn = sqlite3.connect(source)
        dest_conn = sqlite3.connect(str(dest))

        source_conn.backup(dest_conn)

        source_conn.close()
        dest_conn.close()

    def _compress_backup(self, backup_path: Path) -> Path:
        """Comprime el backup en ZIP"""
        zip_path = backup_path.with_suffix('.zip')

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(backup_path):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(backup_path)
                    zipf.write(file_path, arcname)

        return zip_path

    def _cleanup_old_backups(self):
        """Elimina backups antiguos, mantiene solo los últimos N"""
        backups = sorted(self.backup_dir.glob("backup_*.zip"), key=os.path.getmtime, reverse=True)

        for old_backup in backups[self.max_backups:]:
            try:
                os.remove(old_backup)
                logger.info(f"Deleted old backup: {old_backup.name}")
            except Exception as e:
                logger.error(f"Error deleting old backup: {e}")

    @staticmethod
    def _safe_extract(zipf: zipfile.ZipFile, extract_path: Path) -> None:
        """Extrae un zip validando cada miembro para evitar Zip Slip (CWE-22)."""
        dest_root = extract_path.resolve()
        for member in zipf.namelist():
            target = (dest_root / member).resolve()
            if not (target == dest_root or dest_root in target.parents):
                raise ValueError(f"Ruta insegura en el backup (Zip Slip): {member}")
        zipf.extractall(extract_path)

    def restore_backup(self, backup_name: str, restore_dbs: bool = True, restore_dirs: bool = True) -> Dict:
        """Restaura un backup"""
        # Evitar path traversal: quedarse solo con el nombre del archivo
        backup_name = Path(backup_name).name
        zip_path = self.backup_dir / f"{backup_name}.zip"

        if not zip_path.exists():
            # Intentar sin extensión
            zip_path = self.backup_dir / backup_name
            if not zip_path.exists():
                return {"success": False, "error": "Backup no encontrado"}

        try:
            # Extraer backup
            extract_path = self.backup_dir / "temp_restore"
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                self._safe_extract(zipf, extract_path)

            restored = []
            errors = []

            # Restaurar bases de datos
            if restore_dbs:
                for db_file in self.db_files:
                    source = extract_path / db_file
                    if source.exists():
                        try:
                            # Hacer backup del actual antes de restaurar
                            if os.path.exists(db_file):
                                shutil.copy2(db_file, f"{db_file}.bak")

                            shutil.copy2(source, db_file)
                            restored.append(db_file)
                        except Exception as e:
                            errors.append(f"{db_file}: {str(e)}")

            # Restaurar directorios
            if restore_dirs:
                for dir_name in self.important_dirs:
                    source = extract_path / dir_name
                    if source.exists():
                        try:
                            if os.path.exists(dir_name):
                                shutil.rmtree(dir_name)
                            shutil.copytree(source, dir_name)
                            restored.append(dir_name)
                        except Exception as e:
                            errors.append(f"{dir_name}: {str(e)}")

            # Limpiar
            shutil.rmtree(extract_path)

            return {
                "success": True,
                "restored": restored,
                "errors": errors
            }

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return {"success": False, "error": str(e)}

    def list_backups(self) -> List[Dict]:
        """Lista todos los backups disponibles"""
        backups = []

        for zip_file in sorted(self.backup_dir.glob("backup_*.zip"), key=os.path.getmtime, reverse=True):
            try:
                stat = zip_file.stat()
                backups.append({
                    "name": zip_file.stem,
                    "filename": zip_file.name,
                    "size_mb": stat.st_size / (1024 * 1024),
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "age_days": (datetime.now() - datetime.fromtimestamp(stat.st_mtime)).days
                })
            except Exception as e:
                logger.error(f"Error reading backup {zip_file}: {e}")

        return backups

    def get_backup_info(self, backup_name: str) -> Optional[Dict]:
        """Obtiene información detallada de un backup"""
        backup_name = Path(backup_name).name
        zip_path = self.backup_dir / f"{backup_name}.zip"

        if not zip_path.exists():
            return None

        try:
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                # Leer metadata si existe
                if "metadata.json" in zipf.namelist():
                    with zipf.open("metadata.json") as f:
                        metadata = json.load(f)
                else:
                    metadata = {}

                files = zipf.namelist()

            stat = zip_path.stat()

            return {
                "name": backup_name,
                "size_mb": stat.st_size / (1024 * 1024),
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "files": files,
                "metadata": metadata
            }

        except Exception as e:
            logger.error(f"Error reading backup info: {e}")
            return None

    def delete_backup(self, backup_name: str) -> bool:
        """Elimina un backup específico"""
        backup_name = Path(backup_name).name
        zip_path = self.backup_dir / f"{backup_name}.zip"

        if zip_path.exists():
            try:
                os.remove(zip_path)
                logger.info(f"Deleted backup: {backup_name}")
                return True
            except Exception as e:
                logger.error(f"Error deleting backup: {e}")
                return False

        return False

    def start_scheduled_backups(self, interval_hours: int = 24, time_of_day: str = "03:00"):
        """Inicia backups programados"""
        if self._running:
            logger.warning("Scheduled backups already running")
            return

        self._running = True

        # Programar backup diario
        schedule.every().day.at(time_of_day).do(self._scheduled_backup)

        # También cada N horas como respaldo
        schedule.every(interval_hours).hours.do(self._scheduled_backup)

        # Ejecutar en thread separado
        def run_scheduler():
            while self._running:
                schedule.run_pending()
                time.sleep(60)  # Verificar cada minuto

        self._scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        self._scheduler_thread.start()

        logger.info(f"Scheduled backups started (daily at {time_of_day}, every {interval_hours}h)")

    def stop_scheduled_backups(self):
        """Detiene los backups programados"""
        self._running = False
        schedule.clear()
        logger.info("Scheduled backups stopped")

    def _scheduled_backup(self):
        """Ejecuta un backup programado"""
        logger.info("Running scheduled backup...")
        result = self.create_backup(include_videos=False)

        if result["success"]:
            logger.info(f"Scheduled backup completed: {result['backup_name']}")
        else:
            logger.error(f"Scheduled backup failed: {result.get('error')}")

    def get_backup_stats(self) -> Dict:
        """Obtiene estadísticas de backups"""
        backups = self.list_backups()

        if not backups:
            return {
                "total_backups": 0,
                "total_size_mb": 0,
                "last_backup": None,
                "oldest_backup": None,
                "scheduled_enabled": self._running
            }

        total_size = sum(b["size_mb"] for b in backups)

        return {
            "total_backups": len(backups),
            "total_size_mb": round(total_size, 2),
            "last_backup": backups[0] if backups else None,
            "oldest_backup": backups[-1] if backups else None,
            "max_backups": self.max_backups,
            "scheduled_enabled": self._running
        }


# Instancia global
backup_manager = BackupManager()


# Test
if __name__ == "__main__":
    manager = BackupManager("test_backups", max_backups=3)

    print("\n💾 Sistema de Backup")
    print("=" * 50)

    # Crear algunos archivos de prueba
    for db in ["test1.db", "test2.db"]:
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER)")
        conn.execute("INSERT INTO test VALUES (1)")
        conn.commit()
        conn.close()

    manager.db_files = ["test1.db", "test2.db"]
    manager.important_dirs = []

    # Crear backup
    print("\n📦 Creando backup...")
    result = manager.create_backup()
    print(f"Resultado: {result}")

    # Crear otro backup
    time.sleep(1)
    result2 = manager.create_backup()
    print(f"Segundo backup: {result2}")

    # Listar backups
    print("\n📋 Backups disponibles:")
    for b in manager.list_backups():
        print(f"  - {b['name']} ({b['size_mb']:.2f} MB)")

    # Estadísticas
    print(f"\n📊 Estadísticas: {manager.get_backup_stats()}")

    # Limpiar
    import shutil
    shutil.rmtree("test_backups")
    os.remove("test1.db")
    os.remove("test2.db")

    print("\n✅ Test completado")
