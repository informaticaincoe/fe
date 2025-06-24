from odoo import models, fields

class HrRetencionISSS(models.Model):
    _name = 'hr.retencion.isss'
    _description = 'Retención ISSS'

    porcentaje = fields.Float("Porcentaje (%)", required=True)
    techo = fields.Float("Techo", required=True)
    tipo = fields.Selection([
        ('empleado', 'Empleado'),
        ('patron', 'Patrón')
    ], string="Tipo de Aportante", required=True)