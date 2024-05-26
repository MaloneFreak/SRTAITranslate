import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from transformers import MarianMTModel, MarianTokenizer
import srt
import os
from huggingface_hub import login, HfApi

token = ""  # Substitua pelo seu token
login(token)

def get_translator(src_lang, tgt_lang):
    try:
        api = HfApi()
        models = api.list_models(author="Helsinki-NLP")
        model_name = None

        search_patterns = [
            f"opus-mt-{src_lang}-{tgt_lang}",
            f"opus-mt-{src_lang[:2]}-{tgt_lang[:2]}",
            f"opus-mt-tc-big-{src_lang}-{tgt_lang}",
            f"opus-mt-tc-big-{src_lang[:2]}-{tgt_lang[:2]}",
            f"opus-mt-tc-{src_lang}-{tgt_lang}",
            f"opus-mt-tc-{src_lang[:2]}-{tgt_lang[:2]}"
        ]

        for model in models:
            for pattern in search_patterns:
                if pattern in model.modelId:
                    model_name = model.modelId
                    break
            if model_name:
                break

        if not model_name:
            messagebox.showerror("Erro", f"Modelo para a tradução de {src_lang} para {tgt_lang} não encontrado.")
            return None, None

        tokenizer = MarianTokenizer.from_pretrained(model_name)
        model = MarianMTModel.from_pretrained(model_name)
        return lambda text: model.generate(**tokenizer(text, return_tensors="pt", padding=True)), tokenizer
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao carregar o modelo: {e}")
        return None, None
    
def translate_text(text, translator, tokenizer):
    try:
        translated = translator(text)
        result = tokenizer.decode(translated[0], skip_special_tokens=True)
        return result
    except Exception as e:
        messagebox.showerror("Erro", f"Erro na tradução: {e}")
        return text

def translate_srt(input_file, src_lang, tgt_lang, progress_callback):
    translator, tokenizer = get_translator(src_lang, tgt_lang)
    if translator is None or tokenizer is None:
        return None
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            subs = list(srt.parse(f.read()))
        
        total_subs = len(subs)
        for i, sub in enumerate(subs):
            sub.content = translate_text(sub.content, translator, tokenizer)
            progress_callback(i + 1, total_subs)
        
        output_file = os.path.join(os.path.expanduser('~'), 'Downloads', f"translated_{os.path.basename(input_file)}")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(srt.compose(subs))
        return output_file
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao processar o arquivo SRT: {e}")
        return None

def upload_file():
    file_path = filedialog.askopenfilename(filetypes=[("SRT files", "*.srt")])
    if file_path:
        file_label.config(text=os.path.basename(file_path))
        file_label.file_path = file_path

def start_translation():
    if not hasattr(file_label, 'file_path'):
        messagebox.showerror("Erro", "Por favor, selecione um arquivo SRT.")
        return

    src_language = src_language_entry.get()
    tgt_language = tgt_language_entry.get()
    if not src_language or not tgt_language:
        messagebox.showerror("Erro", "Por favor, insira os idiomas de origem e destino.")
        return

    progress_bar['value'] = 0
    progress_bar.update()

    try:
        output_file = translate_srt(file_label.file_path, src_language, tgt_language, update_progress)
        if output_file:
            messagebox.showinfo("Sucesso", f"Arquivo traduzido salvo em: {output_file}")
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao traduzir o arquivo: {e}")

def update_progress(current, total):
    progress = (current / total) * 100
    progress_bar['value'] = progress
    progress_bar.update()

root = tk.Tk()
root.title("Tradutor de Arquivos SRT")
root.geometry("400x300")

upload_button = tk.Button(root, text="Upload", command=upload_file)
upload_button.pack(pady=10)

file_label = tk.Label(root, text="Nenhum arquivo selecionado")
file_label.pack(pady=5)

src_language_label = tk.Label(root, text="Idioma de Origem (ex: en)")
src_language_label.pack(pady=5)

src_language_entry = tk.Entry(root)
src_language_entry.pack(pady=5)

tgt_language_label = tk.Label(root, text="Idioma de Destino (ex: pt)")
tgt_language_label.pack(pady=5)

tgt_language_entry = tk.Entry(root)
tgt_language_entry.pack(pady=5)

translate_button = tk.Button(root, text="Traduzir", command=start_translation)
translate_button.pack(pady=20)

progress_bar = ttk.Progressbar(root, orient="horizontal", length=300, mode="determinate")
progress_bar.pack(pady=10)

root.mainloop()