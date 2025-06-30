import logging
_logger = logging.getLogger(__name__)

def crear_asistencias_faltantes(env):
    _logger.info("Inicio creación de asistencias faltantes.")

    calendar = env.ref('resource.resource_calendar_std', raise_if_not_found=False)
    _logger.info("Calendar= %s", calendar)

    overtime = env.ref('hr_work_entry_contract.work_entry_type_extra_hours', raise_if_not_found=False)

    _logger.info("Overtime= %s", overtime)

    if not calendar or not overtime:
        _logger.warning("No se encontró el calendario estándar o el tipo de horas extra.")
        return

    Attendance = env['resource.calendar.attendance']

    asistencias = [
        {'name': 'Monday Morning', 'dayofweek': '0', 'hour_from': 7.0, 'hour_to': 12.0},
        {'name': 'Monday Lunch', 'dayofweek': '0', 'hour_from': 12.0, 'hour_to': 13.0},
        {'name': 'Monday Afternoon', 'dayofweek': '0', 'hour_from': 13.0, 'hour_to': 16.6},
        {'name': 'Monday Overtime', 'dayofweek': '0', 'hour_from': 16.6, 'hour_to': 24.0,
         'work_entry_type_id': overtime.id},

        {'name': 'Tuesday Morning', 'dayofweek': '1', 'hour_from': 7.0, 'hour_to': 12.0},
        {'name': 'Tuesday Lunch', 'dayofweek': '1', 'hour_from': 12.0, 'hour_to': 13.0},
        {'name': 'Tuesday Afternoon', 'dayofweek': '1', 'hour_from': 13.0, 'hour_to': 16.6},
        {'name': 'Tuesday Overtime', 'dayofweek': '1', 'hour_from': 16.6, 'hour_to': 24.0,
         'work_entry_type_id': overtime.id},

        {'name': 'Wednesday Morning', 'dayofweek': '2', 'hour_from': 7.0, 'hour_to': 12.0},
        {'name': 'Wednesday Lunch', 'dayofweek': '2', 'hour_from': 12.0, 'hour_to': 13.0},
        {'name': 'Wednesday Afternoon', 'dayofweek': '2', 'hour_from': 13.0, 'hour_to': 16.6},
        {'name': 'Wednesday Overtime', 'dayofweek': '2', 'hour_from': 16.6, 'hour_to': 24.0,
         'work_entry_type_id': overtime.id},

        {'name': 'Thursday Morning', 'dayofweek': '3', 'hour_from': 7.0, 'hour_to': 12.0},
        {'name': 'Thursday Lunch', 'dayofweek': '3', 'hour_from': 12.0, 'hour_to': 13.0},
        {'name': 'Thursday Afternoon', 'dayofweek': '3', 'hour_from': 13.0, 'hour_to': 16.6},
        {'name': 'Thursday Overtime', 'dayofweek': '3', 'hour_from': 16.6, 'hour_to': 24.0,
         'work_entry_type_id': overtime.id},

        {'name': 'Friday Morning', 'dayofweek': '4', 'hour_from': 7.0, 'hour_to': 12.0},
        {'name': 'Friday Lunch', 'dayofweek': '4', 'hour_from': 12.0, 'hour_to': 13.0},
        {'name': 'Friday Afternoon', 'dayofweek': '4', 'hour_from': 13.0, 'hour_to': 16.6},
        {'name': 'Friday Overtime', 'dayofweek': '4', 'hour_from': 16.6, 'hour_to': 24.0,
         'work_entry_type_id': overtime.id},

        {'name': 'Saturday Morning', 'dayofweek': '5', 'hour_from': 7.0, 'hour_to': 11.0},
        {'name': 'Saturday Overtime', 'dayofweek': '5', 'hour_from': 11.0, 'hour_to': 24.0,
         'work_entry_type_id': overtime.id},

        {'name': 'Sunday Overtime', 'dayofweek': '6', 'hour_from': 0.0, 'hour_to': 24.0,
         'work_entry_type_id': overtime.id},
    ]

    for i, att in enumerate(asistencias, start=1):
        att['calendar_id'] = calendar.id
        att['sequence'] = i
        exists = Attendance.search([
            ('calendar_id', '=', calendar.id),
            ('dayofweek', '=', att['dayofweek']),
            ('hour_from', '=', att['hour_from']),
            ('hour_to', '=', att['hour_to']),
        ], limit=1)
        if not exists:
            Attendance.create(att)

    _logger.info("Asistencias faltantes creadas exitosamente.")
