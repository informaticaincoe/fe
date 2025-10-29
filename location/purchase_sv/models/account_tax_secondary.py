from odoo import api, fields, models

class AccountTaxSecondary(models.Model):
    _inherit = "account.tax"

    # Cuentas alternativas permitirdas SOLO para uso en la validacion de compras
    sv_secondary_account_ids = fields.Many2one(
        'account.tax.secondary.account', 'tax_id',
        string="Cuentas Alternativas para Validación de Compras",
        help="Cuentas alternativas permitidas SOLO para uso en la validacion de compras",
    )

class AccountTaxSecondaryAccount(models.Model):
    _name = 'accounut.tax.secondary.account'
    _description = "Cuentas Alternativas de impuesto"
    _order = 'id'

    tax_id = fields.Many2one(
        'account.tax',
        required=True,
        ondelete='cascade'
    )
    account_id = fields.many2one(
        'account.account', 
        required=True,
        string='Cuenta contable'
    )
    company_id = fields.Many2one(
        related='tax_id.company_id',
        store=True,
        string='Compañía',
        readonly=True
    )
    name = fields.Char(
        string='Etiqueta',
        help="Etiqueta opcional para identificar el uso",
    )
