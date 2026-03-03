from pathlib import Path

from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand

from intelligence.report_generator import generate_report


class Command(BaseCommand):
    help = "Generate a weekly digest report"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=7, help="Number of days to cover (default: 7)"
        )
        parser.add_argument(
            "--output", type=str, help="Write report to file (default: stdout)"
        )

    def handle(self, **options):
        days = options["days"]
        output_path = options.get("output")

        report = async_to_sync(generate_report)(days=days)

        if output_path:
            Path(output_path).write_text(report)
            self.stdout.write(f"Report written to {output_path}")
        else:
            self.stdout.write(report)
