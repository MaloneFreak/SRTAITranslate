# SRT AI Translator

SRT AI Translator is an automatic subtitle translation tool that leverages the advanced translation model from Hugging Face (facebook/nllb-200-3.3B). This tool enables efficient and easy translation of subtitles from movies and videos into various languages.

## Requirements

Before using SRT AI Translator, ensure that you meet the following requirements:

- **Python 3.12** or higher
- **Python Libraries**:
  - `transformers`
  - `torch`
  - `torchvision`
  - `torchaudio`
  - `srt`
  - `huggingface_hub`
  - `keyring`
  - `tkinter` (usually included with Python)
- **Translation Model**: The "facebook/nllb-200-3.3B" model from Hugging Face will be downloaded automatically.
- **CUDA**: For NVIDIA GPUs (optional, recommended for faster translation).
- **Hugging Face API Token**: To access the translation model on Hugging Face.

## Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/YourUsername/SRTAITranslator.git
   cd SRTAITranslator
   ```

2. **Install Dependencies**
   Run the installation script to install all required dependencies:
   ```bash
   python Module Installation.py
   ```
   This script will install PyTorch and other necessary libraries.

3. **Obtain a Hugging Face Token**
   - Visit [Hugging Face](https://huggingface.co/) and create an account if you don't have one.
   - Go to the access tokens section and generate a new token.

## Usage

1. **Start the Application**
   Run the main script to launch the graphical user interface (GUI):
   ```bash
   python SRTAI_Translator.py
   ```

2. **Upload the SRT File**
   Click the "Upload SRT File" button and select the SRT file you want to translate.

3. **Enter Required Information**
   - **Source Language**: Enter the source language code (e.g., `eng_Latn`).
   - **Target Language**: Enter the target language code (e.g., `por_Latn`).
   - **Hugging Face API Token**: Enter your Hugging Face token.

4. **Translate the File**
   Click the "Start Translation" button and wait while the software translates the SRT file content. Progress will be shown on the progress bar.

5. **Retrieve the Translated File**
   The translated file will be saved in the `Downloads` folder with the prefix `translated_`.

## Known Issues

- **CUDA Compatibility**: Ensure that you have the correct CUDA version installed for your GPU. The installer script uses CUDA 12.4 by default.
- **Installation Errors**: If you encounter issues during installation, try running the `Module Installation.py` script with administrator privileges or in a virtual environment.

## Contributing

If you wish to contribute to the development of SRT AI Translator, feel free to open issues, submit pull requests, or provide feedback.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact

- **Author**: [Pedro Giácomo]
- **GitHub**: [https://github.com/MaloneFreak]
- **Email**: [malonefreak@yandex.ru]

---

Thank you for using SRT AI Translator!
