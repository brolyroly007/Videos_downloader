"""
Authentication Module
Sistema de autenticación simple para el dashboard
"""

import os
import json
import hashlib
import hmac
import secrets
import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import sqlite3
from functools import wraps

from fastapi import HTTPException, Depends, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials, HTTPBearer, HTTPAuthorizationCredentials

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class User:
    """Usuario del sistema"""
    id: str
    username: str
    password_hash: str
    role: str  # admin, user, viewer
    created_at: str
    last_login: Optional[str]
    is_active: bool

    def to_dict(self) -> dict:
        data = asdict(self)
        del data['password_hash']  # No exponer el hash
        return data


@dataclass
class Session:
    """Sesión de usuario"""
    token: str
    user_id: str
    created_at: str
    expires_at: str
    ip_address: str
    user_agent: str


class AuthDatabase:
    """Base de datos de autenticación"""

    def __init__(self, db_path: str = "auth.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                ip_address TEXT,
                success BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)')

        conn.commit()
        conn.close()

        # Crear usuario admin por defecto si no existe
        self._create_default_admin()

    def _create_default_admin(self):
        """Crea usuario admin por defecto"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM users WHERE role = "admin"')
        if cursor.fetchone()[0] == 0:
            # Crear admin con contraseña por defecto
            admin_id = "admin_" + secrets.token_hex(4)
            password_hash = self._hash_password("admin123")  # Cambiar en producción!

            cursor.execute('''
                INSERT INTO users (id, username, password_hash, role)
                VALUES (?, ?, ?, ?)
            ''', (admin_id, "admin", password_hash, "admin"))

            logger.info("Default admin user created (username: admin, password: admin123)")
            logger.warning("⚠️ CHANGE THE DEFAULT ADMIN PASSWORD!")

        conn.commit()
        conn.close()

    def _hash_password(self, password: str) -> str:
        """Hash de contraseña con salt"""
        salt = secrets.token_hex(16)
        hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return f"{salt}${hash_obj.hex()}"

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verifica una contraseña contra su hash"""
        try:
            salt, stored_hash = password_hash.split('$')
            hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            # Comparación en tiempo constante para no filtrar el hash por timing
            return hmac.compare_digest(hash_obj.hex(), stored_hash)
        except Exception:
            return False

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Obtiene un usuario por username"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, username, password_hash, role, created_at, last_login, is_active
            FROM users WHERE username = ?
        ''', (username,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return User(
                id=row[0], username=row[1], password_hash=row[2],
                role=row[3], created_at=row[4], last_login=row[5], is_active=bool(row[6])
            )
        return None

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Obtiene un usuario por ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, username, password_hash, role, created_at, last_login, is_active
            FROM users WHERE id = ?
        ''', (user_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return User(
                id=row[0], username=row[1], password_hash=row[2],
                role=row[3], created_at=row[4], last_login=row[5], is_active=bool(row[6])
            )
        return None

    def create_user(self, username: str, password: str, role: str = "user") -> User:
        """Crea un nuevo usuario"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        user_id = f"user_{secrets.token_hex(4)}"
        password_hash = self._hash_password(password)

        cursor.execute('''
            INSERT INTO users (id, username, password_hash, role)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, password_hash, role))

        conn.commit()
        conn.close()

        return self.get_user_by_id(user_id)

    def update_password(self, user_id: str, new_password: str) -> bool:
        """Actualiza la contraseña de un usuario"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        password_hash = self._hash_password(new_password)

        cursor.execute('''
            UPDATE users SET password_hash = ? WHERE id = ?
        ''', (password_hash, user_id))

        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Autentica un usuario"""
        user = self.get_user_by_username(username)

        if user and user.is_active and self._verify_password(password, user.password_hash):
            # Actualizar último login
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET last_login = ? WHERE id = ?
            ''', (datetime.now().isoformat(), user.id))
            conn.commit()
            conn.close()
            return user

        return None

    def create_session(self, user_id: str, ip_address: str = "", user_agent: str = "",
                       hours_valid: int = 24) -> Session:
        """Crea una nueva sesión"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        token = secrets.token_urlsafe(32)
        created_at = datetime.now()
        expires_at = created_at + timedelta(hours=hours_valid)

        cursor.execute('''
            INSERT INTO sessions (token, user_id, created_at, expires_at, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (token, user_id, created_at.isoformat(), expires_at.isoformat(), ip_address, user_agent))

        conn.commit()
        conn.close()

        return Session(
            token=token,
            user_id=user_id,
            created_at=created_at.isoformat(),
            expires_at=expires_at.isoformat(),
            ip_address=ip_address,
            user_agent=user_agent
        )

    def validate_session(self, token: str) -> Optional[User]:
        """Valida un token de sesión y retorna el usuario"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT user_id, expires_at FROM sessions WHERE token = ?
        ''', (token,))

        row = cursor.fetchone()
        conn.close()

        if row:
            user_id, expires_at = row
            if datetime.fromisoformat(expires_at) > datetime.now():
                return self.get_user_by_id(user_id)

            # Sesión expirada, eliminar
            self.delete_session(token)

        return None

    def delete_session(self, token: str):
        """Elimina una sesión"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM sessions WHERE token = ?', (token,))
        conn.commit()
        conn.close()

    def delete_user_sessions(self, user_id: str):
        """Elimina todas las sesiones de un usuario"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM sessions WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()

    def cleanup_expired_sessions(self):
        """Limpia sesiones expiradas"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM sessions WHERE expires_at < ?
        ''', (datetime.now().isoformat(),))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    def log_login_attempt(self, username: str, ip_address: str, success: bool):
        """Registra un intento de login"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO login_attempts (username, ip_address, success)
            VALUES (?, ?, ?)
        ''', (username, ip_address, success))
        conn.commit()
        conn.close()

    def get_failed_attempts(self, username: str = None, ip_address: str = None,
                            minutes: int = 15) -> int:
        """Cuenta intentos fallidos recientes"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        since = (datetime.now() - timedelta(minutes=minutes)).isoformat()

        if username:
            cursor.execute('''
                SELECT COUNT(*) FROM login_attempts
                WHERE username = ? AND success = 0 AND created_at > ?
            ''', (username, since))
        elif ip_address:
            cursor.execute('''
                SELECT COUNT(*) FROM login_attempts
                WHERE ip_address = ? AND success = 0 AND created_at > ?
            ''', (ip_address, since))
        else:
            return 0

        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_all_users(self) -> list:
        """Obtiene todos los usuarios"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, username, password_hash, role, created_at, last_login, is_active
            FROM users ORDER BY created_at DESC
        ''')

        users = []
        for row in cursor.fetchall():
            users.append(User(
                id=row[0], username=row[1], password_hash=row[2],
                role=row[3], created_at=row[4], last_login=row[5], is_active=bool(row[6])
            ))

        conn.close()
        return users


