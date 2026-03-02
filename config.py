import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    def _load_env():
        path = os.path.join(os.getcwd(), ".env")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if not s or s.startswith("#") or "=" not in s:
                        continue
                    k, v = s.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
                        v = v[1:-1]
                    if k not in os.environ:
                        os.environ[k] = v
    _load_env()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME", "bd_genesis")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", os.getenv("DB_PASSWORD", "sa"))

APP_TITLE = "Sistema de Gestión de Eventos"
APP_ICON = "🎪"

ROLES = [
    "Administrador",
    "Jefe de Eventos",
    "Jefe de Planificación",
    "Jefe de Logística",
    "Secretaria de Eventos",
]

ESTADOS_EVENTO = [
    "Registrada",
    "En Planificación",
    "Plan Aprobado",
    "Confirmada",
    "En Ejecución",
    "Cerrada",
    "Cancelada",
]
