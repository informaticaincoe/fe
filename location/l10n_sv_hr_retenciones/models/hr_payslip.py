from odoo import models, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    # Método sobrescrito para calcular la nómina (payslip) personalizada
    def compute_sheet(self):
        # Registra el inicio del cálculo personalizado de la nómina
        _logger.info(">>> [INICIO] compute_sheet personalizado para %d nóminas", len(self))

        # Itera sobre cada nómina en la lista
        for payslip in self:
            contract = payslip.contract_id  # Se obtiene el contrato asociado a la nómina

            # Eliminar entradas previas (inputs) para evitar duplicados en el cálculo
            for code in ['RENTA', 'AFP', 'ISSS']:
                # Filtra las líneas de input existentes con los códigos específicos
                old_inputs = payslip.input_line_ids.filtered(lambda l: l.code == code)
                if old_inputs:
                    # Si se encuentran entradas previas, se eliminan para evitar duplicados
                    _logger.info("Eliminando inputs previos código %s para nómina %d", code, payslip.id)
                    old_inputs.unlink()

            # Calcular las deducciones: renta, AFP, ISSS
            try:
                # Llama a los métodos del contrato para calcular las deducciones
                renta = contract.calcular_deduccion_renta()
                afp = contract.calcular_afp()
                isss = contract.calcular_isss()
            except Exception as e:
                # Log del error técnico para desarrolladores
                _logger.error("Error al calcular deducciones para nómina %d: %s", payslip.id, e)
                renta = afp = isss = 0.0

                # Mostrar error al usuario en pantalla
                raise UserError(
                    _("Ocurrió un error al calcular las deducciones para la nómina '%s':\n%s") % (payslip.name, str(e)))

            # Busca los tipos de inputs en Odoo usando el código correspondiente (RENTA, AFP, ISSS)
            tipos = {
                code: self.env['hr.payslip.input.type'].search([('code', '=', code)], limit=1)
                for code in ['RENTA', 'AFP', 'ISSS']
            }

            # Si no se encuentra el tipo de input, lanzamos un error
            for code, tipo in tipos.items():
                if not tipo:
                    raise UserError(_("No se encontró el tipo de input para %s. Por favor, asegúrese de que los tipos de deducción estén configurados correctamente.", code))

            # Definir los valores a ser añadidos como inputs a la nómina (con signo negativo, ya que son deducciones)
            valores = [('RENTA', -abs(renta)), ('AFP', -abs(afp)), ('ISSS', -abs(isss))]
            _logger.error("Valores: %s", valores)

            # Crear nuevas entradas para cada tipo de deducción
            for code, valor in valores:
                tipo = tipos.get(code)
                if tipo:
                    # Si el tipo de input es válido, se crea una nueva línea de input para la nómina
                    payslip.input_line_ids.create({
                        'name': tipo.name,  # Nombre del tipo de deducción
                        'code': code,       # Código de la deducción (RENTA, AFP, ISSS)
                        'amount': valor,     # Monto de la deducción (valor negativo)
                        'payslip_id': payslip.id,  # ID de la nómina
                        'input_type_id': tipo.id,  # ID del tipo de input en el sistema
                    })
                    # Registra en el log la adición de un input para la nómina
                    _logger.info("Input %s agregado a nómina %d con monto %.2f", code, payslip.id, valor)

        # Llama al método original para completar el cálculo de la nómina
        res = super().compute_sheet()
        # Registra el fin del cálculo personalizado de la nómina
        _logger.info(">>> [FIN] compute_sheet personalizado completado")
        return res