class AuthManager:
    """Manager de autenticación para FastAPI"""

    def __init__(self, db_path: str = "auth.db", enabled: bool = True):
        self.db = AuthDatabase(db_path)
        self.enabled = enabled
        self.max_login_attempts = 5
        self.lockout_minutes = 15

    def login(self, username: str, password: str, ip_address: str = "", user_agent: str = "") -> Dict:
        """Realiza login y retorna token"""
        # El bloqueo se cuenta por IP cuando está disponible: así un atacante
        # solo se bloquea a sí mismo y no puede dejar fuera a la cuenta ajena
        # (p. ej. admin) fallando logins a propósito. Sin IP, cae a username.
        if ip_address:
            failed_attempts = self.db.get_failed_attempts(ip_address=ip_address, minutes=self.lockout_minutes)
        else:
            failed_attempts = self.db.get_failed_attempts(username=username, minutes=self.lockout_minutes)

        if failed_attempts >= self.max_login_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Demasiados intentos fallidos. Intenta en {self.lockout_minutes} minutos."
            )

        # Autenticar
        user = self.db.authenticate(username, password)

        if user:
            self.db.log_login_attempt(username, ip_address, True)
            session = self.db.create_session(user.id, ip_address, user_agent)

            # Aprovechar el login para purgar sesiones expiradas (evita que
            # la tabla de sesiones crezca sin límite).
            try:
                self.db.cleanup_expired_sessions()
            except Exception:
                pass

            return {
                "success": True,
                "token": session.token,
                "user": user.to_dict(),
                "expires_at": session.expires_at
            }
        else:
            self.db.log_login_attempt(username, ip_address, False)
            remaining = max(0, self.max_login_attempts - failed_attempts - 1)

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Credenciales inválidas. {remaining} intentos restantes."
            )

    def logout(self, token: str):
        """Cierra sesión"""
        self.db.delete_session(token)
        return {"success": True, "message": "Sesión cerrada"}

    def validate_token(self, token: str) -> Optional[User]:
        """Valida un token y retorna el usuario"""
        return self.db.validate_session(token)

    def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        """Cambia la contraseña de un usuario"""
        user = self.db.get_user_by_id(user_id)
        if user and self.db._verify_password(old_password, user.password_hash):
            self.db.update_password(user_id, new_password)
            self.db.delete_user_sessions(user_id)  # Cerrar todas las sesiones
            return True
        return False

    def create_user(self, username: str, password: str, role: str = "user") -> Dict:
        """Crea un nuevo usuario"""
        existing = self.db.get_user_by_username(username)
        if existing:
            raise HTTPException(status_code=400, detail="El usuario ya existe")

        user = self.db.create_user(username, password, role)
        return user.to_dict()

    def get_all_users(self) -> List[Dict]:
        """Obtiene todos los usuarios (solo admin)"""
        return [u.to_dict() for u in self.db.get_all_users()]


