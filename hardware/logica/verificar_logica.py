"""Confere todas as equações de docs/eletronica-digital.md; --markdown imprime as tabelas."""

import argparse

LIVRE, ENTRANDO_A, ENTRANDO_AB, SAINDO_B, SAINDO_BA = 0b000, 0b001, 0b011, 0b101, 0b111
STATES = {
    LIVRE: "LIVRE",
    ENTRANDO_A: "ENTRANDO_A",
    ENTRANDO_AB: "ENTRANDO_AB",
    SAINDO_B: "SAINDO_B",
    SAINDO_BA: "SAINDO_BA",
}
UNUSED = (0b010, 0b100, 0b110)


def bits(value: int, width: int) -> list[int]:
    return [(value >> i) & 1 for i in range(width)]


def door_spec(state: int, a: int, b: int) -> tuple[int, int, int]:
    """Especificação da porta: (próximo estado, pulso de entrada, pulso de saída)."""
    if not a and not b:
        return LIVRE, int(state == ENTRANDO_AB), int(state == SAINDO_BA)
    if state == LIVRE:
        return (ENTRANDO_A if a and not b else SAINDO_B if b and not a else LIVRE), 0, 0
    if state in (ENTRANDO_A, ENTRANDO_AB):
        return (ENTRANDO_AB if b else ENTRANDO_A), 0, 0
    if state in (SAINDO_B, SAINDO_BA):
        return (SAINDO_BA if a else SAINDO_B), 0, 0
    raise ValueError(f"estado inválido {state:03b}")


def door_equations(state: int, a: int, b: int) -> tuple[int, int, int]:
    """Equações mínimas dos flip-flops D e das saídas de Mealy."""
    q0, q1, q2 = bits(state, 3)
    na, nb, nq0, nq2 = 1 - a, 1 - b, 1 - q0, 1 - q2
    d2 = (a & q2) | (b & q2) | (b & na & nq0)
    d1 = (a & q2) | (b & q0 & nq2)
    d0 = (b & q0) | (a & nb) | (b & na)
    entrada = q1 & nq2 & na & nb
    saida = q1 & q2 & na & nb
    return d2 << 2 | d1 << 1 | d0, entrada, saida


def counter_spec(q: int, e: int, s: int) -> int:
    if e and not s:
        return min(q + 1, 15)
    if s and not e:
        return max(q - 1, 0)
    return q


def counter_equations(q: int, e: int, s: int) -> int:
    """Contador crescente/decrescente de 4 bits com flip-flops T e saturação em 0 e 15."""
    q0, q1, q2, q3 = bits(q, 4)
    n0, n1, n2 = 1 - q0, 1 - q1, 1 - q2
    empty = int(q == 0)
    full = q0 & q1 & q2 & q3
    up = e & (1 - s) & (1 - full)
    down = s & (1 - e) & (1 - empty)
    t0 = up | down
    t1 = (up & q0) | (down & n0)
    t2 = (up & q0 & q1) | (down & n0 & n1)
    t3 = (up & q0 & q1 & q2) | (down & n0 & n1 & n2)
    return q ^ (t0 | t1 << 1 | t2 << 2 | t3 << 3)


def ac_spec(a: int, b: int, c: int, m: int) -> int:
    """Resfria se quente (A), sem AC_OFF (C) e em modo manual (M) ou com a sala ocupada (B)."""
    return int(bool(a) and not c and (bool(m) or bool(b)))


def ac_sop(a: int, b: int, c: int, m: int) -> int:
    return (a & b & (1 - c)) | (a & (1 - c) & m)


def run(sequence: list[tuple[int, int]]) -> int:
    """Simula a porta com as equações e devolve o saldo de pessoas da sequência de (A, B)."""
    state, balance = LIVRE, 0
    for a, b in sequence:
        state, entrada, saida = door_equations(state, a, b)
        balance += entrada - saida
    return balance


SEQUENCES = {
    "entrada completa": ([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)], 1),
    "saída completa": ([(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)], -1),
    "entrada rápida (sem 11)": ([(0, 0), (1, 0), (0, 1), (0, 0)], 1),
    "desistiu na porta": ([(0, 0), (1, 0), (0, 0)], 0),
    "entrou até a metade e voltou": ([(0, 0), (1, 0), (1, 1), (1, 0), (0, 0)], 0),
    "os dois feixes juntos": ([(0, 0), (1, 1), (0, 0)], 0),
    "duas entradas seguidas": ([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)] * 2, 2),
}


def check() -> list[str]:
    errors = []
    for state in STATES:
        for a in (0, 1):
            for b in (0, 1):
                if door_equations(state, a, b) != door_spec(state, a, b):
                    errors.append(f"porta: estado {state:03b}, A={a}, B={b}")
    for state in UNUSED:
        if door_equations(state, 0, 0)[0] != LIVRE:
            errors.append(f"porta: estado inválido {state:03b} não volta a LIVRE")
    for name, (sequence, expected) in SEQUENCES.items():
        if run(sequence) != expected:
            errors.append(f"sequência '{name}': esperado {expected}")
    for q in range(16):
        for e in (0, 1):
            for s in (0, 1):
                if counter_equations(q, e, s) != counter_spec(q, e, s):
                    errors.append(f"contador: Q={q}, E={e}, S={s}")
    for n in range(16):
        a, b, c, m = (n >> 3) & 1, (n >> 2) & 1, (n >> 1) & 1, n & 1
        if ac_sop(a, b, c, m) != ac_spec(a, b, c, m):
            errors.append(f"ar-condicionado: A={a}, B={b}, C={c}, M={m}")
    return errors


def print_tables() -> None:
    print("### Máquina de estados da porta\n")
    print("| Estado | Q2 Q1 Q0 | A B = 00 | 01 | 10 | 11 |")
    print("| --- | --- | --- | --- | --- | --- |")
    for state, name in STATES.items():
        cells = []
        for a, b in ((0, 0), (0, 1), (1, 0), (1, 1)):
            nxt, entrada, saida = door_spec(state, a, b)
            mark = " / ENTRADA" if entrada else " / SAÍDA" if saida else ""
            cells.append(f"{STATES[nxt]}{mark}")
        print(f"| {name} | {state:03b} | " + " | ".join(cells) + " |")
    print("\n### Função do ar-condicionado F = A · ¬C · (M + B)\n")
    print("| A | B | C | M | F | Mintermo |")
    print("| --- | --- | --- | --- | --- | --- |")
    for n in range(16):
        a, b, c, m = (n >> 3) & 1, (n >> 2) & 1, (n >> 1) & 1, n & 1
        f = ac_spec(a, b, c, m)
        print(f"| {a} | {b} | {c} | {m} | {f} | {'m' + str(n) if f else ''} |")
    print("\n### Contador de ocupação\n")
    print("| Q | Q+ com ENTRADA | Q+ com SAÍDA |")
    print("| --- | --- | --- |")
    for q in range(16):
        print(f"| {q} | {counter_equations(q, 1, 0)} | {counter_equations(q, 0, 1)} |")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verificar as equações lógicas do Movement")
    parser.add_argument("--markdown", action="store_true", help="Imprimir as tabelas-verdade")
    args = parser.parse_args()
    errors = check()
    if errors:
        print("Divergência:", errors[0])
        return 1
    if args.markdown:
        print_tables()
        print()
    print(
        "OK: 20 transições da porta, 3 estados inválidos, "
        f"{len(SEQUENCES)} sequências, 64 transições do contador e 16 combinações de F conferidas"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
