from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
from odoo.tools import float_round

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    constants = None

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    # Filtrado líneas salariales (solo las reglas que aparecen en payslip)
    line_ids_filtered = fields.One2many(
        comodel_name='hr.payslip.line',
        compute='_compute_line_ids_filtered',
        string='Cálculo del salario (filtrado)',
        store=False,
    )

    # Filtrado líneas de inputs según códigos de reglas visibles
    input_line_ids_filtered = fields.One2many(
        comodel_name='hr.payslip.input',
        compute='_compute_input_line_ids_filtered',
        string='Entradas filtradas',
        store=False,
    )

    @api.depends('line_ids.salary_rule_id.appears_on_payslip')
    def _compute_line_ids_filtered(self):
        """
        Computa las líneas de la nómina (`line_ids_filtered`) que deben mostrarse en el recibo de pago.

        Este campo computado filtra las líneas de salario (`hr.payslip.line`) cuya regla salarial
        asociada (`salary_rule_id`) tenga el campo `appears_on_payslip=True`.

        Esto permite separar visualmente, por ejemplo, descuentos patronales u otras reglas técnicas
        que no deben mostrarse al empleado en el recibo.
        """
        for rec in self:
            rec.line_ids_filtered = rec.line_ids.filtered(
                lambda l: l.salary_rule_id and l.salary_rule_id.appears_on_payslip
            )

    @api.depends('input_line_ids', 'line_ids.salary_rule_id.appears_on_payslip')
    def _compute_input_line_ids_filtered(self):
        """
        Computa las entradas (inputs) filtradas (`input_line_ids_filtered`) que deben mostrarse.

        Se basa en los códigos de las reglas salariales visibles (definidas por `appears_on_payslip=True`).
        Solo los inputs (`hr.payslip.input`) cuyo código coincida con una regla visible serán incluidos.

        Esto permite que, por ejemplo, los aportes del empleador (que no deben mostrarse) también
        se filtren de la vista de otras entradas.
        """
        for rec in self:
            # Obtiene los códigos de las líneas de nómina visibles
            visible_codes = rec.line_ids.filtered(
                lambda l: l.salary_rule_id and l.salary_rule_id.appears_on_payslip
            ).mapped('code')

            # Filtra las líneas de input que coinciden con esos códigos
            rec.input_line_ids_filtered = rec.input_line_ids.filtered(
                lambda i: i.code in visible_codes
            )

    # Método sobrescrito para calcular la nómina (payslip) personalizada
    def compute_sheet(self):
        # Registra el inicio del cálculo personalizado de la nómina
        _logger.info(">>> [INICIO] compute_sheet personalizado para %d nóminas", len(self))

        # Itera sobre cada nómina en la lista
        for payslip in self:
            contract = payslip.contract_id  # Se obtiene el contrato asociado a la nómina

            # Eliminar entradas previas (inputs) para evitar duplicados en el cálculo
            for code in ['RENTA', 'AFP', 'ISSS', 'ISSS_EMP', 'AFP_EMP', 'INCAF']:
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
                afp_patronal = contract.calcular_aporte_patronal('afp')
                isss_patronal = contract.calcular_aporte_patronal('isss')
                incaf = contract.calcular_incaf()
            except Exception as e:
                _logger.error("Error al calcular deducciones para nómina %d: %s", payslip.id, e)
                renta = afp = isss = afp_patronal = isss_patronal = incaf = 0.0

                # Mostrar error al usuario en pantalla
                raise UserError(
                    _("Ocurrió un error al calcular las deducciones para la nómina '%s':\n%s") % (payslip.name, str(e)))

            # Busca los tipos de inputs en Odoo usando el código correspondiente (RENTA, AFP, ISSS)
            tipos = {
                code: self.env['hr.payslip.input.type'].search([('code', '=', code)], limit=1)
                for code in ['RENTA', 'AFP', 'ISSS', 'ISSS_EMP', 'AFP_EMP', 'INCAF']
            }

            _logger.info("Tipos de entradas: %s", tipos)

            # Si no se encuentra el tipo de input, lanzamos un error
            for code, tipo in tipos.items():
                if not tipo:
                    raise UserError(
                        _("No se encontró el tipo de input para %s. Por favor, asegúrese de que los tipos de deducción estén configurados correctamente.",
                          code))

            # Verificar si el contrato es de servicios profesionales
            is_professional = contract.wage_type == constants.SERVICIOS_PROFESIONALES
            _logger.info("Contrato tipo '%s'. ¿Es servicios profesionales? %s", contract.wage_type, is_professional)

            valores = []

            # Definir los valores a ser añadidos como inputs a la nómina (con signo negativo, ya que son deducciones)
            if is_professional:
                valores.append(('RENTA', -abs(renta)))
                _logger.info("Contrato de servicios profesionales: solo se agregará RENTA")
            else:
                valores = [
                    ('RENTA', -abs(renta)),
                    ('AFP', -abs(afp)),
                    ('ISSS', -abs(isss)),
                    ('ISSS_EMP', abs(isss_patronal)),
                    ('AFP_EMP', abs(afp_patronal)),
                    ('INCAF', -abs(incaf)),
                ]
                _logger.error("Valores: %s", valores)

            # Crear nuevas entradas para cada tipo de deducción
            for code, valor in valores:
                tipo = tipos.get(code)
                if tipo:
                    # Si el tipo de input es válido, se crea una nueva línea de input para la nómina
                    payslip.input_line_ids.create({
                        'name': tipo.name,  # Nombre del tipo de deducción
                        'code': code,       # Código de la deducción (RENTA, AFP, ISSS)
                        'amount': float_round(valor, precision_digits=2),     # Monto de la deducción (valor negativo)
                        'payslip_id': payslip.id,  # ID de la nómina
                        'input_type_id': tipo.id,  # ID del tipo de input en el sistema
                    })
                    # Registra en el log la adición de un input para la nómina
                    _logger.info("Input %s agregado a nómina %d con monto %.2f", code, payslip.id, valor)

        _logger.info("Inputs generados: %s", payslip.input_line_ids.mapped(lambda l: (l.code, l.amount)))
        # Llama al método original para completar el cálculo de la nómina
        res = super().compute_sheet()
        # Registra el fin del cálculo personalizado de la nómina
        _logger.info(">>> [FIN] compute_sheet personalizado completado")
        return res
