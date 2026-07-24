from comparison.contract_compare import compare_contracts

print(
    compare_contracts(
        "This agreement has arbitration clause.",
        "This agreement has arbitration and confidentiality clause."
    )
)