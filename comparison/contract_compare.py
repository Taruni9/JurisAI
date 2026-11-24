from backend.gemini_helper import invoke_llm


def compare_contracts(contract1, contract2):

    prompt = f"""
Compare these two contracts.

Contract 1:

{contract1}

Contract 2:

{contract2}

List the major differences.
"""

    return invoke_llm(prompt)
