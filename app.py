"""Dashboard V4: Supabase persistente + acceso administrativo + extracción pública."""
from __future__ import annotations

import hmac
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import pandas as pd
import streamlit as st

from config import (PARTICIPANTES, REDES, REDES_AUTOMATICAS, BONOS, ENLACES,
                    ZONA, INTERVALO_MINUTOS)
from extractor import extraer_me_gusta, error_comprensible
from metrics import (texto_like, parsear_conteo, resumen_participante,
                     tabla_ranking, historial_totales)
from storage import AlmacenSupabase, config_secret

st.set_page_config(page_title="Clasificación del concurso", page_icon="🏆", layout="wide")


def hora_local(valor: str | None) -> str:
    if not valor:
        return "Sin datos"
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00")).astimezone(ZONA).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return "Sin datos"


@st.cache_resource(show_spinner=False)
def obtener_almacen(url: str, key: str):
    return AlmacenSupabase(url, key)


def consultar_redes(almacen, redes: tuple[str, ...], forzar: bool = False):
    """La base reclama atómicamente cada publicación para evitar duplicaciones por visitante."""
    permitidas = set(redes).intersection(REDES_AUTOMATICAS)
    candidatos = []
    errores_reclamo = []
    for (participante, red), enlace in ENLACES.items():
        if red not in permitidas:
            continue
        try:
            if almacen.reclamar_consulta(participante, red, forzar=forzar):
                candidatos.append(((participante, red), enlace))
        except Exception as exc:
            errores_reclamo.append(error_comprensible(red, exc))
    if not candidatos:
        return 0, 0, 0, errores_reclamo

    correctas = 0
    fallidas = 0
    with ThreadPoolExecutor(max_workers=2) as executor:
        pendientes = {executor.submit(extraer_me_gusta, url): clave for clave, url in candidatos}
        for futuro in as_completed(pendientes):
            participante, red = pendientes[futuro]
            try:
                likes = futuro.result()
                almacen.guardar_like(participante, red, likes, "Automático (público)")
                correctas += 1
            except Exception as exc:
                fallidas += 1
                try:
                    almacen.registrar_error(participante, red, error_comprensible(red, exc))
                except Exception:
                    pass
    return len(candidatos), correctas, fallidas, errores_reclamo


st.title("🏆 Monitor de likes del concurso")
st.caption("Cinco participantes · TikTok e Instagram automáticos · Facebook manual · Bonos incluidos · Ecuador")

url = config_secret("SUPABASE_URL")
secret_key = config_secret("SUPABASE_SECRET_KEY")
clave_admin = config_secret("DASHBOARD_ADMIN_PASSWORD")
if not url or not secret_key:
    st.error("Falta configurar la conexión a Supabase.")
    st.info("Crea el proyecto, ejecuta `setup_supabase.sql` y configura `SUPABASE_URL` y "
            "`SUPABASE_SECRET_KEY` en los Secrets de Streamlit. Consulta `README.md`.")
    st.stop()
try:
    almacen = obtener_almacen(url, secret_key)
except Exception:
    st.error("No se pudo inicializar el cliente de Supabase. Verifica los Secrets.")
    st.stop()

# Autorización conservadora: no se permiten cambios manuales si falta la clave.
if "es_admin" not in st.session_state:
    st.session_state.es_admin = False
if "intentos_admin" not in st.session_state:
    st.session_state.intentos_admin = 0
with st.sidebar:
    st.header("Acceso administrativo")
    if not clave_admin:
        st.warning("No hay contraseña configurada: la edición está deshabilitada.")
        st.session_state.es_admin = False
    elif st.session_state.es_admin:
        st.success("Administrador autenticado")
        if st.button("Cerrar sesión", use_container_width=True):
            st.session_state.es_admin = False
            st.rerun()
    elif st.session_state.intentos_admin >= 5:
        st.error("Demasiados intentos en esta sesión. Cierra la pestaña y consulta al administrador.")
    else:
        with st.form("acceso_admin", clear_on_submit=True):
            entrada = st.text_input("Contraseña de administrador", type="password")
            envio = st.form_submit_button("Entrar")
        if envio:
            if hmac.compare_digest(entrada, clave_admin):
                st.session_state.es_admin = True
                st.session_state.intentos_admin = 0
                st.rerun()
            else:
                st.session_state.intentos_admin += 1
                st.error("Contraseña incorrecta")
    permiso_edicion = bool(clave_admin and st.session_state.es_admin)
    st.divider()
    st.header("Actualización")
    st.caption("TikTok e Instagram: intento automático como máximo cada 10 minutos por publicación "
               "mientras haya visitas activas. Facebook siempre es manual.")
    redes_activas = st.multiselect("Consultar automáticamente", REDES_AUTOMATICAS,
                                  default=list(REDES_AUTOMATICAS))
    forzar = st.button("Forzar consulta ahora (administrador)",
                       disabled=not permiso_edicion or not redes_activas,
                       use_container_width=True)
    recargar = st.button("Actualizar vista", use_container_width=True)
    if recargar:
        st.rerun()
    if forzar and permiso_edicion:
        st.session_state["forzar_una_vez"] = True
    st.divider()
    st.markdown("**Bonificaciones**")
    for participante in PARTICIPANTES:
        st.caption(f"{participante}: +{BONOS[participante]}")


