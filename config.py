"""Datos públicos del concurso. NO introducir contraseñas en este archivo."""
from zoneinfo import ZoneInfo

PARTICIPANTES = ("Yan y Yoni", "Verona", "Camila Cruz", "Thiago", "Sócrates")
REDES = ("TikTok", "Instagram", "Facebook")
REDES_AUTOMATICAS = ("TikTok", "Instagram")
BONOS = {
    "Yan y Yoni": 75,
    "Verona": 150,
    "Camila Cruz": 0,
    "Thiago": 0,
    "Sócrates": 100,
}
ENLACES = {
    ("Yan y Yoni", "TikTok"): "https://www.tiktok.com/@chesco.gye/video/7707831013115841812",
    ("Yan y Yoni", "Instagram"): "https://www.instagram.com/reel/DfsebcMhfho/",
    ("Yan y Yoni", "Facebook"): "https://www.facebook.com/share/r/1MXfW85kTv/",
    ("Verona", "TikTok"): "https://www.tiktok.com/@chesco.gye/video/7707831596883414293",
    ("Verona", "Instagram"): "https://www.instagram.com/reel/DfseuifhP97/",
    ("Verona", "Facebook"): "https://www.facebook.com/reel/1412354010883815",
    ("Camila Cruz", "TikTok"): "https://www.tiktok.com/@chesco.gye/video/7707831308059233537",
    ("Camila Cruz", "Instagram"): "https://www.instagram.com/reel/Dfselz4sWdE/",
    ("Camila Cruz", "Facebook"): "https://www.facebook.com/share/r/1Q2D1nSXw7/",
    ("Thiago", "TikTok"): "https://www.tiktok.com/@chesco.gye/video/7707832052447497493",
    ("Thiago", "Instagram"): "https://www.instagram.com/reel/Dfse9AsO0-C/",
    ("Thiago", "Facebook"): "https://www.facebook.com/share/r/18bwUrqib1/",
    ("Sócrates", "TikTok"): "https://www.tiktok.com/@chesco.gye/video/7707832306169285909",
    ("Sócrates", "Instagram"): "https://www.instagram.com/reel/Dfsfr1Yhk9a/",
    ("Sócrates", "Facebook"): "https://www.facebook.com/share/r/1G2PKMt9Fo/",
}
ZONA = ZoneInfo("America/Guayaquil")
INTERVALO_MINUTOS = 10
HISTORIAL_MAX_FILAS = 5000  # Restringe lecturas del dashboard, no borra registros de Supabase.
