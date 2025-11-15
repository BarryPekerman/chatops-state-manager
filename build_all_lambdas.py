#!/usr/bin/env python3
"""Build all Lambda ZIP packages"""
import os
import shutil
import subprocess
import sys
import zipfile
import tempfile

def build_lambda(name, src_dir, output_file, requirements_file=None):
    """Build a Lambda ZIP package"""
    print(f"\n{'='*60}")
    print(f"🔨 Building {name} Lambda...")
    print(f"{'='*60}")

    # Get project root (directory where this script is located)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    lambda_dir = os.path.join(base_dir, 'lambda', src_dir)
    src_path = os.path.join(lambda_dir, 'src')
    terraform_zips_dir = os.path.join(base_dir, 'terraform-zips')

    if not os.path.exists(src_path):
        print(f"❌ Source directory not found: {src_path}")
        return False

    # Create temp directory
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        print(f"📁 Using temporary directory: {temp_dir}")
        # Copy source files
        print("📋 Copying source files...")
        for item in os.listdir(src_path):
            src_item = os.path.join(src_path, item)
            if os.path.isfile(src_item) and item.endswith('.py'):
                shutil.copy(src_item, temp_dir)

        # Find requirements.txt
        req_file = os.path.join(src_path, 'requirements.txt')
        if os.path.exists(req_file):
            shutil.copy(req_file, temp_dir)
            requirements_path = os.path.join(temp_dir, 'requirements.txt')
        elif requirements_file:
            requirements_path = os.path.join(lambda_dir, requirements_file)
        else:
            requirements_path = None

        # Install dependencies
        if requirements_path and os.path.exists(requirements_path):
            print("📥 Installing dependencies...")
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '-r', requirements_path, '-t', temp_dir],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"⚠️  Warning during pip install: {result.stderr[:200]}")

        # Create ZIP
        zip_path = os.path.join(temp_dir, f'{name}.zip')
        print(f"📦 Creating ZIP package...")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(temp_dir):
                # Skip __pycache__ and .pyc files
                dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git']]
                for file in files:
                    if file.endswith('.pyc') or file == f'{name}.zip':
                        continue
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zf.write(file_path, arcname)

        # Copy to terraform-zips directory
        os.makedirs(terraform_zips_dir, exist_ok=True)
        target_path = os.path.join(terraform_zips_dir, output_file)
        shutil.copy(zip_path, target_path)

        # Verify
        size = os.path.getsize(target_path) / (1024 * 1024)
        print(f"✅ {name} Lambda ZIP created: {target_path}")
        print(f"📦 ZIP size: {size:.1f} MB")

        # Verify Python files are in ZIP
        with zipfile.ZipFile(target_path, 'r') as zf:
            py_files = [f for f in zf.namelist() if f.endswith('.py')]
            if py_files:
                print(f"✅ ZIP contains {len(py_files)} Python file(s)")
                return True
            else:
                print(f"❌ ZIP missing Python files")
                return False

    except Exception as e:
        import traceback
        print(f"❌ Error building {name}: {e}")
        traceback.print_exc()
        return False
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)

def main():
    """Build all Lambda functions"""
    lambdas = [
        {
            'name': 'webhook-handler',
            'src_dir': 'webhook-handler',
            'output_file': 'webhook-handler.zip',
        },
        {
            'name': 'telegram-bot',
            'src_dir': 'telegram-bot',
            'output_file': 'telegram-bot.zip',
        },
        {
            'name': 'ai-output-processor',
            'src_dir': 'ai-output-processor',
            'output_file': 'ai-output-processor.zip',
        },
    ]

    results = []
    for lambda_config in lambdas:
        success = build_lambda(**lambda_config)
        results.append((lambda_config['name'], success))

    print(f"\n{'='*60}")
    print("📊 Build Summary")
    print(f"{'='*60}")
    for name, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {name}")

    all_success = all(success for _, success in results)
    return 0 if all_success else 1

if __name__ == '__main__':
    sys.exit(main())
