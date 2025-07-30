from odoo import models, fields

class HrRetencionAFP(models.Model):
    _name = 'hr.retencion.afp'
    _description = 'Retención AFP'

    porcentaje = fields.Float("Porcentaje (%)", required=True)
    techo = fields.Float("Techo", required=True)
    tipo = fields.Selection([
        ('empleado', 'AFP CRECER Empleado'),
        ('patron', 'AFP CRECER Empleador'),
        ('empleado_conf', 'AFP CONFIA Empleado'),
        ('patron_conf', 'AFP CONFIA EMPLEADOR'),
        ('ipsfa_empleado', 'IPSFA Empleado'),
        ('ipsfa_empleador', 'IPSFA Empleador')
    ], string="Tipo de Aportante", required=True)
