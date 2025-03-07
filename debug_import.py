import os
import sys
import glob

print("Current Working Directory:", os.getcwd())
print("\nPython sys.path:")
for p in sys.path:
    print("  ", p)

# List files in the 'wsocket' directory
wsocket_path = os.path.join(os.getcwd(), "wsocket")
print("\nContents of the 'wsocket' directory:")
if os.path.isdir(wsocket_path):
    for filename in os.listdir(wsocket_path):
        print("  ", filename)
else:
    print("  'wsocket' directory not found.")

# Check if __init__.py exists in wsocket directory
init_path = os.path.join(wsocket_path, "__init__.py")
if os.path.isfile(init_path):
    print("\nFound __init__.py in wsocket directory.")
else:
    print("\nWARNING: __init__.py not found in wsocket directory!")

# Attempt an absolute import
try:
    # Try importing the wsocket_handlers module as if wsocket is a package.
    from wsocket import wsocket_handlers
    print("\nSuccessfully imported 'wsocket_handlers' from 'wsocket' package!")
except Exception as e:
    print("\nError importing 'wsocket_handlers':", e)
