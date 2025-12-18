# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import config_utils
    _logger.info("SIT Modulo config_utils [hacienda -sale_order_line]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None
    s
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Impuestos permitidos según el diario de la cotización
    allowed_tax_ids = fields.Many2many(
        'account.tax',
        string='Impuestos permitidos (diario)',
        compute='_compute_allowed_tax_ids',
        store=False,
    )

    @api.depends('order_id.journal_id', 'order_id.journal_id.sit_tax_ids', 'product_id')
    def _compute_allowed_tax_ids(self):
        for line in self:
            _logger.info("=== [SOL COMPUTE ALLOWED TAX IDS] line=%s ===", line.id)

            company = line.order_id.company_id if line.order_id else None

            # ----------------------------------------------------------------------
            # 1) Empresa NO usa facturación → usar impuestos estándar de Odoo
            # ----------------------------------------------------------------------
            if not company or not company.sit_facturacion:
                _logger.info("[SOL] Empresa NO usa facturación → usar comportamiento estándar de impuestos")

                # Si la línea tiene producto → aplicar impuestos del producto
                all_taxes_pred = False

                if line.product_id:
                    product_taxes = line.product_id.taxes_id.filtered(
                        lambda t: t.company_id == company
                    )
                    _logger.info("[SOL] Impuestos del producto aplicados: %s", product_taxes.ids)
                    if product_taxes:
                        line.allowed_tax_ids = product_taxes
                    else:
                        all_taxes_pred = True
                else:
                    all_taxes_pred = True

                if all_taxes_pred:
                    # Sin producto → permitir todos los impuestos de ventas de la compañía (default Odoo)
                    all_taxes = self.env['account.tax'].search([
                        ('company_id', '=', company.id),
                        ('type_tax_use', 'in', ['sale', 'none']),
                        ('active', '=', True)
                    ])
                    _logger.info("[SOL] Línea sin producto → impuestos disponibles: %s", all_taxes.ids)
                    line.allowed_tax_ids = all_taxes
                continue

            # ----------------------------------------------------------------------
            # 2) Empresa con facturación → usar impuestos definidos en el diario
            # ----------------------------------------------------------------------
            journal = line.order_id.journal_id
            _logger.info("[SOL] Journal=%s", journal.id if journal else None)

            if journal and journal.sit_tax_ids:
                _logger.info("[SOL] Impuestos permitidos por diario: %s", journal.sit_tax_ids.ids)
                line.allowed_tax_ids = journal.sit_tax_ids
            else:
                _logger.info("[SOL] Diario sin impuestos configurados → sin taxes permitidos")
                line.allowed_tax_ids = False

    @api.onchange('product_id', 'tax_id')
    def _onchange_fix_tax_from_journal(self):
        _logger.info("=== [SOL ONCHANGE PRODUCT/TAX_ID] START line=%s ===", self.id)
        for line in self:
            _logger.info("[SOL] Ejecutando _apply_journal_tax modo on_product línea %s", line.id)
            config_utils._apply_journal_tax(line, 'tax_id', 'on_product') if config_utils else None
        _logger.info("=== [SOL ONCHANGE PRODUCT/TAX_ID] END ===")

    @api.onchange('order_id.journal_id')
    def _onchange_replace_taxes_on_journal_change(self):
        _logger.info("=== [SOL ONCHANGE JOURNAL CHANGE] START line=%s ===", self.id)
        for line in self:
            _logger.info("[SOL] Ejecutando _apply_journal_tax modo on_journal_change línea %s", line.id)
            config_utils._apply_journal_tax(line, 'tax_id', 'on_journal_change') if config_utils else None
        _logger.info("=== [SOL ONCHANGE JOURNAL CHANGE] END ===")