# -*- coding: utf-8 -*-
from odoo import fields, models, api
import logging

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import config_utils
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils [hacienda ws-account_move]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None

class sit_account_move(models.Model):
    
    _inherit = 'account.move'
    forma_pago = fields.Many2one('account.move.forma_pago.field', store=True)
    invoice_payment_term_name = fields.Char(related='invoice_payment_term_id.name')
    condiciones_pago = fields.Selection(
        selection='_get_condiciones_pago_selection', string='Condición de la Operación (Pago) - Hacienda')
    sit_plazo = fields.Many2one('account.move.plazo.field', string="Plazos")
    sit_periodo = fields.Integer(string="Periodo")

    sit_tipo_contingencia = fields.Many2one('account.move.tipo_contingencia.field', string="Tipo de Contingencia")
    sit_tipo_contingencia_otro = fields.Text(string="Especifique el Otro Tipo de Contingencia")
    sit_tipo_contingencia_valores = fields.Char(related="sit_tipo_contingencia.valores", string="Tipo de contingiancia(nombre)")
    #sit_modelo_facturacion = fields.Selection(selection='_get_modelo_facturacion_selection', string='Modelo de Facturacion - Hacienda', store=True)
    sit_tipo_transmision = fields.Selection(selection='_get_tipo_transmision_selection', string='Tipo de Transmisión - Hacienda', store=True)
    sit_referencia = fields.Text(string="Referencia", default="")
    sit_observaciones = fields.Text(string="Observaciones", default="")
    sit_qr_hacienda = fields.Binary("QR Hacienda", default=False) 
    sit_json_respuesta = fields.Text("Json de Respuesta", default="")
    sit_regimen = fields.Many2one('account.move.regimen.field', string="Régimen de Exportación")
    journal_code = fields.Char(related='journal_id.code', string='Journal Code')

    codigo_tipo_documento = fields.Char(
        related='journal_id.sit_tipo_documento.codigo',
        store=True
    )

    hacienda_estado = fields.Text("Hacienda Estado")
    amount_tax = fields.Float("amount_tax")

    anexo_type = fields.Selection([
        ("consumidor_final", "Consumidor Final"),
        ("credito_fiscal", "Crédito Fiscal"),
        ("exportacion", "Exportación"),
    ], string="Tipo de Anexo - Hacienda")

    invoice_month = fields.Char(
        string="Mes",
        compute='_compute_invoice_month',
        store=False
    )

    @api.depends('invoice_date')
    def _compute_invoice_month(self):
        for record in self:
            if record.invoice_date:
                # Solo número del mes con dos dígitos
                record.invoice_month = record.invoice_date.strftime('%m')
            else:
                record.invoice_month = ''


    sit_facturacion = fields.Boolean(
        related='company_id.sit_facturacion',
        readonly=True,
        store=True,
    )

    razon_social = fields.Char(
        string="Cliente/Proveedor",
        related='partner_id.name',
        readonly=True,
        store=False,  # no se guarda en la base de datos
    )

    tipo_documento_identificacion = fields.Char(
        string="Tipo documento identificacion",
        compute='_compute_get_tipo_documento',
        readonly=True,
        store=False,
    )

    numero_documento = fields.Char(
        string="Número de documento de identificacion",
        compute='_compute_get_tipo_documento',
        readonly=True,
        store=False,  # no se guarda en la base de datos
    )

    @api.depends('partner_id')
    def _compute_get_tipo_documento(self):
        for record in self:
            if record.partner_id:
                _logger.info("DUI: %s", record.partner_id.dui)
                record.numero_documento = record.partner_id.dui
            elif record.partner_vat:
                    record.numero_documento = record.partner_id.vat
            else:
                record.numero_documento = ''

    @api.depends('partner_id')
    def _compute_get_tipo_documento(self):
        for record in self:
            if record.partner_id and record.partner_id.dui:
                record.tipo_documento_identificacion = "01"
                record.numero_documento = record.partner_id.dui
            elif record.partner_id and record.partner_id.vat:
                record.tipo_documento_identificacion = "03"
                record.numero_documento = record.partner_id.vat
            else:
                record.tipo_documento_identificacion = ''
                record.numero_documento = ''


    def _get_condiciones_pago_selection(self):
        return [
            ('1', '1-Contado'),
            ('2', '2-A Crédito'),
            ('3', '3-Otro'),
        ]

    def _get_modelo_facturacion_selection(self):
        return [
            ('1', 'Modelo Facturación previo'),
            ('2', 'Modelo Facturación diferido'),
        ]
    def _get_tipo_transmision_selection(self):
        return [
            ('1', 'Transmisión normal'),
            ('2', 'Transmisión por contingencia'),
        ]    
    
    @api.onchange('condiciones_pago')
    def change_sit_plazo(self):
        if self.condiciones_pago == 1:
            self.sit_plazo = None

