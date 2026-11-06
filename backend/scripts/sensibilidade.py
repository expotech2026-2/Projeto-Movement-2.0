"""Tabela orçamento × erro esperado do plano de leitura com o perfil padrão; não acessa o banco."""

import argparse

from app.optimization import (
    FixedIntervalPolicy,
    InfeasiblePlan,
    OptimizedIntervalPolicy,
    build_plan,
    default_profile,
)


def main():
    parser = argparse.ArgumentParser(description="Análise de sensibilidade do plano de leitura")
    parser.add_argument("--energy", type=float, default=0.32, help="Energia de um envio, em J")
    args = parser.parse_args()
    profile = default_profile()
    baseline = build_plan(FixedIntervalPolicy(), profile, args.energy)
    print("| Orçamento (%) | Energia (J/dia) | Economia (%) | Erro esperado (°C) |")
    print("| --- | --- | --- | --- |")
    for percent in range(20, 101, 10):
        budget = percent / 100 * baseline.energy_j
        try:
            plan = build_plan(OptimizedIntervalPolicy(args.energy, budget), profile, args.energy)
        except InfeasiblePlan:
            print(f"| {percent} | inviável | — | — |")
            continue
        saving = 100 * (1 - plan.energy_j / baseline.energy_j)
        print(f"| {percent} | {plan.energy_j:.1f} | {saving:.1f} | {plan.expected_error_c:.3f} |")
    print(
        f"\nLinha de base (16 s fixo): {baseline.energy_j:.1f} J/dia, "
        f"erro esperado {baseline.expected_error_c:.3f} °C"
    )


if __name__ == "__main__":
    main()
