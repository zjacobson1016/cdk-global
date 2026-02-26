"""Test the Invoice Processing Agent locally on a Databricks cluster."""
from agent import AGENT
from mlflow.types.responses import ResponsesAgentRequest, ChatContext

test_cases = [
    "Give me a summary of all invoices currently in the system.",
    "Show me all invoices pending exception review.",
    "How is AutoZone Commercial performing as a supplier?",
    "What invoices are urgent and need immediate attention?",
]

for i, question in enumerate(test_cases):
    print(f"\n{'='*60}")
    print(f"TEST {i+1}: {question}")
    print(f"{'='*60}")

    request = ResponsesAgentRequest(
        input=[{"role": "user", "content": question}],
        context=ChatContext(user_id="test@sunsetcdjr.com"),
    )

    result = AGENT.predict(request)

    for item in result.output:
        item_dict = item.model_dump(exclude_none=True)
        if item_dict.get("type") == "message":
            print(f"\nAgent: {item_dict.get('content', [{}])[0].get('text', 'No text')}")
        else:
            print(f"\n[{item_dict.get('type', 'unknown')}]: {str(item_dict)[:200]}")

print(f"\n{'='*60}")
print("All tests completed!")
