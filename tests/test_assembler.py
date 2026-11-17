"""Check the assembler against the variant 12 VM specification."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from src.assembler import Instruction, encode_instruction, parse_program


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "spec.asm"
SPEC_HEX_LINES = [
    "0x12, 0x3A, 0x00, 0x00, 0xA0, 0x5F, 0x00, 0x00, 0x00",
    "0x69, 0x3A, 0x00, 0x00, 0xE0, 0x5C, 0x3C, 0x00, 0x00, 0x00",
    "0x8A, 0x6D, 0x00, 0x00, 0x20, 0x58, 0x00, 0x00, 0x00",
    "0x8D, 0x2B, 0x00, 0x00, 0xE0, 0x03, 0x00, 0x00, 0xC0, 0x22, 0x00, "
    "0x00, 0x00",
]


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

        self.assertEqual(
            [instruction.format_fields() for instruction in program],
            [
                "A=18, B=464, C=765",
                "A=9, B=467, C=231, D=482",
                "A=10, B=876, C=705",
                "A=13, B=348, C=31, D=278",
            ],
        )

    def test_cli_writes_spec_bytes(self):
        """Write the exact binary and show distinct outputs for both modes."""
        expected_binary = bytes(
            int(byte, 16)
            for line in SPEC_HEX_LINES
            for byte in line.split(", ")
        )
        count = ["Assembled instructions: 4"]
        modes = (([], count), (["--test"], count + SPEC_HEX_LINES))
        for flags, output in modes:
            with self.subTest(str(flags)), tempfile.TemporaryDirectory() as tmp:
                command = [str(ROOT / "run.sh"), str(FIXTURE), "example.bin"]
                result = subprocess.run(
                    command + flags,
                    check=True,
                    capture_output=True,
                    text=True,
                    cwd=tmp,
                )
                self.assertEqual(
                    (Path(tmp) / "example.bin").read_bytes(), expected_binary
                )
                self.assertEqual(result.stdout.splitlines(), output)

    def test_invalid_program_keeps_existing_output(self):
        """Reject a malformed program before touching its output file."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "invalid.asm"
            binary = Path(tmp) / "example.bin"
            source.write_text("LOAD 0, 7\nREAD 0, 256, 1\n", encoding="utf-8")
            binary.write_bytes(b"existing output")
            result = subprocess.run(
                [str(ROOT / "run.sh"), str(source), str(binary), "--test"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("line 2: C: value must be", result.stderr)
            self.assertEqual(binary.read_bytes(), b"existing output")

    def test_source_syntax(self):
        """Accept case-insensitive mnemonics, hex and comments."""
        source = "# header\n\n  load 0x1D0, 0X2FD  # constant\n"
        self.assertEqual(parse_program(source), [Instruction(18, (464, 765))])

    def test_maximum_operand_values(self):
        """Accept values that fit exactly in the specified field widths."""
        maximum_address = 4294967295
        read, add = parse_program(
            f"READ {maximum_address}, 255, {maximum_address}\n"
            f"ADD {maximum_address}, {maximum_address}, {maximum_address}\n"
        )
        self.assertEqual(
            read, Instruction(9, (maximum_address, 255, maximum_address))
        )
        self.assertEqual(
            encode_instruction(read),
            bytes.fromhex("e9 ff ff ff ff ff ff ff ff 1f"),
        )
        self.assertEqual(
            encode_instruction(add),
            bytes.fromhex("ed ff ff ff ff ff ff ff ff ff ff ff 1f"),
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
