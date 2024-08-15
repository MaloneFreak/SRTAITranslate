import subprocess
import sys
import os

def install_requirements():
    requirements = [
        ("torch", "torchvision", "torchaudio"),
        "transformers",
        "accelerate",  
        "srt",
        "huggingface_hub",
        "keyring",
    ]

    python = sys.executable
    pip = [python, "-m", "pip"]

    print("Installing requirements for SRT Translator...")

    print("Upgrading pip...")
    try:
        subprocess.check_call(pip + ["install", "--upgrade", "pip"])
    except subprocess.CalledProcessError:
        print("Failed to upgrade pip. Continuing with installation...")

    print("Installing PyTorch...")
    try:
        subprocess.check_call(pip + ["install", "--pre", "torch", "torchvision", "torchaudio", "--index-url",
                                     "https://download.pytorch.org/whl/nightly/cu124"])
    except subprocess.CalledProcessError:
        print("Failed to install PyTorch. Please install it manually.")
        return False

    for req in requirements[1:]:  # Skip PyTorch as we've already installed it
        print(f"Installing {req}...")
        try:
            subprocess.check_call(pip + ["install"] + (req.split() if isinstance(req, str) else req))
        except subprocess.CalledProcessError:
            print(f"Failed to install {req}. Please install it manually.")
            return False

    print("All requirements installed successfully!")
    return True

if __name__ == "__main__":
    if install_requirements():
        print("Installation complete. You can now run the SRT Translator application.")
    else:
        print("Installation failed. Please check the error messages above and try again.")

    input("Press Enter to exit...")
