import os

from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash",
    temperature=0
)


def explain_contract(text):

    prompt = f"""
You are a legal assistant.

Explain the following contract in simple English so that a non-lawyer can understand it.

Document:

{text}

Provide:
1. Summary
2. Key obligations
3. Important clauses
4. Potential concerns
"""

    try:

        response = llm.invoke(prompt)

        return response.content

    except Exception as e:

        return f"""
❌ Unable to generate explanation.

Reason:

{str(e)}

Please wait for a minute and try again.
"""