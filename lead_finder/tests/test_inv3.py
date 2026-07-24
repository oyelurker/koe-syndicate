import sys
import importlib
import pkgutil
import google.adk

def find_class():
    for importer, modname, ispkg in pkgutil.walk_packages(path=google.adk.__path__, prefix=google.adk.__name__+'.'):
        try:
            module = importlib.import_module(modname)
            for attr in dir(module):
                if attr == 'InvocationContext':
                    print(f"Found in {modname}")
        except Exception:
            pass

find_class()
