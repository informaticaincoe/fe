# exp_duca.py
from odoo import models, fields, api

class ExpDuca(models.Model):
    _name = "exp_duca"
    _description = "DUCA (mínima)"
    _rec_name = "number"

    company_id = fields.Many2one("res.company", default=lambda s: s.env.company)

    move_id = fields.Many2one(
        "account.move", string="Factura proveedor",
        domain="[('move_type','in',('in_invoice','in_refund')), ('company_id','=',company_id)]",
        help="Factura a la que se asocia esta DUCA."
    )

    number = fields.Char(string="N° DUCA")
    acceptance_date = fields.Date(string="Fecha aceptación")
    aduana = fields.Char(string="Aduana")
    regimen = fields.Char(string="Régimen")

    currency_id = fields.Many2one("res.currency", string="Moneda DUCA",
                                  default=lambda s: s.env.company.currency_id.id)

    # NUEVOS
    valor_transaccion = fields.Monetary(string="Valor transacción", currency_field="currency_id")
    otros_gastos = fields.Monetary(string="Otros gastos", currency_field="currency_id")

    # Existentes
    valor_en_aduana = fields.Monetary(string="Valor en Aduana", currency_field="currency_id")
    dai_amount = fields.Monetary(string="DAI", currency_field="currency_id")
    iva_importacion = fields.Monetary(string="IVA importación (ref.)", currency_field="currency_id")

    duca_file = fields.Binary(string="Archivo DUCA")
    duca_filename = fields.Char(string="Nombre archivo DUCA")

    _sql_constraints = [
        ('unique_duca_per_move', 'unique(move_id)', 'Solo puede existir una DUCA por factura.'),
    ]

    @api.onchange('duca_file')
    def _onchange_duca_file(self):
        for r in self:
            if r.duca_file and not r.duca_filename:
                r.duca_filename = (r.number and f"DUCA_{r.number}.pdf") or "DUCA.pdf"
