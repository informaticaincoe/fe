from odoo import models, fields

class ResourceCalendarAttendance(models.Model):
    _inherit = 'resource.calendar.attendance'

    # vigente = fields.Boolean(string="Vigente", default=True)

import logging
from odoo import models
_logger = logging.getLogger(__name__)

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

# def crear_asistencias_faltantes(env):
#     _logger.warning("🔧 [HOOK] Se ejecutó crear_asistencias_faltantes")
#     _logger.info("Inicio creación de asistencias faltantes.")
#
#     calendar = env.ref('resource.resource_calendar_std', raise_if_not_found=False)
#     overtime = env.ref('hr_work_entry_contract.work_entry_type_extra_hours', raise_if_not_found=False)
#
#     _logger.info("Calendar = %s", calendar)
#     _logger.info("Overtime = %s", overtime)
#
#     if not calendar or not overtime:
#         _logger.warning("No se encontró el calendario estándar o el tipo de horas extra.")
#         return
#
#     Attendance = env['resource.calendar.attendance']
#
#     asistencias = [
#         {'name': 'Monday Morning', 'dayofweek': '0', 'hour_from': 7.0, 'hour_to': 12.0},
#         {'name': 'Monday Lunch', 'dayofweek': '0', 'hour_from': 12.0, 'hour_to': 13.0},
#         {'name': 'Monday Afternoon', 'dayofweek': '0', 'hour_from': 13.0, 'hour_to': 16.0},
#         {'name': 'Monday Overtime', 'dayofweek': '0', 'hour_from': 16.0, 'hour_to': 24.0,
#          'work_entry_type_id': overtime.id},
#
#         {'name': 'Tuesday Morning', 'dayofweek': '1', 'hour_from': 7.0, 'hour_to': 12.0},
#         {'name': 'Tuesday Lunch', 'dayofweek': '1', 'hour_from': 12.0, 'hour_to': 13.0},
#         {'name': 'Tuesday Afternoon', 'dayofweek': '1', 'hour_from': 13.0, 'hour_to': 16.6},
#         {'name': 'Tuesday Overtime', 'dayofweek': '1', 'hour_from': 16.0, 'hour_to': 24.0,
#          'work_entry_type_id': overtime.id},
#
#         {'name': 'Wednesday Morning', 'dayofweek': '2', 'hour_from': 7.0, 'hour_to': 12.0},
#         {'name': 'Wednesday Lunch', 'dayofweek': '2', 'hour_from': 12.0, 'hour_to': 13.0},
#         {'name': 'Wednesday Afternoon', 'dayofweek': '2', 'hour_from': 13.0, 'hour_to': 16.0},
#         {'name': 'Wednesday Overtime', 'dayofweek': '2', 'hour_from': 16.0, 'hour_to': 24.0,
#          'work_entry_type_id': overtime.id},
#
#         {'name': 'Thursday Morning', 'dayofweek': '3', 'hour_from': 7.0, 'hour_to': 12.0},
#         {'name': 'Thursday Lunch', 'dayofweek': '3', 'hour_from': 12.0, 'hour_to': 13.0},
#         {'name': 'Thursday Afternoon', 'dayofweek': '3', 'hour_from': 13.0, 'hour_to': 16.0},
#         {'name': 'Thursday Overtime', 'dayofweek': '3', 'hour_from': 16.0, 'hour_to': 24.0,
#          'work_entry_type_id': overtime.id},
#
#         {'name': 'Friday Morning', 'dayofweek': '4', 'hour_from': 7.0, 'hour_to': 12.0},
#         {'name': 'Friday Lunch', 'dayofweek': '4', 'hour_from': 12.0, 'hour_to': 13.0},
#         {'name': 'Friday Afternoon', 'dayofweek': '4', 'hour_from': 13.0, 'hour_to': 16.0},
#         {'name': 'Friday Overtime', 'dayofweek': '4', 'hour_from': 16.0, 'hour_to': 24.0,
#          'work_entry_type_id': overtime.id},
#
#         {'name': 'Saturday Morning', 'dayofweek': '5', 'hour_from': 7.0, 'hour_to': 11.0},
#         {'name': 'Saturday Overtime', 'dayofweek': '5', 'hour_from': 11.0, 'hour_to': 24.0,
#          'work_entry_type_id': overtime.id},
#
#         {'name': 'Sunday Overtime', 'dayofweek': '6', 'hour_from': 0.0, 'hour_to': 24.0,
#          'work_entry_type_id': overtime.id},
#     ]
#
#     for i, nueva in enumerate(asistencias, start=1):
#         nueva['calendar_id'] = calendar.id
#         nueva['sequence'] = i
#
#         # Buscar cualquier fila con el mismo nombre
#         existente = Attendance.search([
#             ('calendar_id', '=', calendar.id),
#             ('name', '=', nueva['name'])
#         ], limit=1)
#
#         if existente:
#             # Comparar campos clave
#             campos_diferentes = any(
#                 abs(getattr(existente, campo, 0.0) - nueva[campo]) > 0.01 if isinstance(nueva[campo], float) else getattr(existente, campo, None) != nueva[campo]
#                 for campo in ['hour_from', 'hour_to', 'dayofweek', 'work_entry_type_id']
#                 if campo in nueva
#             )
#             if campos_diferentes:
#                 _logger.info("🔄 Archivando fila antigua: %s", existente.name)
#                 existente.vigente = False
#                 nueva['vigente'] = True
#                 Attendance.create(nueva)
#             else:
#                 _logger.info("✔️ Ya existe correctamente: %s", existente.name)
#         else:
#             nueva['vigente'] = True
#             Attendance.create(nueva)
#
#     _logger.info("✔️ Asistencias sincronizadas correctamente.")

