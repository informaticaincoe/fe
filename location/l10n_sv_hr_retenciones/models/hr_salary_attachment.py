from odoo import models, fields, api, _
from datetime import date



class HrSalaryAttachment(models.Model):
    _inherit = 'hr.salary.attachment' # Heredamos del modelo original de Odoo

    PERIOD_MONTHS = [
        ('01', 'enero'), ('02', 'febrero'), ('03', 'marzo'),
        ('04', 'abril'), ('05', 'mayo'), ('06', 'junio'),
        ('07', 'julio'), ('08', 'agosto'), ('09', 'septiembre'),
        ('10', 'octubre'), ('11', 'noviembre'), ('12', 'diciembre'),
    ]

    # Campo computado para el nombre del empleado
    employee_name = fields.Char(
        string="Nombre del Empleado",
        compute='_compute_employee_name',
        store=True, # Necesario para agrupar y filtrar en la base de datos
        help="Nombre completo del empleado para búsquedas y agrupaciones."
    )

    # Funciones para la selección de años (reutilizada de tus otros modelos)
    def year_selection(self):
        current_year = date.today().year
        years = list(range(current_year - 3, current_year + 2))
        return [(str(y), str(y)) for y in years]

    # Campos computados para Año, Mes y Quincena
    # Usaremos el campo 'date_start' del modelo hr.salary.attachment para el cálculo
    period_year = fields.Selection(
        selection=year_selection,
        string='Año',
        compute='_compute_period_fields',
        store=True, # Necesario para agrupar y filtrar
        index=True
    )
    period_month = fields.Selection(
        selection=PERIOD_MONTHS,
        string='Mes',
        compute='_compute_period_fields',
        store=True, # Necesario para agrupar y filtrar
        index=True
    )
    period_quincena = fields.Selection(
        selection=[('1', '1ª quincena'), ('2', '2ª quincena')],
        string='Quincena',
        compute='_compute_period_fields',
        store=True, # Necesario para agrupar y filtrar
        index=True
    )

    # Métodos compute
    @api.depends('employee_ids.name')
    def _compute_employee_name(self):
        for rec in self:
            rec.employee_name = rec.employee_ids.name or False

    @api.depends('date_start') # Usamos 'date_start' como referencia de fecha para deducciones
    def _compute_period_fields(self):
        for rec in self:
            # Asegúrate de que el campo 'date_start' existe en hr.salary.attachment
            if rec.date_start:
                d = rec.date_start
                rec.period_year = str(d.year)
                rec.period_month = f"{d.month:02d}"
                rec.period_quincena = '1' if d.day <= 15 else '2'
            else:
                rec.period_year = False
                rec.period_month = False
                rec.period_quincena = False

