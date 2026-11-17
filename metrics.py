"""Cálculos puros para poder validar resultados sin Streamlit ni Supabase."""
import re
import pandas as pd
from config import PARTICIPANTES, REDES, BONOS, ZONA


def texto_like(valor):
    return f"{valor:,}".replace(",", ".") if valor is not None else "—"


def parsear_conteo(texto: str) -> int | None:
    texto = texto.strip()
    if not texto:
        return None
    if not re.fullmatch(r"\d+|\d{1,3}(?:[., ]\d{3})+", texto):
        raise ValueError(f"Conteo inválido: {texto!r}; usa 1200 o 1.200.")
    return int(re.sub(r"[., ]", "", texto))


def resumen_participante(estado: dict, participante: str) -> dict:
    conteos = {red: estado[(participante, red)]["likes"] for red in REDES}
    subtotal = sum(n for n in conteos.values() if n is not None)
    completo = all(n is not None for n in conteos.values())
    bono = BONOS[participante]
    return {
        "participante": participante, "conteos": conteos,
        "parcial_redes": subtotal, "bono": bono,
        "parcial_con_bono": subtotal + bono,
        "total": subtotal + bono if completo else None,
        "completo": completo,
        "redes_contadas": sum(n is not None for n in conteos.values()),
    }


def tabla_ranking(estado: dict):
    resumenes = [resumen_participante(estado, p) for p in PARTICIPANTES]
    ordenados = sorted(
        resumenes,
        key=lambda r: (not r["completo"], -(r["total"] if r["completo"] else r["parcial_con_bono"])),
    )
    filas, valor_anterior, posicion_anterior = [], None, None
    for indice, r in enumerate(ordenados, start=1):
        posicion = "—"
        if r["completo"]:
            posicion = posicion_anterior if r["total"] == valor_anterior else str(indice)
            valor_anterior, posicion_anterior = r["total"], posicion
        filas.append({
            "Posición": posicion, "Participante": r["participante"],
            "TikTok": texto_like(r["conteos"]["TikTok"]),
            "Instagram": texto_like(r["conteos"]["Instagram"]),
            "Facebook": texto_like(r["conteos"]["Facebook"]),
            "Likes de redes": texto_like(r["parcial_redes"]),
            "Bono": f"+{texto_like(r['bono'])}",
            "Parcial + bono": texto_like(r["parcial_con_bono"]),
            "Total completo": texto_like(r["total"]),
            "Estado": "Completo" if r["completo"] else f"Parcial ({r['redes_contadas']}/3)",
        })
    return pd.DataFrame(filas), ordenados


def historial_totales(historial: list[dict], completos: bool = True) -> pd.DataFrame:
    if not historial:
        return pd.DataFrame()
    filas = pd.DataFrame(historial)
    filas = filas[
        filas["participante"].isin(PARTICIPANTES) & filas["red"].isin(REDES)
    ].copy()
    if filas.empty:
        return pd.DataFrame()
    # Orden por id para preservar mediciones del mismo instante.
    if "id" in filas:
        filas = filas.sort_values("id")
    filas["fecha"] = pd.to_datetime(filas["fecha"], utc=True, errors="coerce")
    filas = filas.dropna(subset=["fecha"])
    if filas.empty:
        return pd.DataFrame()
    tabla = filas.pivot_table(
        index="fecha", columns=["participante", "red"], values="likes", aggfunc="last"
    ).sort_index().ffill()
    resultado = pd.DataFrame(index=tabla.index)
    for participante in PARTICIPANTES:
        columnas = pd.MultiIndex.from_tuples([(participante, red) for red in REDES])
        subset = tabla.reindex(columns=columnas)
        resultado[participante] = subset.sum(axis=1, min_count=3 if completos else 1) + BONOS[participante]
    return resultado.dropna(how="all").tz_convert(ZONA)
