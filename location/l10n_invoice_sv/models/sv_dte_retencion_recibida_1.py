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
    total_monto_sujeto = fields.Float(string="Total monto", readonly = True, compute='_compute_total_monto_sujeto')
    total_iva_retenido = fields.Float(string="Total iva", readonly = True, compute='_compute_total_iva_retenido')

    factura_relacionada_id = fields.Many2one(
        'account.move',
        string='Factura CCF relacionada',
        help='Solo facturas de cliente tipo 03 (Crédito Fiscal).',
        required = True
    )

    proveedor_id = fields.Many2one(
        'res.partner',
        string='Proveedor',
        required=True,
        readonly=True,
        compute='_compute_proveedor_id',
    )

    @api.depends('factura_relacionada_id')
    def _compute_total_monto_sujeto(self):
        for rec in self:
            move = rec.factura_relacionada_id

            rec.total_monto_sujeto = move.amount_total

    @api.depends('factura_relacionada_id')
    def _compute_total_iva_retenido(self):
        for rec in self:
            move = rec.factura_relacionada_id

            rec.total_iva_retenido = move.amount_total * 0.01

    @api.depends('factura_relacionada_id')
    def _compute_proveedor_id(self):
        for rec in self:
            move = rec.factura_relacionada_id

            rec.proveedor_id = move.partner_id