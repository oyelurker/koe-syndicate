import os
import re

TARGET_DIR = "."

def replace_in_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Skipping {filepath}: {e}")
        return

    original_content = content

    # Standard replacements
    content = content.replace("Koe Syndicate", "Koe Syndicate")
    content = content.replace("koe_syndicate", "koe_syndicate")
    content = content.replace("Koe Syndicate", "Koe Syndicate")
    content = content.replace("koesyndicate", "koesyndicate")

    # deploy_local.sh / deploy_local.ps1 startup banner replacement
    # Using regex to find the banners
    content = re.sub(r'KOE SYNDICATE: SYSTEM ONLINE', 'KOE SYNDICATE: SYSTEM ONLINE', content)
    content = re.sub(r'Koe Syndicate -- Local Deploy Script', 'Koe Syndicate -- Local Deploy Script', content)

    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {filepath}")

def main():
    extensions = {'.py', '.html', '.md', '.sh', '.ps1', '.txt', '.yaml', '.toml', '.example'}
    for root, dirs, files in os.walk(TARGET_DIR):
        if 'venv' in root or '.git' in root or '__pycache__' in root:
            continue
        for file in files:
            # Check env files or specific extensions
            if file.startswith('.env') or any(file.endswith(ext) for ext in extensions):
                filepath = os.path.join(root, file)
                replace_in_file(filepath)

if __name__ == "__main__":
    main()
