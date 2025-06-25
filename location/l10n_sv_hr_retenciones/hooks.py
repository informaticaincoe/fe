from odoo.api import Environment, SUPERUSER_ID

def post_init_configuracion_reglas(env):
    """
    Hook que se ejecuta automáticamente después de instalar o actualizar el módulo.

    Esta función crea un entorno Odoo con permisos de superusuario y llama al método
    'actualizar_cuentas_reglas' del modelo 'hr.salary.rule', que se encarga de asignar
    las cuentas contables configuradas en 'res.configuration' a las reglas salariales
    (AFP, ISSS, RENTA) sólo si estas no tienen ya una cuenta asignada.

    Parámetros:
    -----------
    cr : psycopg2.extensions.cursor
        Cursor de base de datos para ejecutar consultas SQL.
    registry : odoo.registry.Registry
        Registro de modelos de Odoo.

    Uso:
    ----
    Se define como post_init_hook en el archivo __manifest__.py del módulo, para que se
    ejecute automáticamente una vez que el módulo es instalado o actualizado.

    """
    env['hr.salary.rule'].sudo().actualizar_cuentas_reglas()
