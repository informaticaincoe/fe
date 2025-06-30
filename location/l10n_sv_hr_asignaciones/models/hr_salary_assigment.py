from odoo import models, fields, api
from datetime import datetime, timedelta
from odoo.exceptions import UserError

class HrSalaryAssignment(models.Model):
    _name = 'hr.salary.assignment'
    _description = 'Salary Assignment'

    employee_id = fields.Many2one('hr.employee', string='Empleado')
    tipo = fields.Selection([
        ('hora_extra', 'Hora extra'),
        ('comision', 'Comisión'),
        ('viaticos', 'Viáticos'),
        ('bono', 'Bono'),
    ], string='Tipo')
    monto = fields.Float("Monto", required=True)
    periodo = fields.Date("Periodo", required=True)
    payslip_id = fields.Many2one('hr.payslip', string='Histórico (Boleta)', help="Si se desea vincular con un recibo de pago.")

    def generar_work_entry_overtime(self):
        work_entry_type = self.env['hr.work.entry.type'].search([('code', '=', 'OVERTIME')], limit=1)
        if not work_entry_type:
            raise UserError("No se encontró el tipo de entrada 'OVERTIME'.")

        for asignacion in self.filtered(lambda a: a.tipo == 'hora_extra' and not a.payslip_id):
            # Buscar el contrato actual
            contrato = asignacion.employee_id.contract_id
            if not contrato:
                raise UserError(f"No se encontró contrato para {asignacion.employee_id.name}")

            # Buscar el recibo de nómina activo en el contexto
            payslip_id = self.env.context.get('payslip_id')
            payslip = self.env['hr.payslip'].browse(payslip_id) if payslip_id else None
            if not payslip or not payslip.exists():
                raise UserError("No se proporcionó un recibo de nómina válido en el contexto.")

            # Verificar si ya existe una línea similar
            existe = payslip.worked_days_line_ids.filtered(
                lambda l: l.work_entry_type_id == work_entry_type
            )
            if not existe:
                payslip.worked_days_line_ids.create({
                    'name': work_entry_type.name,
                    'work_entry_type_id': work_entry_type.id,
                    'payslip_id': payslip.id,
                    'number_of_days': 1,
                    'number_of_hours': asignacion.monto,
                    'amount': 0.0,
                })

            asignacion.payslip_id = payslip.id

    def action_liberar_asignacion(self):
        for asignacion in self:
            if not asignacion.payslip_id:
                raise UserError("La asignación ya está liberada.")
            asignacion.payslip_id = False