# Dependencias de FastAPI
security_bearer = HTTPBearer(auto_error=False)
security_basic = HTTPBasic(auto_error=False)

# Instancia global (se puede configurar desde app.py)
auth_manager = AuthManager(enabled=os.getenv("AUTH_ENABLED", "false").lower() == "true")


async def get_current_user(
    request: Request,
    bearer: HTTPAuthorizationCredentials = Depends(security_bearer),
    basic: HTTPBasicCredentials = Depends(security_basic)
) -> Optional[User]:
    """Dependencia para obtener el usuario actual"""

    # Si la auth está deshabilitada, retornar None (acceso libre)
    if not auth_manager.enabled:
        return None

    # Intentar con Bearer token primero
    if bearer:
        user = auth_manager.validate_token(bearer.credentials)
        if user:
            return user

    # Intentar con Basic auth
    if basic:
        user = auth_manager.db.authenticate(basic.username, basic.password)
        if user:
            return user

    # Verificar header personalizado
    token = request.headers.get("X-Auth-Token")
    if token:
        user = auth_manager.validate_token(token)
        if user:
            return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autenticado",
        headers={"WWW-Authenticate": "Bearer"}
    )


async def get_optional_user(
    request: Request,
    bearer: HTTPAuthorizationCredentials = Depends(security_bearer)
) -> Optional[User]:
    """Dependencia opcional - no falla si no hay auth"""
    if not auth_manager.enabled:
        return None

    if bearer:
        return auth_manager.validate_token(bearer.credentials)

    token = request.headers.get("X-Auth-Token")
    if token:
        return auth_manager.validate_token(token)

    return None


def require_role(required_role: str):
    """Decorador para requerir un rol específico"""
    async def role_checker(user: User = Depends(get_current_user)):
        if not auth_manager.enabled:
            return None

        if not user:
            raise HTTPException(status_code=401, detail="No autenticado")

        role_hierarchy = {"viewer": 0, "user": 1, "admin": 2}
        user_level = role_hierarchy.get(user.role, 0)
        required_level = role_hierarchy.get(required_role, 0)

        if user_level < required_level:
            raise HTTPException(status_code=403, detail="Permisos insuficientes")

        return user

    return role_checker


# Test
if __name__ == "__main__":
    manager = AuthManager("test_auth.db", enabled=True)

    print("\n🔐 Sistema de Autenticación")
    print("=" * 50)

    # Login con admin
    try:
        result = manager.login("admin", "admin123", "127.0.0.1", "Test")
        print(f"\n✅ Login exitoso!")
        print(f"Token: {result['token'][:20]}...")
        print(f"Usuario: {result['user']}")

        # Validar token
        user = manager.validate_token(result['token'])
        print(f"\n✅ Token válido para: {user.username}")

        # Crear usuario
        new_user = manager.create_user("test_user", "test123", "user")
        print(f"\n✅ Usuario creado: {new_user}")

        # Listar usuarios
        users = manager.get_all_users()
        print(f"\n📋 Usuarios ({len(users)}):")
        for u in users:
            print(f"  - {u['username']} ({u['role']})")

    except HTTPException as e:
        print(f"❌ Error: {e.detail}")

    # Limpiar
    import os
    os.remove("test_auth.db")
