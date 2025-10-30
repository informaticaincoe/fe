# -*- coding: utf-8 -*-
from odoo import fields, models

# --- Hijo primero: catálogo de cuentas alternativas por impuesto ---
class AccountTaxSecondaryAccount(models.Model):
    _name = 'account.tax.secondary.account'
    _description = 'Cuenta alternativa de impuesto'
    _order = 'id'

    tax_id = fields.Many2one('account.tax', required=True, ondelete='cascade', string='Impuesto')
    account_id = fields.Many2one('account.account', required=True, string='Cuenta contable')
    company_id = fields.Many2one(related='tax_id.company_id', store=True, readonly=True, string='Compañía')
    name = fields.Char(string='Etiqueta')

# --- Extensión de account.tax: lista de cuentas alternativas ---
class AccountTax(models.Model):
    _inherit = 'account.tax'

    sv_secondary_account_ids = fields.One2many(
        'account.tax.secondary.account', 'tax_id',
        string='Cuentas alternativas (compras)',
        help='Se sugieren cuando el vencimiento es mayor que la fecha contable en facturas de proveedor.',
    )
