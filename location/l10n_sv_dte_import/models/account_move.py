from odoo import api, fields, models, _

class AccountMove(models.Model):
    _inherit = "account.move"

    dte_import_line_id = fields.Many2one(
        "dte.import.line",
        string="Archivo DTE importado",
        ondelete="restrict",
        index=True,
        readonly=True,
    )

