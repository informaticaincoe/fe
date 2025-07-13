from odoo import models, fields

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # Mapeo entre tipos de asistencia y códigos de entradas de nómina
    tipo_asistencia = fields.Selection([
        ('ASISTENCIA', 'Asistencia'),
        ('PERMISO_SG', 'Permiso sin goce'),
        ('PERMISO_CG', 'Permiso con goce'),
        ('VACACIONES', 'Vacaciones'),
        ('INCAPACIDAD', 'Incapacidad'),
        ('FALTA_INJ', 'Falta injustificada'),
        ('MATERNIDAD', 'Maternidad'),
        ('PATERNIDAD', 'Paternidad'),
        ('MATRIMONIO', 'Matrimonio'),
        ('DISCIPLINARIA', 'Medida disciplinaria'),
    ], string="Tipo de Asistencia", default="ASISTENCIA")

    se_paga = fields.Boolean(string="¿Se paga?", default=True)
