#!/usr/bin/env python3
"""Rebuild the webhook handler ZIP file with updated code"""
import os
import shutil
import subprocess
import zipfile
import tempfile

def main():
    # Get directories
    script_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(script_dir, 'src')
    terraform_zips_dir = os.path.join(script_dir, '..', 'terraform-zips')
    
    # Create temp directory
    temp_dir = tempfile.mkdtemp()
    print(f"📦 Creating ZIP in temp directory: {temp_dir}")
    
    try:
        # Copy source files
        shutil.copy(os.path.join(src_dir, 'webhook_handler.py'), temp_dir)
        shutil.copy(os.path.join(src_dir, 'requirements.txt'), temp_dir)
        
        # Install dependencies
        print("📥 Installing dependencies...")
        subprocess.run(
            ['python3', '-m', 'pip', 'install', '-r', os.path.join(temp_dir, 'requirements.txt'), '-t', temp_dir],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Create ZIP
        zip_path = os.path.join(temp_dir, 'webhook-handler.zip')
        print(f"📦 Creating ZIP file...")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file == 'webhook-handler.zip':
                        continue
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zf.write(file_path, arcname)
        
        # Copy to terraform-zips directory
        os.makedirs(terraform_zips_dir, exist_ok=True)
        target_path = os.path.join(terraform_zips_dir, 'webhook-handler.zip')
        shutil.copy(zip_path, target_path)
        
        # Verify ZIP was created and contains main file
        print(f"✅ ZIP created: {target_path}")
        with zipfile.ZipFile(target_path, 'r') as zf:
            if 'webhook_handler.py' not in zf.namelist():
                print("❌ webhook_handler.py not found in ZIP")
                return 1
            size = os.path.getsize(target_path) / (1024 * 1024)
            print(f"📦 ZIP size: {size:.1f} MB")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == '__main__':
    exit(main())




