import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
import srt
import os
from huggingface_hub import login, HfApi, cached_download
import logging
import keyring
import re
from threading import Thread

logging.basicConfig(level=logging.INFO, filename='srt_translator.log', filemode='w')

translation_cancelled = False

class TokenInvalidoError(Exception):
    pass

class ErroDeTraducao(Exception):
    pass

def clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)
    return text

def save_token(token):
    keyring.set_password('huggingface', 'user', token)

def load_token():
    return keyring.get_password('huggingface', 'user')

def validate_token(token):
    api = HfApi()
    try:
        api.whoami(token)
        return True
    except Exception:
        return False

def get_translator(src_lang, tgt_lang):
    try:
        model_name = "facebook/nllb-200-3.3B"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSeq2SeqLM.from_pretrained(model_name)

        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        model.to(device)

        def translator(texts):
            try:
                texts = [clean_text(text) for text in texts]
                tokenizer.src_lang = src_lang
                encoded_texts = tokenizer(texts, return_tensors="pt", padding=True, truncation=True, max_length=512)
                if device != 'cpu':
                    encoded_texts = {k: v.to(device) for k, v in encoded_texts.items()}
                generated_tokens = model.generate(
                    **encoded_texts,
                    forced_bos_token_id=tokenizer.convert_tokens_to_ids(tgt_lang),
                    max_length=512,
                    num_beams=4,
                    no_repeat_ngram_size=2
                )
                return generated_tokens
            except Exception as e:
                logging.error("Error generating tokens: ", exc_info=True)
                return None

        return translator, tokenizer, model, device
    except Exception as e:
        logging.error("Error loading the model: ", exc_info=True)
        return None, None, None, None

def translate_texts(texts, translator, tokenizer, device):
    try:
        logging.info(f"Translating batch of size {len(texts)}")
        translated = translator(texts)
        if translated is None:
            raise ErroDeTraducao("Translation failed")
        result = tokenizer.batch_decode(translated, skip_special_tokens=True)
        return result
    except Exception as e:
        logging.error("Error in translation: ", exc_info=True)
        return texts

def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def translate_srt(input_file, src_lang, tgt_lang, progress_callback):
    global translation_cancelled
    translation_cancelled = False
    translator, tokenizer, model, device = get_translator(src_lang, tgt_lang)
    if translator is None or tokenizer is None or model is None or device is None:
        return None

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            subs = list(srt.parse(f.read()))

        total_subs = len(subs)
        batch_size = 5
        translated_subs = []

        for i, batch in enumerate(chunks(subs, batch_size)):
            if translation_cancelled:
                logging.info("Translation cancelled")
                return None
            texts = [sub.content for sub in batch]
            translated_texts = translate_texts(texts, translator, tokenizer, device)
            for sub, translated_text in zip(batch, translated_texts):
                sub.content = translated_text
                translated_subs.append(sub)
            progress_callback((i + 1) * batch_size, total_subs)
            logging.info(f"Processed batch {i + 1}/{(total_subs + batch_size - 1) // batch_size}")

        output_file = os.path.join(os.path.expanduser('~'), 'Downloads', f"translated_{os.path.basename(input_file)}")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(srt.compose(translated_subs))
        return output_file
    except Exception as e:
        logging.error("Error processing SRT file: ", exc_info=True)
        return None

def upload_file():
    file_path = filedialog.askopenfilename(filetypes=[("SRT files", "*.srt")])
    if file_path:
        file_label.config(text=os.path.basename(file_path))
        file_label.file_path = file_path

def process_translation():
    if not hasattr(file_label, 'file_path'):
        messagebox.showerror("Error", "Please select an SRT file.")
        return

    src_language = src_language_entry.get()
    tgt_language = tgt_language_entry.get()
    token = token_entry.get()
    if not src_language or not tgt_language:
        messagebox.showerror("Error", "Please enter source and target languages.")
        return

    if not token:
        messagebox.showerror("Error", "Please enter the Hugging Face API token.")
        return

    if not validate_token(token):
        raise TokenInvalidoError("Invalid or expired token")

    save_token(token)
    login(token)

    progress_bar['value'] = 0
    progress_bar.update()

    def run_translation():
        try:
            output_file = translate_srt(file_label.file_path, src_language, tgt_language, update_progress)
            if output_file:
                root.after(0, lambda: messagebox.showinfo("Success", f"Translated file saved at: {output_file}"))
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Error", f"Error translating the file: {e}"))

    thread = Thread(target=run_translation)
    thread.start()

