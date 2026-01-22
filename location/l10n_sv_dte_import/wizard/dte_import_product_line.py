from odoo import api, fields, models
from odoo.exceptions import ValidationError

import logging
_logger = logging.getLogger(__name__)

class DTEImportProductLine(models.Model):
    _name = "dte.import.product.line"
    _description = "Líneas de producto DTE (Wizard)"

    wizard_id = fields.Many2one(
        "dte.import",
        required=True,
        ondelete="cascade"
    )

    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        required=True,
        domain="[('company_id', 'in', (False, company_id))]"
    )

    name = fields.Char(
        required=True,
        default="/"
    )

    quantity = fields.Float(
        string="Cantidad",
        default=1.0
    )

    price_unit = fields.Float(
        string="Precio",
        digits='Product Price'
    )

    discount = fields.Float(string="Desc.%")

    tax_ids = fields.Many2many("account.tax", string="Impuestos")

    subtotal = fields.Monetary(
        compute="_compute_amounts",
        currency_field="currency_id",
        store=False,
        readonly=True
    )

    wizard_line_id = fields.Many2one(
        "dte.import.line",
        required=True,
        ondelete="cascade"
    )

    company_id = fields.Many2one(
        "res.company",
        related="wizard_line_id.wizard_id.company_id",
        store=True,
        readonly=True
    )

    currency_id = fields.Many2one(
        related="company_id.currency_id",
        readonly=True
    )

    move_type = fields.Selection(
        related="wizard_line_id.wizard_id.move_type",
        store=False
    )

    def write(self, vals):
        for rec in self:
            state = rec.wizard_line_id.wizard_id.state
            _logger.info("DTE IMPORT PRODUCT: Estado importación: %s", state)

            if state not in ("draft", None):
                raise ValidationError(
                    "No se pueden modificar productos de una importación confirmada."
                )

        return super().write(vals)

    def unlink(self):
        for rec in self:
            state = rec.wizard_line_id.wizard_id.state
            if state not in ("draft", None):
                raise ValidationError(
                    "No se pueden eliminar productos de una importación confirmada."
                )

        return super().unlink()

    @api.depends("quantity", "price_unit", "discount", "tax_ids")
    def _compute_amounts(self):
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100)

            taxes_res = line.tax_ids.compute_all(
                price,
                currency=line.currency_id,
                quantity=line.quantity,
                product=line.product_id,
                partner=False,
            )

            # EXACTAMENTE lo que Odoo muestra como subtotal
            line.subtotal = taxes_res["total_excluded"]

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for line in self:
            if not line.product_id:
                continue

            product = line.product_id
            line.name = product.display_name
            line.price_unit = product.lst_price

            if line.move_type == "sale":
                taxes = product.taxes_id
            else:
                taxes = product.supplier_taxes_id

            line.tax_ids = taxes.filtered(
                lambda t: t.company_id == line.company_id
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                if vals.get("product_id"):
                    product = self.env["product.product"].browse(vals["product_id"])
                    vals["name"] = product.display_name
                else:
                    vals["name"] = "/"
        return super().create(vals_list)
