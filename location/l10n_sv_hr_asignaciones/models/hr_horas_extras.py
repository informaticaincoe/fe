from odoo import models, fields, api, _

class HrHorasExtras(models.Model):
    _name = 'hr.horas.extras'
    _description = 'Horas extras'

    salary_assignment_id = fields.Many2one(
        'hr.salary.assignment',
        string='Asignación salarial',
        ondelete='cascade'
    )

    horas_diurnas = fields.Float("Horas extras diurnas",required=False)
    horas_nocturnas = fields.Float("Horas extras nocturnas", required=False)
    horas_diurnas_descanso = fields.Float("Horas extras diurnas en descanso", required=False)
    horas_nocturnas_descanso = fields.Float("Horas extras nocturnas en descanso", required=False)
    horas_diurnas_asueto = fields.Float("Horas extras diurnas asueto", required=False)
    horas_nocturnas_asueto = fields.Float("Horas extras nocturnas asueto", required=False)
    descripcion = fields.Char("Descripción", required=False)