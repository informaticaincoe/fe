from odoo import models, api, _
import logging

_logger = logging.getLogger(__name__)
    # def action_print_payslip(self):
    #     _logger.info("SIT | Ejecutando action_print_payslip personalizado de Deducciones")
    #     return self.env.ref('l10n_sv_hr_retenciones.hr_payslip_report_incoe').report_action(self)

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def compute_sheet(self):
        _logger.info("Inicio compute_sheet personalizado para %d nóminas", len(self))
        res = super().compute_sheet()

        for payslip in self:
            contract = payslip.contract_id
            _logger.info("Procesando nómina ID %d para empleado %s (Contrato ID %d)", payslip.id, payslip.employee_id.name, contract.id)

            bruto = payslip._get_bruto()
            _logger.info("Salario bruto calculado: %.2f", bruto)

            # Calcular deducción renta (valor positivo)
            renta = abs(contract.calcular_deduccion_renta())
            _logger.info("Deducción renta calculada: %.2f", renta)

            # Limpiar input_line_ids con código RENTA para evitar duplicados
            renta_lines = payslip.input_line_ids.filtered(lambda l: l.code == 'RENTA')
            if renta_lines:
                _logger.info("Eliminando %d líneas input RENTA existentes para nómina ID %d", len(renta_lines), payslip.id)
                renta_lines.unlink()

            if renta > 0:
                # Crear línea input con código RENTA
                input_type = self.env['hr.payslip.input.type'].search([('code', '=', 'RENTA')], limit=1)
                if not input_type:
                    _logger.warning("No se encontró input_type con código RENTA. Crearlo en la configuración.")
                    continue  # o return res

                _logger.info("Creando línea input RENTA para nómina ID %d", payslip.id)
                payslip.input_line_ids = [(0, 0, {
                    'name': 'Deducción Renta',
                    'code': 'RENTA',
                    'amount': renta,
                    'contract_id': contract.id,
                    'input_type_id': input_type.id,
                })]
            else:
                _logger.info("No hay deducción renta para nómina ID %d", payslip.id)

        _logger.info("Finalizado compute_sheet personalizado")
        return res

    def _get_bruto(self):
        """Obtiene el total devengado sin deducciones."""
        self.ensure_one()
        bruto = sum(line.total for line in self.line_ids if line.code == 'BASIC')
        _logger.debug("Bruto para nómina ID %d: %.2f", self.id, bruto)
        return bruto
