from odoo import models, fields, api
from datetime import datetime, timedelta
from odoo.exceptions import UserError
import logging
import unicodedata

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

    codigo_empleado = fields.Char(string="Código de empleado", store=False)

    @api.model
    def create(self, vals):
        _logger.info("=== Entradas vals: %s ===", vals)

        tipo = vals.get("tipo", "OVERTIME").upper()
        vals["tipo"] = tipo
        _logger.info("Procesando asignación tipo: %s", tipo)

        if tipo == "OVERTIME":
            codigo_empleado = vals.get('codigo_empleado')
            if not codigo_empleado:
                raise UserError("Debe proporcionar el código de empleado (codigo_empleado) para importar la asignación.")

            codigo_empleado = str(codigo_empleado).strip()
            empleado = self.env['hr.employee'].search([('barcode', '=', codigo_empleado)], limit=1)
            if not empleado:
                raise UserError(f"No se encontró un empleado con código: {codigo_empleado}")

            vals['employee_id'] = empleado.id

            _logger.info("Procesando asignación de horas extra")

            if not empleado.contract_id:
                raise UserError("No se encontró contrato para calcular horas extra.")

            contrato = empleado.contract_id

            # Convertir el salario a mensual
            # salario_base = empleado.contract_id.wage
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
            # Para otros tipos que no sean horas extra
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
