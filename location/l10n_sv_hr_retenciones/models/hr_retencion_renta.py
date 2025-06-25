from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class HrRetencionRenta(models.Model):
    _name = 'hr.retencion.renta'
    _description = 'Retenciones'

    codigo = fields.Char("Código", required=True)
    nombre = fields.Char("Tipo de retencion", required=True)
    tramo_ids = fields.One2many('hr.retencion.tramo', 'retencion_id', string="Tramos de Renta")
