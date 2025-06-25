from odoo import models, api, _
import logging

_logger = logging.getLogger(__name__)

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def compute_sheet(self):
        _logger.info(">>> [INICIO] compute_sheet personalizado para %d nóminas", len(self))

        for payslip in self:
            contract = payslip.contract_id

            # Eliminar inputs previos para evitar duplicados
            for code in ['RENTA', 'AFP', 'ISSS']:
                old_inputs = payslip.input_line_ids.filtered(lambda l: l.code == code)
                if old_inputs:
                    _logger.info("Eliminando inputs previos código %s para nómina %d", code, payslip.id)
                    old_inputs.unlink()

            # Calcular deducciones
            try:
                renta = contract.calcular_deduccion_renta()
                afp = contract.calcular_afp()
                isss = contract.calcular_isss()
            except Exception as e:
                _logger.error("Error en cálculo deducciones: %s", e)
                renta = afp = isss = 0.0

            tipos = {
                code: self.env['hr.payslip.input.type'].search([('code', '=', code)], limit=1)
                for code in ['RENTA', 'AFP', 'ISSS']
            }

            # Crear inputs (montos positivos, la regla salarial descontará)
            valores = [('RENTA', -abs(renta)), ('AFP', -abs(afp)), ('ISSS', -abs(isss))]
            _logger.error("Valores: %s", valores)
            for code, valor in valores:
                tipo = tipos.get(code)
                if tipo:
                    payslip.input_line_ids.create({
                        'name': tipo.name,
                        'code': code,
                        'amount': valor,
                        'payslip_id': payslip.id,
                        'input_type_id': tipo.id,
                    })
                    _logger.info("Input %s agregado a nómina %d con monto %.2f", code, payslip.id, valor)

        res = super().compute_sheet()
        _logger.info(">>> [FIN] compute_sheet personalizado completado")
        return res
