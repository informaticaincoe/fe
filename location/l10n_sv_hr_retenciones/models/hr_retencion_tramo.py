from odoo import models, fields

class HrRetencionTramo(models.Model):
    _name = 'hr.retencion.tramo'
    _description = 'Tramos de Renta'

    retencion_id = fields.Many2one('hr.retencion.renta', string="Retencion", required=True, ondelete='cascade')
    tramo = fields.Char("Tramo", required=True)
    desde = fields.Float("Desde", required=True)
    hasta = fields.Float("Hasta")
    porcentaje_excedente = fields.Float("Porcentaje aplicable (%)", required=True)
    exceso_sobre = fields.Float("Sobre el exceso de", required=True)
    cuota_fija = fields.Float("Cuota fija", required=True)
    company_id = fields.Many2one('res.company', string="Compañía", ondelete="set null")
