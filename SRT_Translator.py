import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import srt
import os
from huggingface_hub import login
import configparser
from threading import Thread
import torch
import logging

logging.basicConfig(level=logging.INFO)

config_file = os.path.join(os.path.expanduser('~'), 'srt_translator_config.ini')

def load_token():
    config = configparser.ConfigParser()
    if os.path.exists(config_file):
        config.read(config_file)
        if 'HuggingFace' in config and 'token' in config['HuggingFace']:
            return config['HuggingFace']['token']
    return ''

def save_token(token):
    config = configparser.ConfigParser()
    config['HuggingFace'] = {'token': token}
    with open(config_file, 'w') as configfile:
        config.write(configfile)

def get_translator(src_lang, tgt_lang):
    try:
        model_name = "facebook/nllb-200-3.3B"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSeq2SeqLM.from_pretrained(model_name)

        device = 'cpu'
        if torch.cuda.is_available():
            device = 'cuda'
        elif torch.backends.mps.is_available():
            device = 'mps'
        elif torch.backends.rocm.is_available():
            device = 'rocm'
        else:
            device = 'cpu'
        model.to(device) 

        def translator(texts):
            try:
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
                messagebox.showerror("Error", f"Error generating tokens: {e}")
                return None
        
        return translator, tokenizer, model, device
    except Exception as e:
        messagebox.showerror("Error", f"Error loading the model: {e}")
        return None, None, None, None

def translate_texts(texts, translator, tokenizer, device):
    try:
        logging.info(f"Translating batch of size {len(texts)}")
        translated = translator(texts)
        if translated is None:
            raise Exception("Translation failed")
        result = tokenizer.batch_decode(translated, skip_special_tokens=True)
        return result
    except Exception as e:
        messagebox.showerror("Error", f"Error in translation: {e}")
        return texts

def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def translate_srt(input_file, src_lang, tgt_lang, progress_callback):
    translator, tokenizer, model, device = get_translator(src_lang, tgt_lang)
    if translator is None or tokenizer is None or model is None or device is None:
        return None
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            subs = list(srt.parse(f.read()))
        
        total_subs = len(subs)
        batch_size = 10  
        translated_subs = []

        for i, batch in enumerate(chunks(subs, batch_size)):
            texts = [sub.content for sub in batch]
            translated_texts = translate_texts(texts, translator, tokenizer, device)
            for sub, translated_text in zip(batch, translated_texts):
                sub.content = translated_text
                translated_subs.append(sub)
            progress_callback((i + 1) * batch_size, total_subs)
            logging.info(f"Processed batch {i+1}/{(total_subs + batch_size - 1) // batch_size}")
        
        output_file = os.path.join(os.path.expanduser('~'), 'Downloads', f"translated_{os.path.basename(input_file)}")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(srt.compose(translated_subs))
        return output_file
    except Exception as e:
        messagebox.showerror("Error", f"Error processing SRT file: {e}")
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
    thread = Thread(target=process_translation)
    thread.start()

def update_progress(current, total):
    progress = (current / total) * 100
    root.after(0, lambda: progress_bar.configure(value=progress))
    root.after(0, progress_bar.update)

root = tk.Tk()
root.title("SRT AI Translator")
root.geometry("400x400")

upload_button = tk.Button(root, text="Upload", command=upload_file)
upload_button.pack(pady=10)

file_label = tk.Label(root, text="No file selected")
file_label.pack(pady=5)

src_language_label = tk.Label(root, text="Source Language (eng_Latn)")
src_language_label.pack(pady=5)

src_language_entry = tk.Entry(root)
src_language_entry.pack(pady=5)

tgt_language_label = tk.Label(root, text="Target Language (por_Latn)")
tgt_language_label.pack(pady=5)

tgt_language_entry = tk.Entry(root)
tgt_language_entry.pack(pady=5)

token_label = tk.Label(root, text="Hugging Face API Token")
token_label.pack(pady=5)

token_entry = tk.Entry(root, show="*")
token_entry.pack(pady=5)

saved_token = load_token()
if saved_token:
    token_entry.insert(0, saved_token)

translate_button = tk.Button(root, text="Translate", command=start_translation)
translate_button.pack(pady=10)

progress_bar = ttk.Progressbar(root, orient="horizontal", length=300, mode="determinate")
progress_bar.pack(pady=20)

root.mainloop()