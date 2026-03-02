import psycopg2
import streamlit as st
from database.connection import execute_query, execute_insert, execute_query_one

def get_ranking_proveedores():
    try:
        return execute_query(
            "SELECT nombre, promedio, cantidad FROM vw_proveedor_calificacion ORDER BY promedio DESC NULLS LAST, cantidad DESC, nombre ASC"
        ) or []
    except psycopg2.Error as e:
        st.error(f"Error: {e}")
        return []

def create(id_proveedor, id_asignacion, calificacion, fecha):
    try:
        execute_insert(
            "INSERT INTO calificaciones_proveedor (id_proveedor, id_asignacion, calificacion, fecha) VALUES (%s,%s,%s,%s)",
            (id_proveedor, id_asignacion, calificacion, fecha)
        )
        return True
    except psycopg2.Error as e:
        st.error(f"Error: {e}")
        return False

def resolve_proveedor_for_asignacion(id_asignacion):
    try:
        row = execute_query_one(
            """
            SELECT COALESCE(r.id_proveedor, (
                SELECT oc.id_proveedor
                FROM ordenes_compra oc
                WHERE oc.id_evento = a.id_evento AND oc.id_recurso = a.id_recurso
                ORDER BY oc.fecha DESC, oc.id_orden_compra DESC
                LIMIT 1
            )) AS id_proveedor
            FROM asignacion_recurso a
            JOIN recursos r ON r.id_recurso = a.id_recurso
            WHERE a.id_asignacion = %s
            """,
            (id_asignacion,)
        )
        return row[0] if row and row[0] else None
    except psycopg2.Error as e:
        st.error(f"Error: {e}")
        return None