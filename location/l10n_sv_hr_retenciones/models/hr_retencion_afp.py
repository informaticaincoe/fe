from odoo import models, fields

class HrRetencionAFP(models.Model):
    _name = 'hr.retencion.afp'
    _description = 'Retención AFP'

    porcentaje = fields.Float("Porcentaje (%)", required=True)
    techo = fields.Float("Techo", required=True)
    tipo = fields.Selection([
        ('empleado', 'Empleado'),
        ('patron', 'Patrón')
    ], string="Tipo de Aportante", required=True)
