"""UI translations. Code uses English strings; this maps them to Portuguese (Brazil).

Add a language by adding another dict and an entry in LANGUAGES.
"""
from __future__ import annotations

import locale
import os

LANGUAGES = {"en": "English", "pt-BR": "Português (Brasil)"}

PT = {
    # top bar / navigation
    "Translate": "Traduzir",
    "Models": "Modelos",
    "Settings": "Configurações",
    "Update available: {version}": "Atualização disponível: {version}",
    # files
    "Files": "Arquivos",
    "Add files": "Adicionar arquivos",
    "Add folder": "Adicionar pasta",
    "Clear": "Limpar",
    "Drop .srt files here, or use the buttons below.": "Arraste arquivos .srt para cá ou use os botões abaixo.",
    "Ready": "Pronto",
    "Waiting": "Na fila",
    "Done": "Concluído",
    "Failed": "Falhou",
    "Cancelled": "Cancelado",
    "Remove": "Remover",
    "Subtitle files": "Arquivos de legenda",
    "All files": "Todos os arquivos",
    "{n} file": "{n} arquivo",
    "{n} files": "{n} arquivos",
    "Open folder": "Abrir pasta",
    # engine panel
    "Engine": "Motor de tradução",
    "Cloud API": "API na nuvem",
    "Local AI": "IA local",
    "Offline": "Offline",
    "Provider": "Provedor",
    "Model": "Modelo",
    "Refresh model list": "Atualizar lista de modelos",
    "API key": "Chave de API",
    "Save": "Salvar",
    "Saved": "Salva",
    "Get a key": "Obter uma chave",
    "Key saved in the system credential store.": "Chave salva no cofre de credenciais do sistema.",
    "Key saved in the app folder (no credential store available).":
        "Chave salva na pasta do app (cofre de credenciais indisponível).",
    "No key yet.": "Nenhuma chave ainda.",
    "Server URL": "URL do servidor",
    "From": "De",
    "To": "Para",
    "Swap languages": "Inverter idiomas",
    "Auto-detect": "Detectar automaticamente",
    "Search languages": "Buscar idioma",
    "More options": "Mais opções",
    "Notes about the video": "Observações sobre o vídeo",
    "Helps AI engines choose the right words. Example: sci-fi series, casual teenage characters.":
        "Ajuda as IAs a escolher as palavras certas. Ex.: série de ficção científica, personagens adolescentes.",
    "Glossary": "Glossário",
    "One per line. A name to keep: Winterfell. A fixed translation: King's Landing = Porto Real.":
        "Um por linha. Nome a manter: Winterfell. Tradução fixa: King's Landing = Porto Real.",
    "Formality": "Formalidade",
    "Default": "Padrão",
    "Formal": "Formal",
    "Informal": "Informal",
    "Characters per line": "Caracteres por linha",
    "Remove hearing-impaired notes ([music], NAME:)": "Remover notas para surdos ([música], NOME:)",
    "Bilingual subtitles (original below the translation)": "Legenda bilíngue (original abaixo da tradução)",
    "Join sentences split across subtitles (offline and DeepL)":
        "Juntar frases quebradas entre legendas (offline e DeepL)",
    "Reuse earlier translations (faster, cheaper)": "Reaproveitar traduções anteriores (mais rápido e barato)",
    "Save to": "Salvar em",
    "Same folder as the original": "Mesma pasta do original",
    "Browse": "Procurar",
    "File name": "Nome do arquivo",
    "Downloaded once, then works without internet.": "Baixado uma vez, depois funciona sem internet.",
    "Not downloaded yet. It downloads automatically when you translate, or in Models.":
        "Ainda não baixado. Ele baixa sozinho quando você traduzir, ou na aba Modelos.",
    "Installed": "Instalado",
    "Ollama isn't running.": "O Ollama não está rodando.",
    "Ollama {version} is running.": "Ollama {version} está rodando.",
    "Get Ollama": "Baixar Ollama",
    "LM Studio server not found at {url}.": "Servidor do LM Studio não encontrado em {url}.",
    "Could not load models: {error}": "Não foi possível carregar os modelos: {error}",
    "{n} models found.": "{n} modelos encontrados.",
    # screen & action bar
    "Preview": "Prévia",
    "All lines": "Todas as linhas",
    "Translated lines appear here as they're ready.": "As linhas traduzidas aparecem aqui assim que ficam prontas.",
    "Original": "Original",
    "Translation": "Tradução",
    "Cancel": "Cancelar",
    "Cancelling...": "Cancelando...",
    "Add .srt files to start.": "Adicione arquivos .srt para começar.",
    "Translate {n} file": "Traduzir {n} arquivo",
    "Translate {n} files": "Traduzir {n} arquivos",
    "{name}: {done} of {total} lines": "{name}: {done} de {total} linhas",
    "{name}: {done} of {total} lines, about {eta} left": "{name}: {done} de {total} linhas, faltam cerca de {eta}",
    "{ok} of {total} files translated.": "{ok} de {total} arquivos traduzidos.",
    "Translation cancelled.": "Tradução cancelada.",
    "Starting...": "Iniciando...",
    "Detected language: {name}": "Idioma detectado: {name}",
    "Choose a target language different from the source.": "Escolha um idioma de destino diferente do de origem.",
    # models page
    "Offline models": "Modelos offline",
    "Translate without internet. Each model is downloaded once and kept in {path}.":
        "Traduza sem internet. Cada modelo é baixado uma vez e fica guardado em {path}.",
    "NVIDIA GPU found: translations will use it.": "GPU NVIDIA encontrada: as traduções vão usá-la.",
    "No NVIDIA GPU found: translations run on the processor (CPU).":
        "Nenhuma GPU NVIDIA encontrada: as traduções rodam no processador (CPU).",
    "{size} download, needs about {ram} GB of RAM": "Download de {size}, precisa de cerca de {ram} GB de RAM",
    "Download": "Baixar",
    "Delete": "Excluir",
    "Delete {name}?": "Excluir {name}?",
    "Downloading {done} of {total} MB": "Baixando {done} de {total} MB",
    "Download paused. Click Download to resume.": "Download pausado. Clique em Baixar para continuar.",
    "Open models folder": "Abrir pasta de modelos",
    "Ollama (local AI models)": "Ollama (modelos de IA locais)",
    "Ollama runs AI models on your own PC. Install it, keep it open, and download models here.":
        "O Ollama roda modelos de IA no seu próprio PC. Instale, deixe aberto e baixe os modelos aqui.",
    "Refresh": "Atualizar",
    "Installed in Ollama: {names}": "Instalados no Ollama: {names}",
    "No models installed in Ollama yet.": "Nenhum modelo instalado no Ollama ainda.",
    "Downloading...": "Baixando...",
    "Quality": "Qualidade",
    "Speed": "Velocidade",
    "License: {license}": "Licença: {license}",
    # settings page
    "API keys": "Chaves de API",
    "Keys are stored in your system's credential store, never in plain text.":
        "As chaves ficam no cofre de credenciais do sistema, nunca em texto puro.",
    "Servers": "Servidores",
    "Custom OpenAI-compatible server": "Servidor compatível com OpenAI (personalizado)",
    "Performance": "Desempenho",
    "Parallel requests (cloud)": "Requisições em paralelo (nuvem)",
    "Lines per request (cloud)": "Linhas por requisição (nuvem)",
    "Blank = automatic": "Vazio = automático",
    "Offline engine device": "Dispositivo do motor offline",
    "Automatic": "Automático",
    "Processor (CPU)": "Processador (CPU)",
    "NVIDIA GPU": "GPU NVIDIA",
    "Appearance": "Aparência",
    "Theme": "Tema",
    "System": "Sistema",
    "Dark": "Escuro",
    "Light": "Claro",
    "App language": "Idioma do app",
    "Restart the app to apply the new language.": "Reinicie o app para aplicar o novo idioma.",
    "Data": "Dados",
    "Translation memory: {n} saved lines.": "Memória de tradução: {n} linhas salvas.",
    "Clear memory": "Limpar memória",
    "Open data folder": "Abrir pasta de dados",
    "About": "Sobre",
    "Version {version}": "Versão {version}",
    "Project page on GitHub": "Página do projeto no GitHub",
    "Check for updates": "Verificar atualizações",
    "You have the latest version.": "Você está com a versão mais recente.",
    "Could not check for updates.": "Não foi possível verificar atualizações.",
    "Settings saved.": "Configurações salvas.",
    "Error": "Erro",
    "A translation is running. Stop it and quit?": "Uma tradução está em andamento. Parar e sair?",
    # engine status messages
    "Loading the offline model...": "Carregando o modelo offline...",
    "Downloading the offline model (first time only)...": "Baixando o modelo offline (só na primeira vez)...",
    # provider names and notes
    "Custom (OpenAI-compatible)": "Personalizado (compatível com OpenAI)",
    "Built-in offline (NLLB)": "Offline integrado (NLLB)",
    "Has a free tier. Fast and cheap.": "Tem plano gratuito. Rápido e barato.",
    "Free plan: 500,000 characters/month. Translation-only service, no model to choose.":
        "Plano gratuito: 500.000 caracteres/mês. Serviço só de tradução, sem modelo para escolher.",
    "One key for hundreds of models, including free ones.": "Uma chave para centenas de modelos, inclusive gratuitos.",
    "Any server that speaks the OpenAI chat API (vLLM, llama.cpp server, Together...).":
        "Qualquer servidor compatível com a API de chat da OpenAI (vLLM, llama.cpp server, Together...).",
    "Runs models on your PC. Install Ollama from ollama.com; the app downloads models for you.":
        "Roda modelos no seu PC. Instale o Ollama (ollama.com); o app baixa os modelos para você.",
    "Start LM Studio's local server and load a model.": "Inicie o servidor local do LM Studio e carregue um modelo.",
    "No internet or extra software needed after the model download.":
        "Depois de baixar o modelo, não precisa de internet nem de outros programas.",
}

_current = "en"


def detect_system_language() -> str:
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "")
        if value.lower().startswith("pt"):
            return "pt-BR"
    try:
        loc = locale.getlocale()[0] or ""
        if not loc:
            import ctypes

            windll = getattr(ctypes, "windll", None)
            if windll is not None:
                lang_id = windll.kernel32.GetUserDefaultUILanguage()
                return "pt-BR" if (lang_id & 0x3FF) == 0x16 else "en"
        if loc.lower().startswith(("pt", "portuguese")):
            return "pt-BR"
    except Exception:
        pass
    return "en"


def set_language(code: str) -> str:
    global _current
    _current = code if code in LANGUAGES else detect_system_language()
    return _current


def current() -> str:
    return _current


def t(text: str, **kwargs) -> str:
    value = PT.get(text, text) if _current == "pt-BR" else text
    return value.format(**kwargs) if kwargs else value


def plural(n: int, one: str, many: str, **kwargs) -> str:
    return t(one if n == 1 else many, n=n, **kwargs)
