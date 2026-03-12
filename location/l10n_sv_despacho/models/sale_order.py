from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils sv | despacho[sale_order] - res_company")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils' | despacho[sale_order]: {e}")
    constants = None
class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):

        if self.env.context.get("dispatch_route_filter"):

            route_id = self.env.context.get("dispatch_route_id")
            route = self.env["dispatch.route"].browse(route_id)

            # Filtro por municipios de la ruta
            # ---------------------------------------------------------
            if route.zone_municipality_ids:
                domain.append(
                    ("partner_id.munic_id", "in", route.zone_municipality_ids.ids)
                )

            # Exclusión de clientes con etiqueta empleados
            # ---------------------------------------------------------
            tag = self.env["res.partner.category"].search(
                [("name", "ilike", "empleados")], limit=1
            )

            if tag:
                domain += ["!", ("partner_id.category_id", "in", tag.ids)]

            # Exclusión de contacto configurado en empresa
            # ---------------------------------------------------------
            restricted_partner = self.env.company.dispatch_contact_id.id
            if restricted_partner:
                domain.append(("partner_id", "!=", restricted_partner))

            # Exclusión de órdenes que contienen productos tipo servicio
            # (optimizado)
            # ---------------------------------------------------------
            service_lines = self.env["sale.order.line"].search([
                ("product_id.type", "=", constants.TYPE_PRODUCTO_SERVICE)
            ])

            if service_lines:
                order_ids = service_lines.mapped("order_id").ids
                domain.append(("id", "not in", order_ids))

        return super()._search(domain, offset=offset, limit=limit, order=order)
