from odoo import fields, models

class SaleOrder(models.Model):
    _inherit = "sale.order"

    partner_munic_id = fields.Many2one(
        "res.municipality",
        string="Municipio",
        related="partner_id.munic_id",
        store=True,
        readonly=True,
    )

    partner_state_id = fields.Many2one(
        "res.country.state",
        string="Departamento",
        related="partner_id.state_id",
        store=True,
        readonly=True,
    )

    # ✅ Dirección (una sola columna “bonita”)
    partner_address = fields.Char(
        string="Dirección",
        compute="_compute_partner_address",
        store=True,
        readonly=True,
    )

    def _compute_partner_address(self):
        for so in self:
            p = so.partner_id
            parts = []
            if p.street:
                parts.append(p.street)
            if p.street2:
                parts.append(p.street2)
            # si querés incluir ciudad o zip:
            if p.city:
                parts.append(p.city)
            if p.zip:
                parts.append(p.zip)
            so.partner_address = " | ".join([x for x in parts if x])
