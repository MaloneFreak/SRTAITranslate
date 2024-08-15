# SRT AI Translator

SRT AI Translator is an advanced automatic subtitle translation tool that leverages the powerful translation model from Hugging Face (facebook/nllb-200-3.3B). This application enables efficient and easy translation of subtitles from movies and videos into various languages, with an improved user interface and enhanced functionality.

## Features

- User-friendly graphical interface
- Support for multiple language pairs
- Batch translation of SRT files
- Progress tracking with a visual progress bar
- Secure token storage using keyring
- Improved error handling and input validation
- Option to cancel ongoing translations
- Token visibility toggle for enhanced security

## Requirements

Before using SRT AI Translator, ensure that you meet the following requirements:

- **Python 3.12** or higher
- **Python Libraries**:
  - `transformers`
  - `torch`
  - `srt`
  - `huggingface_hub`
  - `keyring`
  - `accelerate`
  - `tkinter` (usually included with Python)
- **Translation Model**: The "facebook/nllb-200-3.3B" model from Hugging Face will be downloaded automatically.
- **CUDA**: For NVIDIA GPUs (optional, recommended for faster translation).
- **Hugging Face API Token**: To access the translation model on Hugging Face.

## Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/MaloneFreak/SRTAITranslator.git
   cd SRTAITranslator
   ```

2. **Install Dependencies**
   Run the installation script to install all required dependencies:
   ```bash
   python Module Installation.py
   ```

3. **Obtain a Hugging Face Token**
   - Visit [Hugging Face](https://huggingface.co/) and create an account if you don't have one.
   - Go to the access tokens section and generate a new token.

## Usage

1. **Start the Application**
   Run the main script to launch the graphical user interface (GUI) or run the .EXE:
   ```bash
   python SRTAI_Translator.py
   ```

2. **Upload the SRT File**
   Click the "Upload SRT File" button and select the SRT file you want to translate.

3. **Enter Required Information**
   - **Source Language**: Enter the source language code (e.g., `eng_Latn`).
   - **Target Language**: Enter the target language code (e.g., `por_Latn`).
   - **Hugging Face API Token**: Enter your Hugging Face token. You can toggle visibility for security.

4. **Translate the File**
   Click the "Translate" button to start the translation process. The progress will be shown on the progress bar.

5. **Cancel Translation**
   If needed, you can cancel the ongoing translation process by clicking the "Cancel" button.

6. **Retrieve the Translated File**
   Upon successful translation, a message will appear with the location of the translated file. The translated file will be saved in the `Downloads` folder with the prefix `translated_`.

## Known Issues

- **CUDA Compatibility**: Ensure that you have the correct CUDA version installed for your GPU if you want to use GPU acceleration.
- **Large File Handling**: Very large SRT files may require significant processing time and memory.

## Contributing

If you wish to contribute to the development of SRT AI Translator, feel free to open issues, submit pull requests, or provide feedback. We welcome contributions to improve the tool's functionality and user experience.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact

- **Author**: [Pedro Giácomo]
- **GitHub**: [https://github.com/MaloneFreak]
- **Email**: [malonefreak@yandex.ru]

---

**Thank you for using SRT AI Translator! We hope this tool enhances your subtitle translation experience.**
