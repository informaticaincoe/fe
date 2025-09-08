from odoo.api import Environment, SUPERUSER_ID

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
    from .hooks import post_init_configuracion_reglas, cargar_archivo_excel#, copiar_reglas_a_estructuras

    post_init_configuracion_reglas(env)
    cargar_archivo_excel(env)

    # Mapeo de estructuras origen -> destino
    # mapping = {
    #     'INCOE': ['PLAN_VAC', 'PLAN_PRO']
    # }
    # copiar_reglas_a_estructuras(env, constants.STRUCTURE_MAPPING)

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
    _logger.info("Asignar cuenta contable a las reglas salariales.")
    env['hr.salary.rule'].sudo().actualizar_cuentas_retenciones()

def cargar_archivo_excel(env):
    _logger.info("[HOOK] Iniciando carga de archivo Excel de asistencia y deducciones")

    try:
        param_obj = env['ir.config_parameter'].sudo()
        ruta_relativa = param_obj.get_param('ruta_plantilla_asistencia')
        _logger.info("ruta_relativa %s", ruta_relativa)
        ruta_relativa_deducciones = param_obj.get_param('ruta_plantilla_deducciones')
        _logger.info("ruta_relativa_deducciones %s", ruta_relativa_deducciones)
        ruta_relativa_tiempo_personal = param_obj.get_param('ruta_plantilla_tiempo_personal')
        _logger.info("ruta_relativa_tiempo_personal %s", ruta_relativa_tiempo_personal)

        if not ruta_relativa:
            ruta_relativa = 'static/src/plantilla/plantilla_asistencia.xlsx'
            param_obj.set_param('ruta_plantilla_asistencia', ruta_relativa)

        if not ruta_relativa_deducciones:
            ruta_relativa_deducciones = 'static/src/plantilla/plantilla_deducciones_salariales.xlsx'
            param_obj.set_param('ruta_plantilla_deducciones', ruta_relativa_deducciones)

        if not ruta_relativa_tiempo_personal:
            ruta_relativa_tiempo_personal = 'static/src/plantilla/plantilla_tiempo_personal.xlsx'
            param_obj.set_param('ruta_relativa_tiempo_personal', ruta_relativa_tiempo_personal)

        module_path = get_module_path('l10n_sv_hr_retenciones')
        ruta_absoluta = os.path.join(module_path, ruta_relativa)

        if not os.path.exists(ruta_absoluta):
            raise FileNotFoundError(f"No se encontró el archivo: {ruta_absoluta}")

        with open(ruta_absoluta, 'rb') as f:
            contenido = base64.b64encode(f.read()).decode('utf-8')

        env['ir.attachment'].create({
            'name': 'plantilla_asistencia.xlsx',
            'datas': contenido,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'public': True,
        })

        ruta_absoluta_deducciones = os.path.join(module_path, ruta_relativa_deducciones)

        if not os.path.exists(ruta_absoluta_deducciones):
            raise FileNotFoundError(f"No se encontró el archivo: {ruta_absoluta_deducciones}")

        with open(ruta_absoluta_deducciones, 'rb') as f:
            contenido = base64.b64encode(f.read()).decode('utf-8')

        env['ir.attachment'].create({
            'name': 'plantilla_deducciones_salariales.xlsx',
            'datas': contenido,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'public': True,
        })

        ruta_absoluta_tiempo_personal = os.path.join(module_path, ruta_relativa_tiempo_personal)

        if not os.path.exists(ruta_absoluta_tiempo_personal):
            raise FileNotFoundError(f"No se encontró el archivo: {ruta_absoluta_tiempo_personal}")

        with open(ruta_absoluta_tiempo_personal, 'rb') as f:
            contenido = base64.b64encode(f.read()).decode('utf-8')

        env['ir.attachment'].create({
            'name': 'plantilla_tiempo_personal.xlsx',
            'datas': contenido,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'public': True,
        })

        _logger.info("[HOOK] Archivo Excel de asistencia cargado correctamente.")

    except Exception as e:
        _logger.error("[HOOK] Error al cargar el archivo Excel de asistencia: %s", e, exc_info=True)
