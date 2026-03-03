import psycopg2
import streamlit as st
from database.connection import execute_query, execute_query_one, execute_insert

DIMENSIONES = [
    "Calidad del servicio",
    "Cumplimiento del programa",
    "Recursos disponibles",
    "Comunicación previa",
]

def get_by_evento(id_evento):
    """Obtiene encuestas registradas para un evento."""
    try:
        return execute_query(
            """SELECT id_encuesta, fecha_evaluacion, nivel_satisfaccion,
                      estado_evaluacion, comentarios
               FROM encuestas
               WHERE id_evento = %s
               ORDER BY id_encuesta""",
            (id_evento,)
        ) or []
    except psycopg2.Error as e:
        st.error(f"Error al obtener encuestas: {e}")
        return []

def get_by_id(id_enc):
    """Obtiene una encuesta por su ID."""
    try:
        return execute_query_one(
            """SELECT id_encuesta, id_evento, fecha_evaluacion,
                      nivel_satisfaccion, estado_evaluacion, comentarios
               FROM encuestas WHERE id_encuesta = %s""",
            (id_enc,)
        )
    except psycopg2.Error as e:
        st.error(f"Error: {e}")
        return None

def get_detalles(id_encuesta):
    """Obtiene las respuestas por dimensión de una encuesta."""
    try:
        return execute_query(
            """SELECT id_detalle_encuesta, pregunta, respuesta
               FROM detalle_encuesta
               WHERE id_encuesta = %s
               ORDER BY id_detalle_encuesta""",
            (id_encuesta,)
        ) or []
    except psycopg2.Error as e:
        st.error(f"Error: {e}")
        return []

def create(id_evento, fecha_evaluacion, nivel_satisfaccion, comentarios):
    """Crea una encuesta y retorna su ID."""
    try:
        row = execute_insert(
            """INSERT INTO encuestas (id_evento, fecha_evaluacion, nivel_satisfaccion, comentarios)
               VALUES (%s, %s, %s, %s) RETURNING id_encuesta""",
            (id_evento, fecha_evaluacion, nivel_satisfaccion, comentarios)
        )
        return row[0] if row else None
    except psycopg2.Error as e:
        st.error(f"Error al crear encuesta: {e}")
        return None

def create_detalle(id_encuesta, pregunta, respuesta):
    """Registra la respuesta de una dimensión en la encuesta."""
    try:
        execute_insert(
            """INSERT INTO detalle_encuesta (id_encuesta, pregunta, respuesta)
               VALUES (%s, %s, %s)""",
            (id_encuesta, pregunta, respuesta)
        )
        return True
    except psycopg2.Error as e:
        st.error(f"Error: {e}")
        return False

def completar_encuesta(id_encuesta):
    """Marca la encuesta como completada."""
    try:
        execute_insert(
            "UPDATE encuestas SET estado_evaluacion = 'Completada' WHERE id_encuesta = %s",
            (id_encuesta,)
        )
        return True
    except psycopg2.Error as e:
        st.error(f"Error: {e}")
        return False
