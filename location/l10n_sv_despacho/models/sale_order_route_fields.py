from odoo import fields, models

class SaleOrder(models.Model):
    _inherit = "sale.order"

    # Municipio del cliente (tu campo custom en res.partner)
    partner_munic_id = fields.Many2one(
        "res.municipality",
        string="Municipio",
        related="partner_id.munic_id",
        store=True,
        readonly=True,
    )

    # Departamento/Estado del cliente (estándar)
    partner_state_id = fields.Many2one(
        "res.country.state",
        string="Departamento",
        related="partner_id.state_id",
        store=True,
        readonly=True,
    )
