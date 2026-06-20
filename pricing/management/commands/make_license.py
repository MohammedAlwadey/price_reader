import base64
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from pricing.licensing import _canonical_payload


class Command(BaseCommand):
    help = "Create signed license.json for a customer."

    def add_arguments(self, parser):
        parser.add_argument("--customer", required=True)
        parser.add_argument("--server-id", required=True)
        parser.add_argument("--expires", required=True)
        parser.add_argument("--max-users", type=int, required=True)
        parser.add_argument("--max-active-sessions", type=int, default=None)
        parser.add_argument("--edition", default="Professional")
        parser.add_argument(
            "--private-key",
            default="license_keys/private_key.pem",
        )
        parser.add_argument(
            "--output",
            default="license.json",
        )

    def handle(self, *args, **options):
        private_key_path = Path(options["private_key"])
        output_path = Path(options["output"])

        if not private_key_path.exists():
            raise CommandError(f"Private key not found: {private_key_path}")

        if options["max_users"] < 1:
            raise CommandError("--max-users must be at least 1")

        payload = {
            "customer": options["customer"],
            "server_id": options["server_id"],
            "expires": options["expires"],
            "max_users": options["max_users"],
            "max_active_sessions": options["max_active_sessions"] or options["max_users"],
            "edition": options["edition"],
        }

        private_key = serialization.load_pem_private_key(
            private_key_path.read_bytes(),
            password=None,
        )

        signature = private_key.sign(
            _canonical_payload(payload),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

        license_data = {
            "payload": payload,
            "signature": base64.b64encode(signature).decode("ascii"),
        }

        output_path.write_text(
            json.dumps(license_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        self.stdout.write(self.style.SUCCESS(f"License created: {output_path}"))