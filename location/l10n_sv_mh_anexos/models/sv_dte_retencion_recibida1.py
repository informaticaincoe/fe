# -*- coding: utf-8 -*-
from odoo import fields, models, api
import logging
import re
import io
import base64
from datetime import date
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import config_utils
    from odoo.addons.common_utils.utils import constants

    _logger.info("SIT Modulo config_utils [hacienda ws-account_move]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None


class svDteRetencionRecibida1(models.Model):
    _inherit = 'sv.dte.retencion.recibida1'

    invoice_date = fields.Date(
        string="Fecha (alias)",
        related='fecha_documento',
        store=False,
        readonly=True,
    )

    nit_company = fields.Char(
        string="NIT o NRC cliente",  # cambia el label si prefieres NIT de compañía
        compute='_compute_get_nit_company',
        readonly=True,
        store=False,
    )

    @api.depends('factura_relacionada_id')
    def _compute_get_nit_company(self):
        for rec in self:
            move = rec.factura_relacionada_id
            # Si quieres NIT del CLIENTE:
            rec.nit_company = move.partner_id.vat if move and move.partner_id else False
            # Si quieres NIT de la COMPAÑÍA emisora:
            # rec.nit_company = move.company_id.vat if move and move.company_id else False

            _logger.info("factura_relacionada_id=%s, nit_company=%s", move and move.id, rec.nit_company)