import sys
from google.adk.sessions import InvocationContext
print(InvocationContext.model_fields['user_content'])
