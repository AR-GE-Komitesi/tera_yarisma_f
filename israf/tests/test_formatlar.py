from django.conf import settings
from django.test import SimpleTestCase

from israf.aktarim import Report, check_headers, parse_rows, read_csv
from israf.formatlar import FORMATS
from israf.management.commands.format_belgesi import _csv_lines, render


class FormatContractTests(SimpleTestCase):
    def test_every_example_is_valid_csv_for_its_format(self):
        for kind, fmt in FORMATS.items():
            with self.subTest(format=kind):
                text = _csv_lines(fmt.column_names, fmt.examples) + "\n"
                parsed = read_csv(text.encode("utf-8"))
                report = Report()
                check_headers(fmt, parsed, report)
                records = parse_rows(fmt, parsed, report)
                self.assertEqual(report.errors, [])
                self.assertEqual(len(records), len(fmt.examples))

    def test_committed_document_matches_contract(self):
        path = settings.BASE_DIR / "docs" / "VERI_FORMATI.md"
        self.assertEqual(
            path.read_text(encoding="utf-8"),
            render(),
            "docs/VERI_FORMATI.md eski. `python manage.py format_belgesi` çalıştırın.",
        )
