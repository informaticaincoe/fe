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
    from .hooks import post_init_configuracion_reglas, cargar_archivo_excel, copiar_reglas_a_estructuras

    post_init_configuracion_reglas(env)
    cargar_archivo_excel(env)

    # Mapeo de estructuras origen -> destino
    mapping = {
        'INCOE': ['PLAN_VAC', 'PLAN_PRO']
    }
    copiar_reglas_a_estructuras(env, mapping)

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
    _logger.info("[HOOK] Iniciando carga de archivo Excel de asistencia")

    try:
        param_obj = env['ir.config_parameter'].sudo()
        ruta_relativa = param_obj.get_param('ruta_plantilla_asistencia')

        if not ruta_relativa:
            ruta_relativa = 'static/src/plantilla/plantilla_asistencia.xlsx'
            param_obj.set_param('ruta_plantilla_asistencia', ruta_relativa)

        module_path = get_module_path('l10n_sv_hr_retenciones')
        ruta_absoluta = os.path.join(module_path, ruta_relativa)

        _logger.info("[HOOK] Ruta absoluta calculada: %s", ruta_absoluta)

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

        _logger.info("[HOOK] Archivo Excel de asistencia cargado correctamente.")

    except Exception as e:
        _logger.error("[HOOK] Error al cargar el archivo Excel de asistencia: %s", e, exc_info=True)

def copiar_reglas_a_estructuras(env, mapping):
    """
    Copia reglas salariales de estructuras origen a múltiples estructuras destino SIN agregar (copy) al nombre.
    Si el destino es PLAN_PRO (Servicios Profesionales), excluye ISSS/AFP/RENTA.
    Si el destino es PLAN_VAC (Vacaciones), copia TODO igual que en la principal.
    """
    _logger.info("Creación/Actualización de reglas para planillas de vacaciones y servicios profesionales")

    campos_deseados = [
        'name', 'code', 'sequence', 'category_id',
        'condition_select', 'condition_python', 'condition_range',
        'condition_range_min', 'condition_range_max',
        'amount_select', 'amount_fix', 'amount_percentage',
        'amount_percentage_base', 'amount_python_compute',
        'appears_on_payslip', 'active',
        'quantity', 'note',
        'account_debit', 'account_credit',
        'amount_other_input_id',
    ]

    fields_available = env['hr.salary.rule'].fields_get().keys()
    campos_existentes = [c for c in campos_deseados if c in fields_available]

    _logger.info(f"Campos disponibles en hr.salary.rule: {fields_available}")
    _logger.info(f"Campos que se van a copiar/actualizar: {campos_existentes}")

    # Campos Many2one que necesitan normalización
    campos_many2one = {'category_id', 'account_debit', 'account_credit', 'amount_other_input_id'}

    reglas_excluir_servicios = {'RENTA', 'ISSS', 'AFP', 'AFP_EMP', 'ISSS_EMP', 'INCAF'}

    for codigo_origen, destinos in mapping.items():
        estructura_origen = env['hr.payroll.structure'].search([('code', '=', codigo_origen)], limit=1)
        if not estructura_origen:
            _logger.error(f"No se encontró la estructura origen ({codigo_origen})")
            continue

        for codigo_destino in destinos:
            estructura_destino = env['hr.payroll.structure'].search([('code', '=', codigo_destino)], limit=1)
            if not estructura_destino:
                _logger.error(f"No se encontró la estructura destino ({codigo_destino})")
                continue

            _logger.info(f"Iniciando copia/actualización de reglas de {codigo_origen} a {codigo_destino}")

            # Solo filtra si es PLAN_PRO
            domain = [('struct_id', '=', estructura_origen.id)]
            if codigo_destino == 'PLAN_PRO':
                domain.append(('code', 'not in', list(reglas_excluir_servicios)))

            reglas_a_copiar = env['hr.salary.rule'].search(domain)

            for regla in reglas_a_copiar:
                try:
                    vals = regla.read(campos_existentes)[0]

                    for campo in campos_many2one:
                        if campo in vals and isinstance(vals[campo], (list, tuple)):
                            vals[campo] = vals[campo][0] if vals[campo] else False

                    vals['struct_id'] = estructura_destino.id
                    vals['name'] = regla.name

                    regla_destino = env['hr.salary.rule'].search([
                        ('struct_id', '=', estructura_destino.id),
                        ('code', '=', regla.code)
                    ], limit=1)

                    if regla_destino:
                        regla_destino.write(vals)
                        _logger.info(f"La regla {regla.code} ya existe en estructura {codigo_destino}, se actualizó.")
                    else:
                        nueva_regla = env['hr.salary.rule'].create(vals)
                        _logger.info(f"Regla {nueva_regla.code} copiada a estructura {codigo_destino} SIN (copy).")
                except Exception as e:
                    _logger.error(f"Error copiando regla {regla.code} a estructura {codigo_destino}: {e}")

            _logger.info(f"Copia/actualización de reglas de {codigo_origen} a {codigo_destino} finalizada.")
