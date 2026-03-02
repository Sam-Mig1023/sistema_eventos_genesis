ALTER TABLE recursos ADD COLUMN IF NOT EXISTS cantidad_disponible INTEGER NOT NULL DEFAULT 0;
UPDATE recursos SET cantidad_disponible = cantidad WHERE cantidad_disponible = 0;

CREATE OR REPLACE FUNCTION set_disponible_inicial()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.cantidad_disponible IS NULL THEN
        NEW.cantidad_disponible = NEW.cantidad;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_recursos_set_disp
BEFORE INSERT ON recursos
FOR EACH ROW EXECUTE FUNCTION set_disponible_inicial();

CREATE OR REPLACE FUNCTION ajustar_disponible_asignacion()
RETURNS TRIGGER AS $$
DECLARE
    disp INTEGER;
    delta INTEGER;
BEGIN
    IF TG_OP = 'INSERT' THEN
        SELECT COALESCE(cantidad_disponible, 0) INTO disp FROM recursos WHERE id_recurso = NEW.id_recurso FOR UPDATE;
        IF NEW.cantidad > GREATEST(disp, 0) THEN
            RAISE EXCEPTION 'Cantidad a asignar supera disponible';
        END IF;
        UPDATE recursos SET cantidad_disponible = cantidad_disponible - NEW.cantidad WHERE id_recurso = NEW.id_recurso;
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        delta = NEW.cantidad - OLD.cantidad;
        IF delta <> 0 THEN
            SELECT COALESCE(cantidad_disponible, 0) INTO disp FROM recursos WHERE id_recurso = NEW.id_recurso FOR UPDATE;
            IF delta > 0 AND delta > GREATEST(disp, 0) THEN
                RAISE EXCEPTION 'Cantidad a asignar supera disponible';
            END IF;
            UPDATE recursos SET cantidad_disponible = cantidad_disponible - delta WHERE id_recurso = NEW.id_recurso;
        END IF;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE recursos SET cantidad_disponible = cantidad_disponible + OLD.cantidad WHERE id_recurso = OLD.id_recurso;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_asignacion_adjust_insert ON asignacion_recurso;
CREATE TRIGGER trg_asignacion_adjust_insert
BEFORE INSERT ON asignacion_recurso
FOR EACH ROW EXECUTE FUNCTION ajustar_disponible_asignacion();

DROP TRIGGER IF EXISTS trg_asignacion_adjust_update ON asignacion_recurso;
CREATE TRIGGER trg_asignacion_adjust_update
BEFORE UPDATE ON asignacion_recurso
FOR EACH ROW EXECUTE FUNCTION ajustar_disponible_asignacion();

DROP TRIGGER IF EXISTS trg_asignacion_adjust_delete ON asignacion_recurso;
CREATE TRIGGER trg_asignacion_adjust_delete
BEFORE DELETE ON asignacion_recurso
FOR EACH ROW EXECUTE FUNCTION ajustar_disponible_asignacion();

CREATE TABLE IF NOT EXISTS calificaciones_proveedor (
    id_calificacion INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    id_proveedor    INTEGER NOT NULL REFERENCES proveedores(id_proveedor) ON DELETE RESTRICT,
    id_asignacion   INTEGER REFERENCES asignacion_recurso(id_asignacion) ON DELETE SET NULL,
    calificacion    INTEGER NOT NULL CHECK (calificacion BETWEEN 1 AND 10),
    fecha           TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE VIEW vw_proveedor_calificacion AS
SELECT p.id_proveedor,
       p.nombre,
       ROUND(AVG(c.calificacion)::numeric, 2) AS promedio,
       COUNT(c.id_calificacion) AS cantidad
FROM proveedores p
LEFT JOIN calificaciones_proveedor c ON c.id_proveedor = p.id_proveedor
GROUP BY p.id_proveedor, p.nombre;