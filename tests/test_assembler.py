"""Check the stage 1 assembler against the VM specification."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from src.assembler import Instruction, parse_program


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "spec.asm"


class AssemblerTests(unittest.TestCase):
    """Exercise intermediate translation and the command-line interface."""

    def test_spec_instructions(self):
        """Translate the four official instructions into their field values."""
        program = parse_program(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(
            program,
            [
                Instruction(18, (464, 765)),
                Instruction(9, (467, 231, 482)),
                Instruction(10, (876, 705)),
                Instruction(13, (348, 31, 278)),
            ],
        )

    def test_test_mode(self):
        """Print the official fields and preserve the binary output path."""
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "example.bin"
            result = subprocess.run(
                [str(ROOT / "run.sh"), str(FIXTURE), str(binary), "--test"],
                check=True,
                capture_output=True,
                text=True,
                cwd=directory,
            )
            self.assertFalse(binary.exists())
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "A=18, B=464, C=765",
                "A=9, B=467, C=231, D=482",
                "A=10, B=876, C=705",
                "A=13, B=348, C=31, D=278",
            ],
        )

    def test_source_syntax(self):
        """Accept case-insensitive mnemonics, hex and comments."""
        source = "# header\n\n  load 0x1D0, 0X2FD  # constant\n"
        self.assertEqual(parse_program(source), [Instruction(18, (464, 765))])

    def test_maximum_operand_values(self):
        """Accept values that fit exactly in the specified field widths."""
        self.assertEqual(
            parse_program("READ 4294967295, 255, 0"),
            [Instruction(9, (4294967295, 255, 0))],
        )

    def test_invalid_source_reports_line(self):
        """Reject malformed instructions and values outside the field width."""
        invalid_sources = (
            ("MOVE 1, 2", "unknown mnemonic"),
            ("LOAD", "LOAD: expected 2 operands"),
            ("LOAD 1", "LOAD: expected 2 operands"),
            ("LOAD 1, 2, 3", "LOAD: expected 2 operands"),
            ("LOAD 1,", "C: expected"),
            ("LOAD 1, -1", "C: expected"),
            ("LOAD 4294967296, 1", "B: value must be"),
            ("LOAD 1, 4294967296", "C: value must be"),
            ("READ 1, 256, 2", "C: value must be"),
            ("READ 1, 0, 4294967296", "D: value must be"),
        )
        for statement, message in invalid_sources:
            with self.subTest(statement=statement):
                with self.assertRaisesRegex(ValueError, rf"line 2: {message}"):
                    parse_program(f"# header\n{statement}")
