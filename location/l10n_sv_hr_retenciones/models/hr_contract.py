import logging
from odoo import models

_logger = logging.getLogger(__name__)

class HrContract(models.Model):
    _inherit = 'hr.contract'

    def calcular_afp(self):
        self.ensure_one()
        salario = self.wage
        porcentaje_afp = 0.0725  # Porcentaje estándar para empleado en El Salvador
        deduccion = salario * porcentaje_afp
        _logger.info("AFP para contrato ID %d: salario %.2f * %.4f = %.2f", self.id, salario, porcentaje_afp, deduccion)
        return deduccion

    def calcular_isss(self):
        self.ensure_one()
        salario = self.wage
        techo_isss = 1000.00  # Techo legal ISSS en El Salvador
        porcentaje_isss = 0.03  # 3% para el empleado
        base = min(salario, techo_isss)
        deduccion = base * porcentaje_isss
        _logger.info("ISSS para contrato ID %d: base %.2f * %.4f = %.2f", self.id, base, porcentaje_isss, deduccion)
        return deduccion

    def calcular_deduccion_renta(self, bruto=None):
        self.ensure_one()
        _logger.info("Cálculo de deducción de renta iniciado para contrato ID %s", self.id)

        if not self.schedule_pay:
            _logger.warning("El contrato no tiene definida la frecuencia de pago.")
            return 0.0

        codigo_mapeo = {
            'monthly': 'a',
            'bi-weekly': 'b',
            'weekly': 'c',
        }

        codigo = codigo_mapeo.get(self.schedule_pay)
        _logger.info("Frecuencia de pago: %s → Código tabla: %s", self.schedule_pay, codigo)

        if not codigo:
            _logger.warning("No se encontró código de tabla para la frecuencia de pago '%s'", self.schedule_pay)
            return 0.0

        tabla = self.env['hr.retencion.renta'].search([('codigo', '=', codigo)], limit=1)
        if not tabla:
            _logger.warning("No se encontró tabla de remuneración gravada con código '%s'", codigo)
            return 0.0

        bruto = bruto if bruto is not None else self.wage or 0.0
        _logger.info("Salario bruto usado para cálculo: %.2f", bruto)

        tramos = tabla.tramo_ids.sorted(key=lambda t: t.desde)
        for tramo in tramos:
            if (not tramo.hasta or bruto <= tramo.hasta) and bruto >= tramo.desde:
                exceso = bruto - tramo.exceso_sobre
                resultado = tramo.cuota_fija + (exceso * tramo.porcentaje_excedente / 100)
                _logger.info("Deducción de renta calculada: %.2f (tramo aplicado)", resultado)
                return resultado

        _logger.info("No se encontró tramo aplicable para el salario bruto.")
        return 0.0
