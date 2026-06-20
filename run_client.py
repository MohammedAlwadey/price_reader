import os
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)

try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except Exception:
    pass

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


# نسخة العميل تمنع أوامر الإدارة الحساسة.
# إذا احتجت نسخة داخلية لك كمطور، اجعلها False قبل التحزيم ولا تسلمها للعميل.
CLIENT_BUILD = True

BLOCKED_CLIENT_COMMANDS = {
    "createsuperuser",
    "shell",
    "dbshell",
    "changepassword",
    "flush",
    "dumpdata",
    "loaddata",
}


def run_server():
    from pricing.licensing import validate_license, LicenseError

    try:
        license_payload = validate_license()
        print(f"License OK: {license_payload.get('customer')} / {license_payload.get('edition')}")
    except LicenseError as exc:
        print(f"License Error: {exc}")
        raise SystemExit(3)

    from django.core.wsgi import get_wsgi_application
    from waitress import serve

    application = get_wsgi_application()

    listen = os.environ.get("PRICE_READER_LISTEN", "0.0.0.0:2026")
    threads = int(os.environ.get("PRICE_READER_THREADS", "8"))

    serve(application, listen=listen, threads=threads)



def run_manage_command():
    command = sys.argv[1] if len(sys.argv) > 1 else ""

    if command == "serverid":
        from pricing.licensing import get_current_server_id
        print(get_current_server_id())
        raise SystemExit(0)

    if CLIENT_BUILD and command in BLOCKED_CLIENT_COMMANDS:
        print("This management command is disabled in the client build.")
        raise SystemExit(2)

    from django.core.management import execute_from_command_line

    execute_from_command_line([sys.argv[0], *sys.argv[1:]])


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_manage_command()
    else:
        run_server()