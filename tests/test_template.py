import sys
from pathlib import Path
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

sys.path.insert(0, 'C:\\SS')
templates = Jinja2Templates(directory='C:\\SS\\ui_client\\templates')

try:
    # We need a mock request for FastAPI's Jinja2Templates
    scope = {'type': 'http', 'method': 'GET'}
    request = Request(scope)
    template = templates.get_template('index.html')
    print("Template loaded OK")
    print(template.render({'request': request}))
except Exception as e:
    import traceback
    traceback.print_exc()
