import sys
from google.adk.agents.invocation_context import InvocationContext
print(InvocationContext.model_fields['user_content'].annotation)
print(InvocationContext.model_fields['user_content'].default)
