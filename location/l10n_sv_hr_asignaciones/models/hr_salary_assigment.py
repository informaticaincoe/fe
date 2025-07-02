from odoo import models, fields, api
from datetime import datetime, timedelta
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils [Asignaciones[]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    constants = None

class HrSalaryAssignment(models.Model):
    _name = 'hr.salary.assignment'
    _description = 'Salary Assignment'

    employee_id = fields.Many2one('hr.employee', string='Empleado')
    tipo = fields.Selection([
        ('OVERTIME', 'Hora extra'),
        ('COMISION', 'Comisión'),
        ('VIATICO', 'Viáticos'),
        ('BONO', 'Bono'),
    ], string='Tipo')
    monto = fields.Float("Monto", required=False)
    periodo = fields.Date("Periodo", required=True)
    description = fields.Text(string="Descripción", help="Descripción")
    payslip_id = fields.Many2one('hr.payslip', string='Histórico (Boleta)', help="Si se desea vincular con un recibo de pago.")

    horas_diurnas = fields.Float("Horas extras diurnas", invisible=False)
    horas_nocturnas = fields.Float("Horas extras nocturnas", invisible=False)
    horas_diurnas_descanso = fields.Float("Horas extras diurnas dia descanso", invisible=False)
    horas_nocturnas_descanso = fields.Float("Horas extras nocturnas dia descanso", invisible=False)
    horas_diurnas_asueto = fields.Float("Horas diurnas dia de asueto", invisible=False)
    horas_nocturnas_asueto = fields.Float("Horas nocturnas dia de asueto", invisible=False)

    # def generar_work_entry_overtime(self):
    #     work_entry_type = self.env['hr.work.entry.type'].search([('code', '=', 'OVERTIME')], limit=1)
    #     if not work_entry_type:
    #         raise UserError("No se encontró el tipo de entrada 'OVERTIME'.")
    #
    #     for asignacion in self.filtered(lambda a: a.tipo == 'hora_extra' and not a.payslip_id):
    #         # Buscar el contrato actual
    #         contrato = asignacion.employee_id.contract_id
    #         if not contrato:
    #             raise UserError(f"No se encontró contrato para {asignacion.employee_id.name}")
    #
    #         # Buscar el recibo de nómina activo en el contexto
    #         payslip_id = self.env.context.get('payslip_id')
    #         payslip = self.env['hr.payslip'].browse(payslip_id) if payslip_id else None
    #         if not payslip or not payslip.exists():
    #             raise UserError("No se proporcionó un recibo de nómina válido en el contexto.")
    #
    #         # Verificar si ya existe una línea similar
    #         existe = payslip.worked_days_line_ids.filtered(
    #             lambda l: l.work_entry_type_id == work_entry_type
    #         )
    #         if not existe:
    #             payslip.worked_days_line_ids.create({
    #                 'name': work_entry_type.name,
    #                 'work_entry_type_id': work_entry_type.id,
    #                 'payslip_id': payslip.id,
    #                 'number_of_days': 1,
    #                 'number_of_hours': asignacion.monto,
    #                 'amount': 0.0,
    #             })
    #
    #         asignacion.payslip_id = payslip.id

    # def action_liberar_asignacion(self):
    #     for asignacion in self:
    #         if not asignacion.payslip_id:
    #             raise UserError("La asignación ya está liberada.")
    #         asignacion.payslip_id = False

    @api.model
    def create(self, vals):
        _logger.info("=== Entradas vals: %s ===", vals)

        tipo = vals.get("tipo", "OVERTIME").upper()
        vals["tipo"] = tipo
        _logger.info("Procesando asignación tipo: %s", tipo)

        barcode = vals.get('barcode')
        if not barcode:
            raise UserError("Debe proporcionar el código de empleado (barcode) para importar la asignación.")

        barcode = barcode.strip()
        empleado = self.env['hr.employee'].search([('barcode', '=', barcode)], limit=1)
        if not empleado:
            raise UserError(f"No se encontró un empleado con código: {barcode}")

        vals['employee_id'] = empleado.id
        _logger.info("Empleado encontrado por código: %s => ID: %s", barcode, empleado.id)

        if tipo == "OVERTIME":
            _logger.info("Procesando asignación de horas extra")

            if not empleado.contract_id:
                raise UserError("No se encontró contrato para calcular horas extra.")

            # Convertir el salario a mensual
            # salario_base = empleado.contract_id.wage
            contrato = empleado.contract_id
            salario_base = contrato.wage

            if contrato.schedule_pay in ['bi-weekly', 'semi-monthly']:
                salario_base *= 2
            elif contrato.schedule_pay == 'weekly':
                salario_base *= 4.33

            salario_hora = salario_base / 30.0 / 8.0  # Jornada de 240h/mes
            _logger.info("Salario hora calculado: %s", salario_hora)

            # Obtener horas desde vals
            horas_diurnas = vals.get('horas_diurnas', 0.0)
            horas_nocturnas = vals.get('horas_nocturnas', 0.0)
            horas_diurnas_descanso = vals.get('horas_diurnas_descanso', 0.0)
            horas_nocturnas_descanso = vals.get('horas_nocturnas_descanso', 0.0)
            horas_diurnas_asueto = vals.get('horas_diurnas_asueto', 0.0)
            horas_nocturnas_asueto = vals.get('horas_nocturnas_asueto', 0.0)
            _logger.info("Horas diurnas: %s, horas nocturnas: %s", horas_diurnas, horas_nocturnas)

            # monto_diurno = horas_diurnas * salario_hora * 2.0
            # monto_nocturno = horas_nocturnas * salario_hora * 2.15
            # _logger.info("Monto diurno: %s, monto nocturno: %s", monto_diurno, monto_nocturno)

            # Validar que al menos una hora haya sido ingresada
            total_horas = (
                horas_diurnas + horas_nocturnas +
                horas_diurnas_descanso + horas_nocturnas_descanso +
                horas_diurnas_asueto + horas_nocturnas_asueto
            )
            if total_horas <= 0:
                raise UserError("Debe ingresar al menos una hora extra.")

            # Calcular monto total aplicando recargos
            monto = (
                horas_diurnas * salario_hora * 2.0 +
                horas_nocturnas * salario_hora * 2.5 +
                horas_diurnas_descanso * salario_hora * 2.5 +
                horas_diurnas_descanso * salario_hora * 0.5 +
                horas_nocturnas_descanso * salario_hora * 3.125 +
                horas_diurnas_asueto * salario_hora * 4.0 +
                horas_nocturnas_asueto * salario_hora * 5.0
            )

            # total_monto = monto_diurno + monto_nocturno
            # _logger.info("Total monto horas extra: %s", total_monto)

            # Asignar valores calculados
            vals['monto'] = round(monto, 2)  # vals['monto'] = total_monto
            vals['description'] = vals.get('description', '')
            _logger.info("Vals actualizado con monto y description: %s", {
                'monto': vals['monto'],
                'description': vals['description'],
            })
        else:
            # Para tipos como COMISION, BONO, etc.
            if not vals.get("monto"):
                _logger.error("No se proporcionó 'monto' para tipo distinto de horas extra")
                raise UserError("Debe indicar el monto para este tipo de asignación.")

        record = super().create(vals)
        _logger.info("Registro creado (ID=%s) con vals finales: %s", record.id, record.read()[0])
        return record

    def action_descargar_plantilla(self):
        # Busca el archivo adjunto con la plantilla
        attachment = self.env['ir.attachment'].search([('name', '=', 'Plantilla de Horas extras')], limit=1)
        if not attachment:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'No se encontró la plantilla para descargar.',
                    'type': 'danger',
                    'sticky': False,
                }
            }
        # Retorna la acción para descargar el archivo
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
