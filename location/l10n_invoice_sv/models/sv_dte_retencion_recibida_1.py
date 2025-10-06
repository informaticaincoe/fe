from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from .amount_to_text_sv import to_word
import base64
import logging

_logger = logging.getLogger(__name__)
import base64
import json
from decimal import Decimal, ROUND_HALF_UP
from odoo.tools import float_round

class SvDteRetencionRecibida1(models.Model):
    _name = "sv.dte.retencion.recibida1"
    _description = "Comprobantes de retención recibidas"

    numero_control = fields.Char(string="Número de control", default=False, required=True)
    codigo_generacion = fields.Char(string="Código generación", default=False, required=True)
    sello_recepcion = fields.Char(string="Sello Recepcion", default=False, required=True)
    fecha_documento = fields.Date(string="Fecha de documento", default=False, required=True)
    fecha_recibido = fields.Date(string="Fecha de recibido", default=False, required=True)

    factura_relacionada_id = fields.Many2one(
        'account.move',
        string='Factura CCF relacionada',
        help='Solo facturas de cliente tipo 03 (Crédito Fiscal).',
        required = True
    )