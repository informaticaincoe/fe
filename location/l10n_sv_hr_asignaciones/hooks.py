from odoo import models, fields, api, SUPERUSER_ID

import base64
import os

import logging
from odoo import models
_logger = logging.getLogger(__name__)

from odoo import api, SUPERUSER_ID
from odoo.modules import get_module_path

# Intentamos importar constantes definidas en un módulo utilitario común.
try:
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo common_utils [Asignaciones -payslip]")
except ImportError as e:
    _logger.error(f"Error al importar 'common_utils': {e}")
    constants = None

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
    """
    Carga la plantilla Excel desde la ruta configurada en `res.configuration`
    (clave='ruta_plantilla_asignaciones') y la guarda como archivo público en `ir.attachment`.
    """
    # ruta_archivo = os.path.join(os.path.dirname(__file__), 'static', 'src', 'plantilla', 'plantilla_asignaciones.xlsx')
    # ruta_absoluta = os.path.abspath(ruta_archivo)

    param_obj = env['ir.config_parameter'].sudo()
    ruta_relativa = param_obj.get_param('ruta_plantilla_asignaciones')

    if not ruta_relativa:
        # Poner valor default para la instalación
        ruta_relativa = 'static/src/plantilla/plantilla_asignaciones.xlsx'
        param_obj.set_param('ruta_plantilla_asignaciones', ruta_relativa)

    # Obtener ruta absoluta del módulo
    module_path = get_module_path('l10n_sv_hr_asignaciones')
    ruta_absoluta = os.path.join(module_path, ruta_relativa)

    if not os.path.exists(ruta_absoluta):
        raise FileNotFoundError(f"No se encontró el archivo: {ruta_absoluta}")

    with open(ruta_absoluta, 'rb') as f:
        contenido = base64.b64encode(f.read()).decode('utf-8')

    env['ir.attachment'].create({
        'name': constants.NOMBRE_PLANTILLA_ASIGNACIONES,
        'datas': contenido,
        'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'public': True,
    })

    _logger.info("Archivo Excel de plantilla de asignaciones cargado en ir.attachment desde %s", ruta_absoluta)