def start_translation():
    process_translation()

def update_progress(current, total):
    progress_bar['value'] = (current / total) * 100
    root.update_idletasks()

def cancel_translation():
    global translation_cancelled
    translation_cancelled = True

def toggle_token_visibility():
    if token_entry.cget('show') == '*':
        token_entry.config(show='')
        show_hide_button.config(text='Hide')
    else:
        token_entry.config(show='*')
        show_hide_button.config(text='Show')

if __name__ == "__main__":
    root = tk.Tk()
    root.title("SRT AI Translator")
    root.geometry("500x450")
    root.configure(bg="#f0f0f0")

    style = ttk.Style()
    style.configure('TButton',
                    font=('Arial', 10),
                    padding=6,
                    relief='flat',
                    background="#ffffff",
                    foreground="#000000")
    style.configure('TLabel',
                    font=('Arial', 10),
                    background="#f0f0f0")
    style.configure('TProgressbar', thickness=20)
    style.map('TButton',
              background=[('active', '#f0f0f0')],
              foreground=[('active', '#000000')])

    root.grid_rowconfigure(0, weight=0)
    root.grid_rowconfigure(1, weight=0)
    root.grid_rowconfigure(2, weight=0)
    root.grid_rowconfigure(3, weight=0)
    root.grid_rowconfigure(4, weight=0)
    root.grid_rowconfigure(5, weight=0)
    root.grid_rowconfigure(6, weight=0)
    root.grid_rowconfigure(7, weight=1)
    root.grid_columnconfigure(0, weight=0)
    root.grid_columnconfigure(1, weight=1)
    root.grid_columnconfigure(2, weight=0)

    upload_button = ttk.Button(root, text="Upload SRT File", command=upload_file)
    upload_button.grid(row=0, column=0, columnspan=3, padx=10, pady=10, sticky="ew")

    file_label = ttk.Label(root, text="No file selected")
    file_label.grid(row=1, column=0, columnspan=3, padx=10, pady=10, sticky="ew")

    src_language_label = ttk.Label(root, text="Source Language (e.g.,eng_Latn):")
    src_language_label.grid(row=2, column=0, padx=10, pady=10, sticky="w")

    src_language_entry = ttk.Entry(root)
    src_language_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")

    tgt_language_label = ttk.Label(root, text="Target Language (e.g.,por_Latn):")
    tgt_language_label.grid(row=3, column=0, padx=10, pady=10, sticky="w")

    tgt_language_entry = ttk.Entry(root)
    tgt_language_entry.grid(row=3, column=1, padx=10, pady=10, sticky="ew")

    token_label = ttk.Label(root, text="Hugging Face Token:")
    token_label.grid(row=4, column=0, padx=10, pady=10, sticky="w")

    token_entry = ttk.Entry(root, show="*")
    token_entry.grid(row=4, column=1, padx=10, pady=10, sticky="ew")

    show_hide_button = ttk.Button(root, text="Show", command=toggle_token_visibility)
    show_hide_button.grid(row=4, column=2, padx=10, pady=10)

    translate_button = ttk.Button(root, text="Translate", command=start_translation)
    translate_button.grid(row=5, column=0, columnspan=3, padx=10, pady=10, sticky="ew")

    cancel_button = ttk.Button(root, text="Cancel", command=cancel_translation)
    cancel_button.grid(row=6, column=0, columnspan=3, padx=10, pady=10, sticky="ew")

    progress_bar = ttk.Progressbar(root, mode='determinate')
    progress_bar.grid(row=7, column=0, columnspan=3, padx=10, pady=10, sticky="ew")

    root.mainloop()