# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class AccountQuedan(models.Model):
    _name = "account.quedan"
    _description = "Quedán de Proveedor"
    _order = "id desc"

    name = fields.Char(
        string="Número de Quedán",
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code('account.quedan')
    )
    partner_id = fields.Many2one(
        'res.partner',
        string="Proveedor",
        required=True,
        domain=[('supplier_rank', '>', 0)]
    )
    fecha_programada = fields.Date(
        string="Fecha programada de pago",
        required=True
    )
    observaciones = fields.Text(string="Observaciones")

    factura_ids = fields.Many2many(
        'account.move',
        string="Facturas vinculadas",
        domain=[('move_type', '=', 'in_invoice'), ('payment_state', '!=', 'paid')]
    )

    payment_ids = fields.One2many(
        'account.payment',
        'quedan_id',
        string="Pagos relacionados"
    )

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('paid', 'Pagado'),
    ], string="Estado", default='draft', tracking=True)

    monto_total = fields.Monetary(
        string="Monto total",
        compute="_compute_monto_total",
        store=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        string="Moneda",
        default=lambda self: self.env.company.currency_id
    )

    # === Métodos ===
    @api.depends('factura_ids.amount_total')
    def _compute_monto_total(self):
        for rec in self:
            rec.monto_total = sum(rec.factura_ids.mapped('amount_total'))

    def action_confirm(self):
        for rec in self:
            rec.state = 'confirmed'

    def action_paid(self):
        for rec in self:
            rec.state = 'paid'

    def action_reset(self):
        for rec in self:
            rec.state = 'draft'

    def download_quedan(self):
        for rec in self:
            _logger.info("click")