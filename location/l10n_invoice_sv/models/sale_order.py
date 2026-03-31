from odoo import api, fields, models, _
import logging
from odoo.tools import float_round
_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import config_utils
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils [invoice_sv -sale_order]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None
    constants = None

class SaleOrder(models.Model):
    _inherit = "sale.order"

    recintoFiscal = fields.Many2one('account.move.recinto_fiscal.field', string="Recinto Fiscal")

    # res.partner
    condiciones_pago_default = fields.Selection(
        [
            ('1', '1-Contado'),
            ('2', '2-A Crédito'),
            ('3', '3-Otro'),
        ],
        string="Condición de pago por defecto (DTE)",
        default='1',
    )

    # Aplicar retenciones
    apply_retencion_iva = fields.Boolean(string="Aplicar Retención IVA", default=False)
    retencion_iva_amount = fields.Monetary(string="Monto Retención IVA", currency_field='currency_id', tracking=True,
                                           compute='_compute_retencion_sale', readonly=True, store=True, default=0.0)

    apply_retencion_renta = fields.Boolean(string="Aplicar Renta 10%", default=False)
    retencion_renta_amount = fields.Monetary(string="Monto Retención Renta", currency_field='currency_id', tracking=True,
                                             compute='_compute_retencion_sale', readonly=True, store=True, default=0.0)

    apply_iva_percibido = fields.Boolean(string="Aplicar IVA percibido", default=False)
    iva_percibido_amount = fields.Monetary(string="Monto iva percibido", currency_field='currency_id', tracking=True,
                                           compute='_compute_retencion_sale', readonly=True, store=True, default=0.0)

    amount_total_retenciones = fields.Monetary(
        string="Total a Pagar con Retención",
        currency_field="currency_id",
        compute="_compute_total_con_retenciones",
        store=True,
        tracking=True
    )

    sit_observaciones_order = fields.Text(string="Observaciones", default="")

    # ── Banner de advertencia en el formulario ──────────────────────
    advertencia_gran_contribuyente = fields.Html(
        string='Advertencia Gran Contribuyente',
        compute='_compute_advertencia_gran_contribuyente',
    )

    def _prepare_invoice(self):
        _logger.info("==== PREPARE INVOICE DESDE SALE ORDER ====")

        self.ensure_one()
        invoice_vals = super()._prepare_invoice()

        # Copiamos el recinto fiscal seleccionado en la venta
        if self.recintoFiscal:
            invoice_vals['recinto_sale_order'] = self.recintoFiscal.id

        # Logs de estado de retenciones
        _logger.info("Estado retenciones -> renta:%s iva:%s iva_percibido:%s",
            self.apply_retencion_renta, self.apply_retencion_iva, self.apply_iva_percibido)

        # Copiar configuración de retenciones desde la cotización
        if self.apply_retencion_renta:
            invoice_vals.update({
                'apply_retencion_renta': self.apply_retencion_renta,
                'retencion_renta_amount': self.retencion_renta_amount,
            })

        if self.apply_retencion_iva:
            invoice_vals.update({
                'apply_retencion_iva': self.apply_retencion_iva,
                'retencion_iva_amount': self.retencion_iva_amount,
            })

        if self.apply_iva_percibido:
            invoice_vals.update({
                'apply_iva_percibido': self.apply_iva_percibido,
                'iva_percibido_amount': self.iva_percibido_amount,
            })

        if self.sit_observaciones_order:
            invoice_vals.update({
                'sit_observaciones': self.sit_observaciones_order
            })

        _logger.info("Valores finales enviados para crear factura: %s", invoice_vals)
        _logger.info("==== FIN PREPARE INVOICE ====")
        return invoice_vals

    @api.depends('apply_retencion_renta', 'apply_retencion_iva', 'apply_iva_percibido', 'amount_untaxed')
    def _compute_retencion_sale(self):
        for sale in self:
            """Reinicia los montos de retención e IVA percibido a cero."""
            sale.retencion_renta_amount = 0.0
            sale.retencion_iva_amount = 0.0
            sale.iva_percibido_amount = 0.0
            tipo_doc = sale.journal_id.sit_tipo_documento
            retencion_renta = 0.0
            retencion_iva = 0.0
            iva_percibido = 0.0

            # Ventas → solo si no hay facturación electrónica se resetea
            if not sale.company_id.sit_facturacion:
                _logger.info(
                    "SIT _compute_retencion_sale Cotizacion | Orden de Venta detectada sin facturación -> order_id: %s, se omiten cálculos",
                    sale.id)
                continue

            base_total = sale.amount_untaxed

            if sale.apply_retencion_renta:
                sale.retencion_renta_amount = base_total * 0.10

            _logger.info("base total %s", base_total)
            _logger.info(" sale.retencion_renta_amount %s", sale.retencion_renta_amount)

            # Retencion 1%
            retencion = config_utils.get_config_value(self.env, constants.config_retencion_venta, sale.company_id.id)
            try:
                retencion = float(retencion) / 100.0
            except (TypeError, ValueError):
                retencion = 0.0

            # Retencion IVA
            iva_retencion = config_utils.get_config_value(self.env, constants.config_iva_rete, sale.company_id.id)
            try:
                iva_retencion = float(iva_retencion) / 100.0
            except (TypeError, ValueError):
                iva_retencion = 0.0

            # IVA Percibido
            iva_percibido = config_utils.get_config_value(self.env, constants.config_iva_percibido_venta,
                                                          sale.company_id.id)
            try:
                iva_percibido = float(iva_percibido) / 100.0
            except (TypeError, ValueError):
                iva_percibido = 0.0
            _logger.info("SIT Retencion= %s, Retencion IVA= %s, IVA Percibido= %s", retencion, iva_retencion, iva_percibido)

            if sale.apply_retencion_iva:
                if tipo_doc.codigo in [constants.COD_DTE_FSE]:  # FSE
                    retencion_iva = base_total * iva_retencion
                    sale.retencion_iva_amount = float_round(retencion_iva, precision_rounding=sale.currency_id.rounding)
                elif tipo_doc.codigo in [constants.COD_DTE_CCF, constants.COD_DTE_NC, constants.COD_DTE_ND]:
                    retencion_iva = base_total * retencion
                    sale.retencion_iva_amount = float_round(retencion_iva, precision_rounding=sale.currency_id.rounding)
                else:
                    retencion_iva = base_total * retencion
                    sale.retencion_iva_amount = float_round(retencion_iva, precision_rounding=sale.currency_id.rounding)
            if sale.apply_iva_percibido and tipo_doc.codigo in [constants.COD_DTE_CCF, constants.COD_DTE_NC, constants.COD_DTE_ND]:
                iva_percibido_amount = base_total * iva_percibido
                sale.iva_percibido_amount = float_round(iva_percibido_amount, precision_rounding=sale.currency_id.rounding)

    @api.onchange('partner_id', 'journal_id', 'order_line') # 'order_line'
    def _onchange_partner_id(self):
        _logger.info("[ONCHANGE SALE ORDER] partner_id cambiado en sale.order ID=%s", self.id)

        self.apply_retencion_iva = False
        tipo_documento = None

        if self.journal_id and self.journal_id.sit_tipo_documento:
            tipo_documento = self.journal_id.sit_tipo_documento
        elif self.partner_id and self.partner_id.journal_id and self.partner_id.journal_id.sit_tipo_documento:
            tipo_documento = self.partner_id.journal_id.sit_tipo_documento

        _logger.info(
            "Filtros DTE -> company:%s | sit_fact:%s | tipo_doc:%s | codigo:%s",
            self.company_id,
            self.company_id.sit_facturacion,
            tipo_documento if tipo_documento else None, (tipo_documento.codigo if tipo_documento else None)
        )

        if (self.company_id and self.company_id.sit_facturacion and tipo_documento and
                tipo_documento.codigo in(constants.COD_DTE_FE, constants.COD_DTE_CCF, constants.COD_DTE_NC, constants.COD_DTE_ND)):
            if self.partner_id:
                _logger.info("[ONCHANGE] Cliente: %s (ID=%s) - gran_contribuyente=%s",
                    self.partner_id.name, self.partner_id.id, self.partner_id.gran_contribuyente)

                if self.amount_untaxed >= 100 and self.partner_id.gran_contribuyente:
                    self.apply_retencion_iva = True
                    _logger.info("[ONCHANGE] apply_retencion_iva=True (gran contribuyente y monto >= 100).")
                else:
                    _logger.info("[ONCHANGE] Se estableció apply_retencion_iva=False porque NO es gran contribuyente.")
            else:
                _logger.info("[ONCHANGE] No hay partner seleccionado, apply_retencion_iva=False")

    @api.depends('amount_total', 'retencion_renta_amount', 'retencion_iva_amount', 'iva_percibido_amount')
    def _compute_total_con_retenciones(self):

        _logger.info("==== COMPUTE TOTAL CON RETENCIONES ====")

        for order in self:
            total_ret = (order.retencion_renta_amount + order.retencion_iva_amount + order.iva_percibido_amount)
            order.amount_total_retenciones = order.amount_total - total_ret

            _logger.info("Orden %s | total original=%s | retenciones=%s | total final=%s",
                order.id, order.amount_total, total_ret, order.amount_total_retenciones)

    # ── Banner: depende de apply_retencion_iva (ya calculado) ──────
    @api.depends('apply_retencion_iva', 'partner_id', 'journal_id', 'amount_untaxed')
    def _compute_advertencia_gran_contribuyente(self):
        for order in self:
            tipo_documento = None

            if order.journal_id and order.journal_id.sit_tipo_documento:
                tipo_documento = order.journal_id.sit_tipo_documento
            elif (order.partner_id and order.partner_id.journal_id
                  and order.partner_id.journal_id.sit_tipo_documento):
                tipo_documento = order.partner_id.journal_id.sit_tipo_documento

            _logger.info(
                "Filtros DTE -> company:%s | sit_fact:%s | tipo_doc:%s | codigo:%s",
                order.company_id,
                order.company_id.sit_facturacion,
                tipo_documento if tipo_documento else None,
                (tipo_documento.codigo if tipo_documento else None),
            )

            cumple_dte = (
                    order.company_id
                    and order.company_id.sit_facturacion
                    and tipo_documento
                    and tipo_documento.codigo in (
                        constants.COD_DTE_FE,
                        constants.COD_DTE_CCF,
                        constants.COD_DTE_NC,
                        constants.COD_DTE_ND,
                    )
            )

            if (
                    cumple_dte
                    and order.partner_id
                    and order.partner_id.gran_contribuyente
                    and order.amount_untaxed >= 100
            ):
                order.advertencia_gran_contribuyente = _(
                    '<p><strong>⚠️ </strong>'
                    'El cliente <strong>%s</strong> es Gran Contribuyente. '
                    'La retención de IVA ha sido aplicada automáticamente '
                    'y puede ser modificada si es necesario.</p>'
                ) % order.partner_id.name
            else:
                # Siempre asignar en todos los caminos — evita el ValueError
                order.advertencia_gran_contribuyente = False
