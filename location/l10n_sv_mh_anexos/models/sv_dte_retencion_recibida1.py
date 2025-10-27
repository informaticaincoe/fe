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

    sello_recepcion = fields.Char(string="Sello Recepcion", default=False, required=True)

    move_type = fields.Char(
        string="Tipo de documento",
        compute="_compute_move_type",
        readonly=True,
        store=False,
    )

    invoice_date = fields.Date(
        string="Fecha (alias)",
        compute="_compute_get_invoice_date",
        store=False,
        readonly=True,
    )

    fecha_documento = fields.Date(string="Fecha de documento", default=False, required=True)

    nit_company = fields.Char(
        string="NIT o NRC cliente",  # cambia el label si prefieres NIT de compañía
        compute='_compute_get_nit_company',
        readonly=True,
        store=False,
    )

    nit_cliente = fields.Char(
        string="NIT cliente",
        compute='_compute_get_nit',
        readonly=True,
        store=False,
    )

    dui_proveedor = fields.Char(string="Dui proveedor", compute='_compute_dui_proveedor')

    invoice_date = fields.Date(
        string="Fecha",
        readonly=True,
    )

    sit_tipo_documento = fields.Char(
        string="Tipo de documento",
        compute="_compute_sit_tipo_documento",
        readonly=True,
        store=False
    )

    has_sello_anulacion = fields.Boolean(
        string="Tiene Sello Anulación",
        compute="_compute_has_sello_anulacion",
        search="_search_has_sello_anulacion",
        store=False,
        readonly=True,
        index=True,
    )

    sello_recepcion = fields.Char("Sello recepcion")

    numero_documento = fields.Char("Numero documento")
    codigo_generacion = fields.Char("Código generación")

    numero_anexo = fields.Char(
        string="Número del anexo",
        compute='_compute_get_numero_anexo',
        readonly=True,
    )

    total_monto_sujeto = fields.Float(string="Monto sujeto")
    total_iva_retenido = fields.Float(string="Monto retencion 1%")

    @api.depends('factura_relacionada_id')
    def _compute_move_type(self):
        for record in self:
            move = record.factura_relacionada_id
            record.move_type = move.move_type

    @api.depends('factura_relacionada_id.partner_id.vat')
    def _compute_get_nit(self):
        for record in self:
            move = record.factura_relacionada_id
            record.nit_cliente = move.partner_id.vat if move and move.partner_id and move.partner_id.vat else ''

    @api.depends('factura_relacionada_id')
    def _compute_get_invoice_date(self):
        for record in self:
            move = record.factura_relacionada_id
            record.invoice_date = move.invoice_date

    @api.depends('factura_relacionada_id')
    def _compute_sit_tipo_documento(self):
        for record in self:
            move = record.factura_relacionada_id
            record.sit_tipo_documento = move.sit_tipo_documento_id.codigo

    @api.depends('factura_relacionada_id')
    def _compute_get_nit_company(self):
        for rec in self:
            move = rec.factura_relacionada_id
            # Si quieres NIT del CLIENTE:
            rec.nit_company = move.partner_id.vat if move and move.partner_id else False
            # Si quieres NIT de la COMPAÑÍA emisora:
            # rec.nit_company = move.company_id.vat if move and move.company_id else False

            _logger.info("factura_relacionada_id=%s, nit_company=%s", move and move.id, rec.nit_company)

    @api.depends('factura_relacionada_id')
    def _compute_has_sello_anulacion(self):
        for m in self:
            move = m.factura_relacionada_id
            inv = move.sit_evento_invalidacion
            m.has_sello_anulacion = bool(inv and inv.hacienda_selloRecibido_anulacion)

    def _search_has_sello_anulacion(self, operator, value):
        """
        Busca por el sello de anulación del DTE en el MOVE relacionado.
        True  -> tiene evento de invalidación con sello
        False -> no tiene evento o el evento no tiene sello
        """
        target = bool(value)

        domain_true = [
            ('factura_relacionada_id.sit_evento_invalidacion.hacienda_selloRecibido_anulacion', '!=', False)
        ]
        domain_false = ['|',
                        ('factura_relacionada_id.sit_evento_invalidacion', '=', False),
                        ('factura_relacionada_id.sit_evento_invalidacion.hacienda_selloRecibido_anulacion', '=', False),
                        ]

        if operator == '=':
            return domain_true if target else domain_false
        elif operator == '!=':
            return domain_false if target else domain_true
        # Fallback: tratar cualquier otro operador como '='
        return domain_true if target else domain_false

    @api.depends('factura_relacionada_id')
    def _compute_get_numero_documento(self):
        limite = date(2022, 11, 1)
        for record in self:
            if record.invoice_date and record.invoice_date < limite:
                record.numero_documento = record.numero_control
            else:
                record.numero_documento = record.codigo_generacion

    @api.depends('factura_relacionada_id')
    def _compute_dui_proveedor(self):
        for record in self:
            move = record.factura_relacionada_id
            if(record.nit_cliente == ""):
                record.dui_proveedor = move.partner_id.dui
            else:
                record.dui_proveedor = ""

    @api.depends('invoice_date')
    def _compute_get_numero_anexo(self):
        for record in self:
            ctx = self.env.context
            if ctx.get('numero_anexo'):
                record.numero_anexo = str(ctx['numero_anexo'])

    def export_csv_from_action(self):
        ctx = self.env.context
        numero_anexo = str(ctx.get("numero_anexo") or "")

        # 1) Si hay selección en la lista
        active_ids = ctx.get("active_ids") or []
        if active_ids:
            recs = self.browse(active_ids)
        else:
            recs = self.search([])

        if not recs:
            _logger.warning("Sin registros para exportar en %s.", self._name)
            return

        # (opcional) recuperar view_id
        view_id = None
        params = ctx.get("params") or {}
        xmlid = params.get("action")
        if xmlid:
            try:
                action = self.env["ir.actions.act_window"]._for_xml_id(xmlid)
                view_id = action.get("view_id") and action["view_id"][0] or None
            except Exception as e:
                _logger.warning("No se pudo resolver view_id: %s", e)

        csv_bytes = self.env["anexo.csv.utils"].generate_csv(
            recs,
            numero_anexo=numero_anexo,
            view_id=view_id,
            include_header=False,
        )

        att = self.env["ir.attachment"].create({
            "name": f"anexo_{numero_anexo or 'reporte'}.csv",
            "type": "binary",
            "datas": base64.b64encode(csv_bytes),
            "res_model": self._name,
            "res_id": False,
            "public": True,
        })
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{att.id}?download=true",
            "target": "self",
        }