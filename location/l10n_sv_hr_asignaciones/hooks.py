from odoo import models, fields, api, SUPERUSER_ID

import base64
import os

import logging
from odoo import models
_logger = logging.getLogger(__name__)

from odoo import api, SUPERUSER_ID

def ejecutar_hooks_post_init(env):
    from .hooks import post_init_configuracion_reglas, cargar_archivo_excel

    post_init_configuracion_reglas(env)
    cargar_archivo_excel(env)


def post_init_configuracion_reglas(env):
    """
    Hook que se ejecuta automáticamente después de instalar o actualizar el módulo.

    Esta función crea un entorno Odoo con permisos de superusuario y llama al método
    'actualizar_cuentas_reglas' del modelo 'hr.salary.rule', que se encarga de asignar
    las cuentas contables configuradas en 'res.configuration' a las reglas salariales
    (Comnisiones, Horas extras, Viaticos) sólo si estas no tienen ya una cuenta asignada.

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
    env['hr.salary.rule'].sudo().actualizar_cuentas_asignaciones()

def cargar_archivo_excel(env):
    ruta_archivo = os.path.join(os.path.dirname(__file__), 'static', 'src', 'plantilla', 'plantilla_horas_extra.xlsx')
    ruta_absoluta = os.path.abspath(ruta_archivo)

    if not os.path.exists(ruta_absoluta):
        raise FileNotFoundError(f"No se encontró el archivo: {ruta_absoluta}")

    with open(ruta_absoluta, 'rb') as f:
        contenido = base64.b64encode(f.read()).decode('utf-8')

    env['ir.attachment'].create({
        'name': 'Plantilla de Horas extras',
        'datas': contenido,
        'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'public': True,
    })

    _logger.info("✅ Archivo Excel de plantilla de horas extra creado en ir.attachment.")
