from odoo import api, fields, models, _
import logging
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo common_utils-constants [Despacho - account_move]")
except ImportError as e:
    _logger.error(f"Error al importar 'constants' en modelo dispatch_route: {e}")
    constants = None

class AccountMove(models.Model):
    _inherit = 'account.move'


    ##FRANCISCO FLORES

    dispatch_state = fields.Selection([
        ("free", "Libre"),
        ("assigned", "Asignada a ruta"),
        ("delivered", "Entregada"),
        ("returned", "Devuelta"),
    ], default="free", copy=False)

    dispatch_reception_line_id = fields.Many2one("dispatch.route.reception.line", copy=False)
    dispatch_return_id = fields.Many2one("dispatch.route.invoice.return", copy=False)

    ############

    dispatch_route_id = fields.Many2one(
        'dispatch.route',
        string='Ruta de despacho',
        ondelete='set null',
        index=True,
        copy=False
    )

    partner_phone = fields.Char(
        related='partner_id.phone',
        string='Teléfono',
        store=False
    )

    partner_address = fields.Char(
        string='Dirección',
        compute='_compute_partner_address',
        store=False
    )

    dte_x_zona = fields.Boolean(
        string="DTEs de la zona",
        compute='_compute_dte_x_zona',
        search='_search_dte_x_zona'
    )

    def _compute_partner_address(self):
        for move in self:
            partner = move.partner_id
            parts = []
            if partner.street:
                parts.append(partner.street)
            if partner.street2:
                parts.append(partner.street2)
            move.partner_address = ', '.join(parts)

    @api.constrains('dispatch_route_id')
    def _check_unique_route(self):
        for move in self:
            if move.dispatch_route_id:
                count = self.search_count([
                    ('id', '=', move.id),
                    ('dispatch_route_id', '!=', False),
                ])
                if count > 1:
                    raise ValidationError(_("El documento electrónico ya está asignado a una ruta."))

    def _compute_dte_x_zona(self):
        for rec in self:
            rec.dte_x_zona = False

    def _search_dte_x_zona(self, operator, value):
        _logger.info("[DTE x Zona] search ejecutado")

        route_id = self.env.context.get('default_dispatch_route_id')
        _logger.info("[DTE x Zona] default_dispatch_route_id=%s", route_id)

        if not route_id:
            _logger.warning("[DTE x Zona] No hay ruta en contexto")
            return [('id', '=', False)]

        route = self.env['dispatch.route'].browse(route_id)
        if not route.exists() or not route.zone_id:
            _logger.warning("[DTE x Zona] Ruta o zona inexistente")
            return [('id', '=', False)]

        municipios = route.zone_id.zone_line_ids.mapped('munic_ids')
        _logger.info("[DTE x Zona] Municipios IDs=%s", municipios.ids)

        if not municipios:
            _logger.warning("[DTE x Zona] La zona no tiene municipios")
            return [('id', '=', False)]

        domain = [
            ('dispatch_route_id', '=', False),
            ('move_type', 'in', (constants.OUT_INVOICE, constants.OUT_REFUND)),
            ('state', '=', 'posted'),
            ('payment_state', 'not in', (constants.PAID, constants.IN_PAYMENT)),
            ('partner_id.munic_id', '!=', False),
            ('partner_id.munic_id', 'in', municipios.ids),
        ]

        _logger.info("[DTE x Zona] Domain retornado=%s", domain)
        return domain
