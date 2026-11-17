"""Acceso desde el servidor a Supabase, sin exponer credenciales a visitantes."""
import os
from supabase import create_client
from config import PARTICIPANTES, REDES, ENLACES, INTERVALO_MINUTOS, HISTORIAL_MAX_FILAS


def config_secret(nombre: str) -> str:
    """Los secretos pueden venir de variables de entorno o de Streamlit."""
    valor = os.getenv(nombre, "")
    if valor:
        return valor
    try:
        import streamlit as st
        return str(st.secrets.get(nombre, ""))
    except (FileNotFoundError, KeyError):
        return ""


class AlmacenSupabase:
    def __init__(self, url: str, clave: str):
        if not url or not clave:
            raise ValueError("Faltan SUPABASE_URL o SUPABASE_SECRET_KEY")
        self.cliente = create_client(url, clave)

    def lectura_actual(self) -> dict:
        respuesta = self.cliente.table("actual").select("*").execute()
        estado = {(f["participante"], f["red"]): f for f in respuesta.data}
        faltantes = [clave for clave in ENLACES if clave not in estado]
        if faltantes:
            raise RuntimeError("Faltan registros en Supabase. Ejecuta setup_supabase.sql otra vez.")
        return estado

    def guardar_like(self, participante: str, red: str, likes: int, origen: str) -> bool:
        if (participante, red) not in ENLACES:
            raise ValueError("Participante o red desconocidos")
        if isinstance(likes, bool) or not isinstance(likes, int) or likes < 0:
            raise ValueError("Likes inválidos")
        respuesta = self.cliente.rpc("guardar_medicion", {
            "p_participante": participante, "p_red": red,
            "p_likes": likes, "p_origen": origen,
        }).execute()
        return respuesta.data is True

    def reclamar_consulta(self, participante: str, red: str, forzar: bool = False) -> bool:
        if (participante, red) not in ENLACES or red == "Facebook":
            return False
        respuesta = self.cliente.rpc("claim_lookup", {
            "p_participante": participante, "p_red": red,
            "p_minutos": INTERVALO_MINUTOS, "p_forzar": bool(forzar),
        }).execute()
        return respuesta.data is True

    def registrar_error(self, participante: str, red: str, error: str) -> None:
        self.cliente.table("actual").update({"ultimo_error": error[:250]}).eq(
            "participante", participante
        ).eq("red", red).execute()

    def obtener_historial(self, limite: int = HISTORIAL_MAX_FILAS) -> list[dict]:
        # Se leen los N registros más recientes; en DB no se borran los antiguos.
        filas = []
        tamano_pagina = 1000  # PostgREST normalmente limita las filas de cada respuesta.
        while len(filas) < limite:
            cantidad = min(tamano_pagina, limite - len(filas))
            respuesta = self.cliente.table("historial").select(
                "id, participante, red, likes, origen, fecha"
            ).order("id", desc=True).range(len(filas), len(filas) + cantidad - 1).execute()
            lote = respuesta.data or []
            filas.extend(lote)
            if len(lote) < cantidad:
                break
        return list(reversed(filas))
