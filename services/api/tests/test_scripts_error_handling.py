"""Synthetic CLI error-handling tests; no production CSV or database is used."""

import csv
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts import analyze, seed_incidents
from services.api import promote_admin, services_auth


CSV_COLUMNS = (
    "incident_id",
    "date",
    "location_id",
    "category",
    "description",
    "status",
    "customer_id",
    "satisfaction_score",
    "reporter_id",
)


def write_valid_csv(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "incident_id": "SYN-CLI-1",
                "date": "2026-10-28",
                "location_id": "COL-01",
                "category": "SUPPLY",
                "description": "Synthetic incident description",
                "status": "OPEN",
                "customer_id": "",
                "satisfaction_score": "",
                "reporter_id": "SYN-EMP-1",
            }
        )


class AnalyzeCliErrorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def run_analyzer(self, csv_path: Path | None, input_side_effect="n"):
        stdout = StringIO()
        stderr = StringIO()
        arguments = ["analyze.py"]
        if csv_path is not None:
            arguments.append(str(csv_path))
        with (
            patch.object(sys, "argv", arguments),
            patch("builtins.input", side_effect=input_side_effect),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            try:
                analyze.main()
            except SystemExit as exc:
                return exc.code, stdout.getvalue(), stderr.getvalue()
        return 0, stdout.getvalue(), stderr.getvalue()

    def assert_clean_failure(self, result, message: str, expected_code=1):
        code, stdout, stderr = result
        self.assertEqual(code, expected_code)
        self.assertIn(message, stderr)
        self.assertNotIn("Traceback", stdout + stderr)

    def test_missing_argument_has_nonzero_exit(self):
        self.assert_clean_failure(
            self.run_analyzer(None),
            "Debe indicar la ruta del archivo CSV.",
            expected_code=2,
        )

    def test_missing_empty_header_missing_columns_and_invalid_encoding(self):
        cases = [
            (
                "missing.csv",
                None,
                "No se encontró el archivo CSV indicado.",
            ),
            ("empty.csv", b"", "El CSV está vacío o no contiene una cabecera."),
            ("headerless.csv", b"\n", "El CSV está vacío o no contiene una cabecera."),
            (
                "missing-columns.csv",
                b"incident_id,date\nSYN-1,2026-01-01\n",
                "Al CSV le faltan columnas requeridas.",
            ),
            ("invalid-encoding.csv", b"\xff\xfe", "El CSV debe estar codificado en UTF-8."),
            (
                "malformed.csv",
                b'"incident_id,date\n',
                "El archivo CSV tiene un formato no válido.",
            ),
        ]
        for filename, contents, message in cases:
            with self.subTest(filename=filename):
                csv_path = self.directory / filename
                if contents is not None:
                    csv_path.write_bytes(contents)
                self.assert_clean_failure(
                    self.run_analyzer(csv_path),
                    message,
                )

    def test_permission_error_has_a_safe_message(self):
        csv_path = self.directory / "synthetic.csv"
        write_valid_csv(csv_path)
        with patch.object(Path, "open", side_effect=PermissionError("private path")):
            result = self.run_analyzer(csv_path)
        self.assert_clean_failure(
            result,
            "No hay permisos para leer el archivo CSV indicado.",
        )
        self.assertNotIn("private path", result[2])

    def test_write_failure_and_eof_have_nonzero_exit(self):
        csv_path = self.directory / "synthetic.csv"
        write_valid_csv(csv_path)
        with patch.object(analyze, "export_results", side_effect=OSError("private path")):
            self.assert_clean_failure(
                self.run_analyzer(csv_path, input_side_effect="s"),
                "no se pudieron escribir los resultados CSV.",
            )
        self.assert_clean_failure(
            self.run_analyzer(csv_path, input_side_effect=EOFError),
            "no se recibió una respuesta para exportar.",
        )


class IncidentSeedCliErrorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.csv_path = self.directory / "synthetic.csv"

    def run_seed(self, csv_path=None):
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = seed_incidents.main(
                [] if csv_path is None else [str(csv_path)]
            )
        return code, stdout.getvalue(), stderr.getvalue()

    def assert_clean_failure(self, result, message: str):
        code, stdout, stderr = result
        self.assertEqual(code, 1)
        self.assertIn(message, stderr)
        self.assertNotIn("Traceback", stdout + stderr)

    def test_input_failures_are_reported_without_tracebacks(self):
        cases = [
            (None, None, "No se encontró el archivo CSV."),
            ("empty.csv", b"", "El CSV está vacío o no contiene cabecera."),
            ("missing-columns.csv", b"incident_id,date\n", "Al CSV le faltan columnas requeridas."),
            ("invalid-encoding.csv", b"\xff\xfe", "El CSV debe estar codificado en UTF-8."),
            ("malformed.csv", b'"incident_id,date\n', "El archivo CSV tiene un formato no válido."),
        ]
        for filename, contents, message in cases:
            with self.subTest(filename=filename):
                csv_path = self.directory / filename if filename else self.directory / "absent.csv"
                if contents is not None:
                    csv_path.write_bytes(contents)
                self.assert_clean_failure(self.run_seed(csv_path), message)

    def test_database_failure_is_reported_without_internal_details(self):
        write_valid_csv(self.csv_path)
        with patch.object(
            seed_incidents.database,
            "get_incidents_tables",
            side_effect=OSError("private database path"),
        ):
            result = self.run_seed(self.csv_path)
        self.assert_clean_failure(
            result,
            "No se pudo acceder a la base de datos de incidencias.",
        )
        self.assertNotIn("private database path", result[2])

    def test_permission_error_is_reported_without_internal_details(self):
        write_valid_csv(self.csv_path)
        with patch.object(Path, "open", side_effect=PermissionError("private path")):
            result = self.run_seed(self.csv_path)
        self.assert_clean_failure(
            result,
            "No hay permisos para leer el archivo CSV.",
        )
        self.assertNotIn("private path", result[2])


class PromoteAdminCliErrorTests(unittest.TestCase):
    def run_promote(self, email):
        stdout = StringIO()
        stderr = StringIO()
        with (
            patch.object(sys, "argv", ["promote_admin.py", email]),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            try:
                promote_admin.main()
            except SystemExit as exc:
                return exc.code, stdout.getvalue(), stderr.getvalue()
        return 0, stdout.getvalue(), stderr.getvalue()

    def test_database_failure_exits_cleanly_without_email_or_details(self):
        with patch.object(
            services_auth,
            "obtener_usuario_por_email",
            side_effect=OSError("private database path"),
        ):
            code, stdout, stderr = self.run_promote("synthetic@example.test")
        self.assertNotEqual(code, 0)
        self.assertIn("No se pudo consultar el usuario", stderr)
        self.assertNotIn("Traceback", stdout + stderr)
        self.assertNotIn("private database path", stdout + stderr)
        self.assertNotIn("synthetic@example.test", stdout + stderr)

    def test_success_message_preserves_original_format(self):
        user = SimpleNamespace(id=123, email="synthetic@example.test")
        with (
            patch.object(services_auth, "obtener_usuario_por_email", return_value=user),
            patch.object(services_auth, "actualizar_usuario", return_value=user),
        ):
            code, stdout, stderr = self.run_promote("synthetic@example.test")
        self.assertEqual(code, 0)
        self.assertEqual(
            stdout.strip(),
            "Usuario synthetic@example.test promovido a admin (id=123).",
        )
        self.assertEqual(stderr, "")


if __name__ == "__main__":
    unittest.main()
