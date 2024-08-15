import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
import torch
import srt
import os
from huggingface_hub import login
import logging
import json
from threading import Thread

logging.basicConfig(level=logging.INFO, filename='srt_translator.log', filemode='w')


class SRTTranslatorApp:
    def __init__(self, master):
        self.master = master
        self.translation_cancelled = False
        self.translation_thread = None

        master.title("SRT AI Translator")
        master.geometry("500x500")
        master.configure(bg="#f0f0f0")

        self.style = ttk.Style()
        self.style.configure('TButton', font=('Arial', 10), padding=6, relief='flat', background="#ffffff",
                             foreground="#000000")
        self.style.configure('TLabel', font=('Arial', 10), background="#f0f0f0")
        self.style.configure('TProgressbar', thickness=20)
        self.style.map('TButton', background=[('active', '#f0f0f0')], foreground=[('active', '#000000')])

        self.create_widgets()
        self.load_saved_settings()

    def create_widgets(self):
        self.upload_button = ttk.Button(self.master, text="Upload SRT File", command=self.upload_file)
        self.upload_button.grid(row=0, column=0, columnspan=3, padx=10, pady=10, sticky="ew")

        self.file_label = ttk.Label(self.master, text="No file selected")
        self.file_label.grid(row=1, column=0, columnspan=3, padx=10, pady=10, sticky="ew")

        self.src_language_label = ttk.Label(self.master, text="Source Language (e.g., eng_Latn):")
        self.src_language_label.grid(row=2, column=0, padx=10, pady=10, sticky="w")

        self.src_language_entry = ttk.Entry(self.master)
        self.src_language_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")

        self.tgt_language_label = ttk.Label(self.master, text="Target Language (e.g., por_Latn):")
        self.tgt_language_label.grid(row=3, column=0, padx=10, pady=10, sticky="w")

        self.tgt_language_entry = ttk.Entry(self.master)
        self.tgt_language_entry.grid(row=3, column=1, padx=10, pady=10, sticky="ew")

        self.token_label = ttk.Label(self.master, text="Hugging Face Token:")
        self.token_label.grid(row=4, column=0, padx=10, pady=10, sticky="w")

        self.token_entry = ttk.Entry(self.master, show="*")
        self.token_entry.grid(row=4, column=1, padx=10, pady=10, sticky="ew")

        self.show_hide_button = ttk.Button(self.master, text="Show", command=self.toggle_token_visibility)
        self.show_hide_button.grid(row=4, column=2, padx=10, pady=10)

        self.translate_button = ttk.Button(self.master, text="Translate", command=self.start_translation)
        self.translate_button.grid(row=5, column=0, columnspan=3, padx=10, pady=10, sticky="ew")

        self.cancel_button = ttk.Button(self.master, text="Cancel", command=self.cancel_translation, state=tk.DISABLED)
        self.cancel_button.grid(row=6, column=0, columnspan=3, padx=10, pady=10, sticky="ew")

        self.progress_bar = ttk.Progressbar(self.master, mode='determinate')
        self.progress_bar.grid(row=7, column=0, columnspan=3, padx=10, pady=10, sticky="ew")

        self.status_label = ttk.Label(self.master, text="")
        self.status_label.grid(row=8, column=0, columnspan=3, padx=10, pady=10, sticky="ew")

    def load_saved_settings(self):
        settings = self.load_settings()
        if settings:
            self.src_language_entry.insert(0, settings.get('src_lang', ''))
            self.tgt_language_entry.insert(0, settings.get('tgt_lang', ''))
            self.token_entry.insert(0, settings.get('token', ''))

    def upload_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("SRT files", "*.srt")])
        if file_path:
            self.file_label.config(text=os.path.basename(file_path))
            self.file_label.file_path = file_path

    def toggle_token_visibility(self):
        if self.token_entry.cget('show') == '*':
            self.token_entry.config(show='')
            self.show_hide_button.config(text='Hide')
        else:
            self.token_entry.config(show='*')
            self.show_hide_button.config(text='Show')

    def start_translation(self):
        if not hasattr(self.file_label, 'file_path'):
            messagebox.showerror("Error", "Please select an SRT file.")
            return

        src_language = self.src_language_entry.get()
        tgt_language = self.tgt_language_entry.get()
        token = self.token_entry.get()
        if not src_language or not tgt_language:
            messagebox.showerror("Error", "Please enter source and target languages.")
            return

        if not token:
            messagebox.showerror("Error", "Please enter the Hugging Face API token.")
            return

        if not self.validate_token(token):
            messagebox.showerror("Error", "Invalid token")
            return

        self.save_settings(src_language, tgt_language, token)
        login(token)

        self.progress_bar['value'] = 0
        self.progress_bar.update()
        self.translate_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        self.status_label.config(text="Translation in progress...")

        self.translation_cancelled = False
        self.translation_thread = Thread(target=self.run_translation, args=(src_language, tgt_language))
        self.translation_thread.start()

    def run_translation(self, src_language, tgt_language):
        try:
            output_file = self.translate_srt(self.file_label.file_path, src_language, tgt_language,
                                             self.update_progress)
            if output_file:
                self.master.after(0, lambda: messagebox.showinfo("Success", f"Translated file saved at: {output_file}"))
                self.master.after(0, lambda: self.status_label.config(text="Translation completed successfully."))
            else:
                self.master.after(0, lambda: self.status_label.config(text="Translation cancelled or failed."))
        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("Error", f"Error translating the file: {str(e)}"))
            self.master.after(0, lambda: self.status_label.config(text="Translation failed."))
        finally:
            self.master.after(0, self.reset_ui)

    def update_progress(self, current, total):
        progress = (current / total) * 100
        self.master.after(0, lambda: self.progress_bar.config(value=progress))
        self.master.after(0, lambda: self.status_label.config(text=f"Translating... {progress:.1f}% complete"))

    def cancel_translation(self):
        self.translation_cancelled = True
        self.status_label.config(text="Cancelling translation...")

    def reset_ui(self):
        self.translate_button.config(state=tk.NORMAL)
        self.cancel_button.config(state=tk.DISABLED)

    def save_settings(self, src_lang, tgt_lang, token):
        settings = {
            'src_lang': src_lang,
            'tgt_lang': tgt_lang,
            'token': token
        }
        with open('settings.json', 'w') as f:
            json.dump(settings, f)

    def load_settings(self):
        try:
            with open('settings.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def validate_token(self, token):
        return bool(token.strip())

    def get_translator(self, src_lang, tgt_lang):
        try:
            model_name = "facebook/nllb-200-3.3B"
            tokenizer = AutoTokenizer.from_pretrained(model_name, src_lang=src_lang)

            model = AutoModelForSeq2SeqLM.from_pretrained(
                model_name,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto",
                low_cpu_mem_usage=True
            )

            translator = pipeline(
                "translation",
                model=model,
                tokenizer=tokenizer,
                batch_size=8
            )

            return translator, src_lang, tgt_lang
        except Exception as e:
            logging.error("Error loading the model: ", exc_info=True)
            raise

    def translate_texts(self, texts, translator, src_lang, tgt_lang):
        try:
            logging.info(f"Translating batch of size {len(texts)}")
            translated = translator(texts, src_lang=src_lang, tgt_lang=tgt_lang, max_length=200)
            return [t['translation_text'] for t in translated]
        except Exception as e:
            logging.error("Error in translation: ", exc_info=True)
            raise

    def chunks(self, lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    def translate_srt(self, input_file, src_lang, tgt_lang, progress_callback):
        translator, src_lang, tgt_lang = self.get_translator(src_lang, tgt_lang)

        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                subs = list(srt.parse(f.read()))

            total_subs = len(subs)
            batch_size = 16
            translated_subs = []

            for i, batch in enumerate(self.chunks(subs, batch_size)):
                if self.translation_cancelled:
                    logging.info("Translation cancelled")
                    return None
                texts = [sub.content for sub in batch]
                translated_texts = self.translate_texts(texts, translator, src_lang, tgt_lang)
                for sub, translated_text in zip(batch, translated_texts):
                    sub.content = translated_text
                    translated_subs.append(sub)
                progress_callback(min((i + 1) * batch_size, total_subs), total_subs)
                logging.info(f"Processed batch {i + 1}/{(total_subs + batch_size - 1) // batch_size}")

            output_file = os.path.join(os.path.expanduser('~'), 'Downloads',
                                       f"translated_{os.path.basename(input_file)}")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(srt.compose(translated_subs))
            return output_file
        except Exception as e:
            logging.error("Error processing SRT file: ", exc_info=True)
            raise


if __name__ == "__main__":
    root = tk.Tk()
    app = SRTTranslatorApp(root)
    root.mainloop()
