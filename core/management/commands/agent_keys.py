import re

from django.core.management.base import BaseCommand, CommandError

from core.models import AgentKey
from core.services import scoping

SLUG_RE = re.compile(r"^[a-z0-9-]+$")


class Command(BaseCommand):
    help = (
        "Manage per-agent API keys. Subcommands: "
        "create <name> --default-domain <slug> [--allow <slug> ...] | "
        "revoke <name> | list. The plaintext key is printed exactly once "
        "at creation and never stored."
    )

    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest="action", required=True)

        create = sub.add_parser("create")
        create.add_argument("name")
        create.add_argument("--default-domain", required=True)
        create.add_argument(
            "--allow", action="append", default=[],
            help="Additional allowed domain (repeatable); the default "
                 "domain is always allowed.",
        )

        revoke = sub.add_parser("revoke")
        revoke.add_argument("name")

        sub.add_parser("list")

    def handle(self, *args, **options):
        action = options["action"]
        if action == "create":
            name = options["name"]
            default = options["default_domain"]
            for value, what in [(name, "name"), (default, "default domain")]:
                if not SLUG_RE.match(value):
                    raise CommandError(f"invalid {what}: {value!r} (allowed: [a-z0-9-]+)")
            allowed = [default]
            for extra in options["allow"]:
                if not SLUG_RE.match(extra):
                    raise CommandError(f"invalid domain: {extra!r} (allowed: [a-z0-9-]+)")
                if extra not in allowed:
                    allowed.append(extra)
            if AgentKey.objects.filter(name=name).exists():
                raise CommandError(f"key {name!r} already exists (revoke it first)")
            plaintext, key_hash = scoping.generate_key()
            AgentKey.objects.create(
                name=name, key_hash=key_hash,
                default_domain=default, allowed_domains=allowed,
            )
            self.stdout.write(f"created agent key {name!r}")
            self.stdout.write(f"  default domain: {default}")
            self.stdout.write(f"  allowed domains: {', '.join(allowed)}")
            self.stdout.write(
                self.style.WARNING(
                    f"  key (shown once, store it now): {plaintext}"
                )
            )
        elif action == "revoke":
            updated = AgentKey.objects.filter(name=options["name"]).update(is_active=False)
            if not updated:
                raise CommandError(f"no key named {options['name']!r}")
            self.stdout.write(f"revoked {options['name']!r}")
        elif action == "list":
            keys = AgentKey.objects.all()
            if not keys:
                self.stdout.write("no agent keys")
            for key in keys:
                status = "active" if key.is_active else "revoked"
                last = key.last_used_at.isoformat() if key.last_used_at else "never"
                self.stdout.write(
                    f"{key.name}: {status} | default={key.default_domain} "
                    f"| allowed={','.join(key.allowed_domains)} | last_used={last}"
                )
