"""Metadatos públicos: experimental, sin descargar los videos."""
import re
from yt_dlp import YoutubeDL

USER_AGENT_TIKTOK = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)
ANSI = re.compile(r"\x1b\[[0-9;]*m")

class LoggerSilencioso:
    def debug(self, msg):
        pass
    def warning(self, msg):
        pass
    def error(self, msg):
        pass


def extraer_me_gusta(url: str) -> int:
    opciones = {
        "quiet": True, "no_warnings": True, "logger": LoggerSilencioso(),
        "skip_download": True, "noplaylist": True, "ignoreerrors": False,
        "socket_timeout": 12, "retries": 0, "extractor_retries": 0,
        "cachedir": False,
    }
    if "tiktok.com" in url.lower():
        opciones["http_headers"] = {"User-Agent": USER_AGENT_TIKTOK}
    with YoutubeDL(opciones) as ydl:
        datos = ydl.extract_info(url, download=False)
    if not isinstance(datos, dict):
        raise RuntimeError("El sitio no devolvió metadatos del video.")
    valor = datos.get("like_count")
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        raise RuntimeError("La plataforma no devolvió un like_count válido.")
    return valor


def error_comprensible(red: str, exc: Exception) -> str:
    mensaje = ANSI.sub("", str(exc))
    if "Unexpected response from webpage request" in mensaje:
        return "TikTok devolvió una página incompatible con el extractor."
    if "like_count" in mensaje:
        return f"{red} no publicó un conteo válido de likes."
    return mensaje.splitlines()[0][:210] or type(exc).__name__
