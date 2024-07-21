# SRT AI Translator

SRT AI Translator is an automatic subtitle translation tool that uses advanced translation models from Hugging Face. This tool allows you to translate subtitles from movies and videos into different languages efficiently and with ease.

## Requirements

Before using SRT AI Translator, ensure that you meet the following requirements:

- **Python 3.12** or higher
- **Python Libraries**:
  - `transformers`
  - `torch`
  - `srt`
  - `huggingface_hub`
  - `tkinter` (usually included with Python)
- **Translation Model**: The "facebook/nllb-200-3.3B" model from Hugging Face will be downloaded automatically.
- **CUDA**: For NVIDIA GPUs (optional). ROCm support may depend on your hardware and installation.
- **Hugging Face API Token**: To access the translation model on Hugging Face.

## Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/MaloneFreak/SRTAITranslate.git
   cd SRTAITranslate
   ```

2. **Install Dependencies**

   It is recommended to use a virtual environment to manage dependencies.

   ```bash
   python -m venv env
   source env/bin/activate  # On Windows use `env\Scripts\activate`
   pip install -r requirements.txt
   ```

3. **Obtain a Hugging Face Token**

   - Visit [Hugging Face](https://huggingface.co/) and create an account if you don’t have one.
   - Go to the access tokens section and generate a new token.

4. **Configure the Hugging Face Token**

   Create a configuration file `srt_translator_config.ini` in your home directory (or use the application to input the token) and add the following content:

   ```ini
   [HuggingFace]
   token = YOUR_HUGGING_FACE_API_TOKEN
   ```

## Usage

1. **Start the Application**

   Run the main script to launch the graphical user interface (GUI):

   ```bash
   python SRT_Translator.py
   ```

2. **Upload the SRT File**

   Click the **"Upload"** button and select the SRT file you want to translate.

3. **Enter Required Information**

   - **Source Language**: Source language code (e.g., `eng_Latn`).
   - **Target Language**: Target language code (e.g., `por_Latn`).
   - **Hugging Face API Token**: Enter your Hugging Face token.

4. **Translate the File**

   Click the **"Translate"** button and wait while the software translates the SRT file content. Progress will be shown on the progress bar.

5. **Retrieve the Translated File**

   The translated file will be saved in the `Downloads` folder with the prefix `translated_`.

## Known Issues

- **CUDA and ROCm**: Ensure that drivers and libraries are correctly installed and configured. Compatibility may vary.

## Contributing

If you wish to contribute to the development of SRT AI Translator, feel free to open issues, submit pull requests, or provide feedback.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact

- **Author**: [MaloneFreak](https://github.com/MaloneFreak), [Kattiel](https://github.com/Kattiell)
- **Email**: [malonefreak@yandex.ru](mailto:malonefreak@yandex.ru), [gabrielcaetanopf.contato@gmail.com](mailto:gabrielcaetanopf.contato@gmail.com)

---

Thank you for using SRT AI Translator!
