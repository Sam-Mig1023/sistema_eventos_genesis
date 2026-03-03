import psycopg2
import streamlit as st
from database.connection import execute_query, execute_query_one, execute_insert

TIPOS_INCIDENCIA = ['Técnica', 'Logística', 'Personal', 'Climática', 'Seguridad', 'Otra']

def get_by_evento(id_evento):
    """Obtiene incidencias de un evento (para listado en página)."""
    try:
        return execute_query(
            """SELECT id_incidencia, tipo_incidencia, descripcion,
                      fecha_registro, estado
               FROM incidencias
               WHERE id_evento = %s
               ORDER BY id_incidencia DESC""",
            (id_evento,)
        ) or []
    except psycopg2.Error as e:
        st.error(f"Error al obtener incidencias: {e}")
        return []

def get_by_id(id_inc):
    """Obtiene una incidencia por su ID."""
    try:
        return execute_query_one(
            """SELECT id_incidencia, id_evento, tipo_incidencia,
                      descripcion, fecha_registro, estado
               FROM incidencias WHERE id_incidencia = %s""",
            (id_inc,)
        )
    except psycopg2.Error as e:
        st.error(f"Error: {e}")
        return None

def create(id_evento, tipo_incidencia, descripcion):
    """Registra una nueva incidencia y retorna su ID."""
    try:
        row = execute_insert(
            """INSERT INTO incidencias (id_evento, tipo_incidencia, descripcion)
               VALUES (%s, %s, %s) RETURNING id_incidencia""",
            (id_evento, tipo_incidencia, descripcion)
        )
        return row[0] if row else None
    except psycopg2.Error as e:
        st.error(f"Error al registrar incidencia: {e}")
        return None

def create_detalle(id_incidencia, descripcion, accion_tomada):
    """Agrega un detalle / acción tomada a una incidencia."""
    try:
        execute_insert(
            """INSERT INTO detalle_incidencia (id_incidencia, descripcion, accion_tomada)
               VALUES (%s, %s, %s)""",
            (id_incidencia, descripcion, accion_tomada)
        )
        return True
    except psycopg2.Error as e:
        st.error(f"Error al registrar detalle: {e}")
        return False

def get_detalles(id_incidencia):
    """Obtiene los detalles de una incidencia."""
    try:
        return execute_query(
            """SELECT id_detalle_incidencia, descripcion, accion_tomada, created_at
               FROM detalle_incidencia
               WHERE id_incidencia = %s
               ORDER BY id_detalle_incidencia""",
            (id_incidencia,)
        ) or []
    except psycopg2.Error as e:
        st.error(f"Error: {e}")
        return []

def cambiar_estado(id_inc, nuevo_estado):
    """Cambia el estado de una incidencia (Abierta → En Proceso → Resuelta → Cerrada)."""
    try:
        execute_insert(
            "UPDATE incidencias SET estado = %s WHERE id_incidencia = %s",
            (nuevo_estado, id_inc)
        )
        return True
    except psycopg2.Error as e:
        st.error(f"Error: {e}")
        return False