@st.fragment(run_every=f"{INTERVALO_MINUTOS}m")
def panel():
    if redes_activas:
        with st.spinner("Comprobando si hay publicaciones pendientes de actualizar..."):
            usar_forzado = bool(permiso_edicion and st.session_state.pop("forzar_una_vez", False))
            intentados, exitos, errores, errores_reclamo = consultar_redes(
                almacen, tuple(redes_activas), forzar=usar_forzado
            )
        if intentados:
            st.caption(f"Lecturas intentadas: {intentados} · Correctas: {exitos} · Sin dato nuevo: {errores}.")
        if errores_reclamo:
            st.warning("No se pudo consultar el estado de algunas publicaciones en Supabase. "
                       "Comprueba los permisos y las funciones SQL.")
    try:
        estado = almacen.lectura_actual()
    except Exception:
        st.error("No se pudieron cargar los datos de Supabase. Verifica la conexión y `setup_supabase.sql`.")
        return

    tabla, ordenados = tabla_ranking(estado)
    completos = [r for r in ordenados if r["completo"]]

    st.subheader("Clasificación general")
    st.dataframe(tabla, hide_index=True, use_container_width=True)
    st.download_button("Descargar clasificación (CSV)",
                       data=tabla.to_csv(index=False).encode("utf-8-sig"),
                       file_name="clasificacion_concurso.csv", mime="text/csv")

    if len(completos) == len(PARTICIPANTES):
        lideres = [r["participante"] for r in completos if r["total"] == completos[0]["total"]]
        if len(lideres) == 1:
            st.success(f"Lidera **{completos[0]['participante']}** con "
                       f"**{texto_like(completos[0]['total'])}** likes, bono incluido.")
        else:
            st.info(f"Empate en el primer lugar: {', '.join(lideres)}.")
    elif completos:
        st.warning(f"Clasificación provisional: solo {len(completos)} de {len(PARTICIPANTES)} "
                   "tienen las tres redes registradas. Los demás no reciben puesto definitivo.")
    else:
        st.warning("No hay totales completos todavía. La columna 'Parcial + bono' "
                   "no determina el ganador.")

    st.subheader("Ventaja del primer lugar")
    if len(completos) >= 2:
        primero, segundo = completos[:2]
        diferencia = primero["total"] - segundo["total"]
        texto = "Ventaja provisional" if len(completos) != len(PARTICIPANTES) else "Ventaja sobre el segundo"
        st.metric(texto, f"+{texto_like(diferencia)} likes")
        if diferencia == 0:
            st.caption(f"Empate: {primero['participante']} y {segundo['participante']} "
                       f"tienen {texto_like(primero['total'])} likes.")
        else:
            st.caption(f"{primero['participante']} ({texto_like(primero['total'])}) supera a "
                       f"{segundo['participante']} ({texto_like(segundo['total'])}) por "
                       f"{texto_like(diferencia)} likes (bonos incluidos).")
    else:
        st.info("Hace falta completar las tres plataformas de al menos dos participantes.")

    st.subheader("Comparación por plataforma")
    grafico = pd.DataFrame(
        {red: [estado[(p, red)]["likes"] for p in PARTICIPANTES] for red in REDES},
        index=PARTICIPANTES,
    )
    if grafico.notna().any().any():
        st.bar_chart(grafico, stack=False)
    else:
        st.caption("No hay conteos para graficar.")

    st.subheader("Detalle y enlaces")
    tabs = st.tabs(PARTICIPANTES)
    for i, p in enumerate(PARTICIPANTES):
        with tabs[i]:
            r = resumen_participante(estado, p)
            cols = st.columns(3)
            for j, red in enumerate(REDES):
                with cols[j]:
                    registro = estado[(p, red)]
                    st.metric(red, texto_like(registro["likes"]))
                    st.caption(f"{registro['origen'] or 'Sin medición'} · "
                               f"Actualizado: {hora_local(registro['actualizado'])}")
                    st.markdown(f"[Abrir publicación de {red}]({ENLACES[(p, red)]})")
                    if registro.get("ultimo_error") and red in REDES_AUTOMATICAS:
                        st.caption(f"Consulta fallida: {registro['ultimo_error']}")
            m1, m2, m3 = st.columns(3)
            m1.metric("Likes disponibles", texto_like(r["parcial_redes"]))
            m2.metric("Bono", f"+{texto_like(r['bono'])}")
            m3.metric("Total completo" if r["completo"] else "Parcial + bono",
                      texto_like(r["total"] if r["completo"] else r["parcial_con_bono"]))
            if not r["completo"]:
                st.caption("Faltan: " + ", ".join(red for red, n in r["conteos"].items() if n is None))

    st.subheader("Evolución histórica")
    try:
        historial = almacen.obtener_historial()
        evol_completa = historial_totales(historial, completos=True)
        if not evol_completa.empty:
            st.line_chart(evol_completa)
        else:
            st.caption("El historial completo aparecerá cuando existan tres conteos por participante.")
        evol_parcial = historial_totales(historial, completos=False)
        if not evol_parcial.empty:
            with st.expander("Ver evolución provisional"):
                st.line_chart(evol_parcial)
        st.caption("El gráfico utiliza los registros históricos más recientes; los antiguos se conservan "
                   "en Supabase. Solo se registra un punto nuevo cuando cambia un conteo.")
    except Exception:
        st.warning("El historial no está disponible temporalmente; la clasificación sigue siendo válida.")

    st.caption("Los likes automáticos son aproximaciones obtenidas de metadatos públicos, no conteos "
               "oficiales del concurso. Facebook se registra manualmente. Los errores no borran lecturas previas.")


