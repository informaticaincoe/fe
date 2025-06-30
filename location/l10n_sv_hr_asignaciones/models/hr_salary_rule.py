from odoo import models

class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    def compute_rule(self, localdict):
        # Si la regla no es OVERTIME, usa el cálculo original
        if self.code != 'OVERTIME':
            return super().compute_rule(localdict)

        # Variables útiles
        contract = localdict.get('contract')
        inputs = localdict.get('inputs', {})

        # Obtén las horas extra ingresadas (input OVERTIME)
        horas_extra = inputs.get('OVERTIME', 0.0)

        # Calcula tarifa hora (ejemplo 160 horas mensuales)
        tarifa_hora = contract.wage / 160 if contract and contract.wage else 0
        tarifa_extra = tarifa_hora * 1.5

        # Calcula el monto total por horas extra
        amount = horas_extra * tarifa_extra

        # Retorna resultado en formato esperado
        return {
            'amount': amount,
            'quantity': 1,
            'rate': 100,
        }
