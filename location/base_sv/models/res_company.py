# -*- coding: utf-8 -*-
from odoo import fields, models, api


class Company(models.Model):
    _inherit = 'res.company'

    vat = fields.Char(string="N.I.T.")
    giro = fields.Char(string="Giro")

    @api.onchange('vat')
    def change_vat(self):
        self.partner_id.vat = self.vat

    email_from_quedan = fields.Char('Remitente Quedán (From)')
    smtp_quedan_id = fields.Many2one('ir.mail_server', 'SMTP Quedán')

    email_from_invoice = fields.Char('Remitente Facturas (From)')
    smtp_invoice_id = fields.Many2one('ir.mail_server', 'SMTP Facturas')

    email_from_payslip = fields.Char('Remitente Boletas (From)')
    smtp_payslip_id = fields.Many2one('ir.mail_server', 'SMTP Boletas')