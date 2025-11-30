##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.tools import float_repr
from odoo.addons.l10n_sv_haciendaws_fe.afip_utils import get_invoice_number_from_response
import base64
import pyqrcode
import qrcode
import os
from PIL import Image
import io


base64.encodestring = base64.encodebytes
import json
import requests
import logging
import sys
import traceback
from datetime import datetime
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import config_utils
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils [hacienda fex-account_move]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None
    constants = None

class AccountMove(models.Model):

    _inherit = "account.move"

    tipoItemEmisor = fields.Many2one('account.move.tipo_item.field', string="Tipo de Item Emisor")
    sale_order_id = fields.Many2one('sale.order', string='Orden de Venta', compute='_compute_sale_order', store=False)
    recinto_sale_order = fields.Many2one('account.move.recinto_fiscal.field' )

    def _compute_sale_order(self):
        for rec in self:
            if rec.company_id.sit_facturacion and rec.move_type in (constants.OUT_INVOICE, constants.OUT_REFUND):
                sale_orders = rec.invoice_line_ids.mapped('sale_line_ids.order_id')
                rec.sale_order_id = sale_orders[:1] if sale_orders else False

    def action_post(self):
        sit_import_dte_json = self.env.context.get('sit_import_dte_json', False)
        _logger.info("SIT Action post FEX. %s | sit_import_dte_json=%s", self, sit_import_dte_json)

        # Si FE está desactivada → comportamiento estándar de Odoo
        invoices = self.filtered(lambda inv: inv.move_type in (constants.OUT_INVOICE, constants.OUT_REFUND, constants.IN_INVOICE, constants.IN_REFUND))
        if not invoices:
            # Si no hay facturas, llamar al método original sin hacer validaciones DTE
            return super().action_post()

        if not self.env.company.sit_facturacion:
            return super().action_post()

        # FE activa → aplica tus validaciones extra solo en facturacion de ventas y luego deja que Odoo postee
        for rec in self:
            tipo_doc = rec.journal_id.sit_tipo_documento
            es_venta = rec.move_type in (constants.OUT_INVOICE, constants.OUT_REFUND)

            # Solo ejecutar validaciones si es venta y el código del DTE es 11 (Factura de Exportación)
            if es_venta and tipo_doc and tipo_doc.codigo == constants.COD_DTE_FEX:
                if not rec.tipoItemEmisor:
                    raise ValidationError("El campo 'Tipo de Ítem Emisor' es obligatorio para facturas de exportación (11).")
                if not rec.invoice_incoterm_id:
                    raise ValidationError("Debe seleccionar un INCOTERM para facturas de exportación (11).")
                if not rec.partner_id.country_id:
                    raise ValidationError("El receptor debe tener un país seleccionado.")
                if not rec.sit_regimen:
                    raise ValidationError("Debe seleccionar un régimen de exportación.")
                if not sit_import_dte_json and not rec.sale_order_id.recintoFiscal:
                    raise ValidationError("Debe seleccionar un recinto fiscal.")

                # OJO: si 'constants' no cargó, evita acceder a atributos
                if (constants and rec.partner_id.l10n_latam_identification_type_id
                        and rec.partner_id.l10n_latam_identification_type_id.codigo == constants.COD_TD_DUI):
                    raise ValidationError("Cliente no aplica.")

                # Cuenta seguro/flete
                company = rec.company_id
                cuenta_exportacion = company.account_exportacion_id
                if not cuenta_exportacion:
                    cuenta = config_utils.get_config_value(self.env, 'cuenta_exportacion', self.company_id.id) if config_utils else False
                    if cuenta:
                        cuenta = cuenta.strip()
                        cuenta_exportacion = self.env['account.account'].search([('code', '=', cuenta)], limit=1)
                    if not cuenta_exportacion:
                        raise UserError(
                            "Debe configurar la cuenta contable para seguro y flete. "
                            "Hágalo en Ajustes de la Compañía o asigne una cuenta con código '450000'."
                        )
                    company.write({'account_exportacion_id': cuenta_exportacion.id})

                if not rec.invoice_date:
                    raise ValidationError("Debe seleccionar la fecha de la Factura.")

                if not rec.invoice_incoterm_id:
                    raise ValidationError("Es obligatorio seleccionar un Incoterm.")

                if rec.invoice_incoterm_id and not rec.invoice_incoterm_id.codigo_mh:
                    raise ValidationError("El Incoterm seleccionado no tiene Código de Hacienda. Verifique que los códigos estén actualizados.")

        return super().action_post()

    #---------------------------------------------------------------------------------------------
    # Exportacion
    #---------------------------------------------------------------------------------------------
    def check_parametros_linea_firmado_fex(self, line_temp):
        """Valida líneas solo si la FE está activa; si está apagada, no bloquea."""
        if self.move_type in (constants.IN_INVOICE, constants.IN_REFUND):
            tipo_doc = self.journal_id.sit_tipo_documento
            if not tipo_doc or tipo_doc.codigo != constants.COD_DTE_FSE or (tipo_doc.codigo == constants.COD_DTE_FSE and not move.company_id.sit_facturacion):
                _logger.info("Omitiendo validación de línea en %s: tipo=%s, codigo_dte=%s", self._name, move_type, codigo_dte)
                return None

        if not self.env.company.sit_facturacion:
            _logger.info("FE OFF: omitiendo check_parametros_linea_firmado_fex en %s", self._name)
            return None

        if not line_temp.get("codigo"):
            raise UserError(_('El CODIGO del producto  %s no está definido.') % line_temp.get("descripcion"))
        if not line_temp.get("cantidad"):
            raise UserError(_('La CANTIDAD del producto  %s no está definida.') % line_temp.get("descripcion"))
        if not line_temp.get("precioUni"):
            raise UserError(_('El PRECIO UNITARIO del producto  %s no está definido.') % line_temp.get("descripcion"))
        if not line_temp.get("uniMedida"):
            raise UserError(_('La UNIDAD DE MEDIDA del producto  %s no está definida.') % line_temp.get("descripcion"))
        return None
