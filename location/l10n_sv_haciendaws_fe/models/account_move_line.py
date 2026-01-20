import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import config_utils
    _logger.info("SIT Modulo config_utils [hacienda -account_move_line]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None

class AccountMoveLine(models.Model):
    _inherit = ['account.move.line']

    allowed_invoice_tax_ids = fields.Many2many(
        'account.tax',
        string='Impuestos permitidos (diario)',
        compute='_compute_invoice_allowed_tax_ids',
        store=False,
    )

    @api.depends('move_id.journal_id', 'move_id.journal_id.sit_tax_ids')
    def _compute_invoice_allowed_tax_ids(self):
        for line in self:
            _logger.info("=== [SOL COMPUTE ALLOWED TAX IDS] line=%s ===", line.id)

            company = line.move_id.company_id if line.move_id else None
            move = line.move_id
            move_type = move.move_type if move else False

            is_purchase = move_type in ('in_invoice', 'in_refund')

            # ----------------------------------------------------------------------
            # 0) Compras → comportamiento estándar de Odoo (NO restringir impuestos)
            # ----------------------------------------------------------------------
            if is_purchase:
                _logger.info("[SOL] Compra detectada → usar comportamiento estándar de Odoo")

                company = line.move_id.company_id
                if line.product_id:
                    taxes = line.product_id.supplier_taxes_id.filtered(
                        lambda t: t.company_id == company
                    )
                    line.allowed_invoice_tax_ids = taxes
                else:
                    line.allowed_invoice_tax_ids = self.env['account.tax'].search([
                        ('company_id', '=', company.id),
                        ('type_tax_use', 'in', ['purchase', 'none']),
                        ('active', '=', True),
                    ])
                continue

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
                        line.allowed_invoice_tax_ids = product_taxes
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
                    line.allowed_invoice_tax_ids = all_taxes
                continue

            # ----------------------------------------------------------------------
            # 2) Empresa con facturación → usar impuestos definidos en el diario
            # ----------------------------------------------------------------------
            journal = line.move_id.journal_id
            _logger.info("[SOL] Journal=%s", journal.id if journal else None)

            if journal and journal.sit_tax_ids:
                _logger.info("[SOL] Impuestos permitidos por diario: %s", journal.sit_tax_ids.ids)
                line.allowed_invoice_tax_ids = journal.sit_tax_ids
            else:
                _logger.info("[SOL] Diario sin impuestos configurados → sin taxes permitidos")
                line.allowed_invoice_tax_ids = False

    @api.onchange('product_id', 'tax_id')
    def _onchange_fix_tax_from_invoice_journal(self):
        _logger.info("=== [AML ONCHANGE PRODUCT/TAX_IDS] START line=%s ===", self.id)
        for line in self:
            _logger.info("[AML] Ejecutando _apply_journal_tax modo on_product para línea %s", line.id)
            config_utils._apply_journal_tax(line, 'tax_ids', 'on_product') if config_utils else None
        _logger.info("=== [AML ONCHANGE PRODUCT/TAX_IDS] END ===")

    @api.onchange('move_id.journal_id')
    def _onchange_replace_taxes_on_invoice_journal_change(self):
        _logger.info("=== [AML ONCHANGE JOURNAL CHANGE] START line=%s ===", self.id)
        for line in self:
            _logger.info("[AML] Ejecutando _apply_journal_tax modo on_journal_change para línea %s", line.id)
            config_utils._apply_journal_tax(line, 'tax_ids', 'on_journal_change') if config_utils else None
        _logger.info("=== [AML ONCHANGE JOURNAL CHANGE] END ===")