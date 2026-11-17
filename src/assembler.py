"""Assemble variant 12 source into VM machine code."""

import argparse
from dataclasses import dataclass
from pathlib import Path


BITS_PER_BYTE = 8
OPCODE_BITS = 5
ADDRESS_BITS = 32
CONSTANT_BITS = 32
OFFSET_BITS = 8


@dataclass(frozen=True)
class Command:
    """Opcode and operand field widths in assembly source order."""

    opcode: int
    operand_bits: tuple[int, ...]


COMMANDS = {
    "LOAD": Command(18, (ADDRESS_BITS, CONSTANT_BITS)),
    "READ": Command(9, (ADDRESS_BITS, OFFSET_BITS, ADDRESS_BITS)),
    "STORE": Command(10, (ADDRESS_BITS, ADDRESS_BITS)),
    "ADD": Command(13, (ADDRESS_BITS, ADDRESS_BITS, ADDRESS_BITS)),
}
COMMANDS_BY_OPCODE = {command.opcode: command for command in COMMANDS.values()}


@dataclass(frozen=True)
class Instruction:
    """Opcode and operand values in specification field order."""

    opcode: int
    operands: tuple[int, ...]

    def format_fields(self) -> str:
        """Return a specification-style list such as A=18, B=464, C=765."""
        values = (self.opcode, *self.operands)
        return ", ".join(
            f"{field}={value}" for field, value in zip("ABCD", values)
        )


def parse_operand(token: str, width: int, field: str) -> int:
    """Read a decimal or hexadecimal unsigned operand of the given width."""
    token = token.strip().lower()
    digits = token.removeprefix("0x")
    alphabet = "0123456789abcdef" if token.startswith("0x") else "0123456789"
    if not digits or any(digit not in alphabet for digit in digits):
        raise ValueError(f"{field}: expected a decimal or 0x integer")
    base = 16 if token.startswith("0x") else 10
    value = int(digits.lstrip("0") or "0", base)
    maximum = (1 << width) - 1
    if value > maximum:
        raise ValueError(f"{field}: value must be in 0..{maximum}")
    return value


def parse_instruction(line: str) -> Instruction:
    """Parse one instruction after stripping its comment and whitespace."""
    mnemonic, *argument_text = line.split(maxsplit=1)
    command = COMMANDS.get(mnemonic.upper())
    if command is None:
        raise ValueError(f"unknown mnemonic {mnemonic!r}")
    tokens = argument_text[0].split(",") if argument_text else []
    if len(tokens) != len(command.operand_bits):
        raise ValueError(
            f"{mnemonic.upper()}: expected {len(command.operand_bits)} operands"
        )
    operands = tuple(
        parse_operand(token, width, field)
        for token, width, field in zip(tokens, command.operand_bits, "BCD")
    )
    return Instruction(command.opcode, operands)


def parse_program(source: str) -> list[Instruction]:
    """Translate assembly source, reporting errors with source line numbers."""
    instructions = []
    for number, line in enumerate(source.splitlines(), start=1):
        statement = line.partition("#")[0].strip()
        if not statement:
            continue
        try:
            instructions.append(parse_instruction(statement))
        except ValueError as error:
            raise ValueError(f"line {number}: {error}") from error
    return instructions


def encode_instruction(instruction: Instruction) -> bytes:
    """Pack an instruction produced by the parser in little-endian order."""
    command = COMMANDS_BY_OPCODE[instruction.opcode]
    word = instruction.opcode
    bit_position = OPCODE_BITS
    for operand, width in zip(
        instruction.operands, command.operand_bits, strict=True
    ):
        word |= operand << bit_position
        bit_position += width
    byte_count = (bit_position + BITS_PER_BYTE - 1) // BITS_PER_BYTE
    return word.to_bytes(byte_count, byteorder="little")


def format_bytes(instruction_bytes: bytes) -> str:
    """Format one encoded instruction as in the VM specification."""
    return ", ".join(f"0x{byte:02X}" for byte in instruction_bytes)


def main() -> None:
    """Assemble a source file and report its instruction count."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="UTF-8 assembly source")
    parser.add_argument("output", type=Path, help="path for the output binary")
    parser.add_argument("--test", action="store_true", help="print VM bytes")
    args = parser.parse_args()

    try:
        program = parse_program(args.source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        parser.error(f"{args.source}: {error}")

    encoded = [encode_instruction(instruction) for instruction in program]
    try:
        args.output.write_bytes(b"".join(encoded))
    except OSError as error:
        parser.error(f"{args.output}: {error}")

    print(f"Assembled instructions: {len(program)}")
    if args.test:
        for instruction_bytes in encoded:
            print(format_bytes(instruction_bytes))


if __name__ == "__main__":
    main()