panel()

if permiso_edicion:
    st.divider()
    st.subheader("Administración: introducir likes de Facebook")
    st.caption("Deja vacío para conservar el valor anterior; cero es un valor válido.")
    try:
        datos_actuales = almacen.lectura_actual()
    except Exception:
        st.error("No se pueden editar datos sin conexión a Supabase.")
        st.stop()
    with st.form("editar_facebook", clear_on_submit=True):
        fb = {}
        for p in PARTICIPANTES:
            c1, c2 = st.columns([2, 3])
            with c1:
                st.markdown(f"**{p}**")
                st.caption("Actual: " + texto_like(datos_actuales[(p, "Facebook")]["likes"]))
            with c2:
                fb[p] = st.text_input(f"Facebook — {p}", key=f"facebook_{p}",
                                      placeholder="Nuevo valor (opcional)")
        guardar_fb = st.form_submit_button("Guardar Facebook", type="primary")
    if guardar_fb:
        try:
            nuevos = {p: val for p, texto in fb.items()
                      if (val := parsear_conteo(texto)) is not None}
            for p, n in nuevos.items():
                almacen.guardar_like(p, "Facebook", n, "Manual")
        except ValueError as exc:
            st.error(str(exc))
        except Exception:
            st.error("No se pudo escribir en Supabase. Revisa permisos y conexión.")
        else:
            if nuevos:
                st.success(f"Se guardaron {len(nuevos)} conteos de Facebook.")
                st.rerun()
            else:
                st.info("No se ingresaron cambios.")

    with st.expander("Corrección manual excepcional: Instagram o TikTok"):
        st.caption("Solo si la lectura automática falla. La próxima lectura válida sustituirá la corrección.")
        with st.form("editar_otras", clear_on_submit=True):
            entradas = {}
            for p in PARTICIPANTES:
                st.markdown(f"**{p}**")
                cs = st.columns(2)
                for i, red in enumerate(REDES_AUTOMATICAS):
                    with cs[i]:
                        entradas[(p, red)] = st.text_input(
                            f"{red} — {p}", key=f"manual_{red}_{p}",
                            placeholder="Nuevo valor (opcional)")
            enviar = st.form_submit_button("Guardar correcciones")
        if enviar:
            try:
                nuevos = {clave: n for clave, texto in entradas.items()
                          if (n := parsear_conteo(texto)) is not None}
                for (p, red), n in nuevos.items():
                    almacen.guardar_like(p, red, n, "Manual")
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                st.error("No se pudo guardar la corrección en Supabase.")
            else:
                if nuevos:
                    st.success(f"Se guardaron {len(nuevos)} correcciones.")
                    st.rerun()
                else:
                    st.info("No se ingresaron cambios.")
else:
    st.caption("Los formularios de edición solo están disponibles para el administrador autenticado.")
