# -*- coding: utf-8 -*-
from odoo import fields, models, api
import logging
import base64

_logger = logging.getLogger(__name__)


class ReportAccountMoveConsumidorFinalAgrupado(models.Model):
    _name = "report.account.move.consumidor.final.agrupado"
    _description = "Facturas consumidor final agrupadas por día, tipo y clase de documento"
    _auto = False

    invoice_date = fields.Date("Fecha", readonly=True)

    hacienda_codigoGeneracion_identificacion = fields.Char("Codigo generación", readonly=True)

    # nuevo: incluir journal_id
    journal_id = fields.Many2one(
        "account.journal",
        string="Diario",
        readonly=True
    )

    codigo_tipo_documento = fields.Char(
        string="Código tipo documento",
        readonly=True
    )

    name = fields.Char(
        string="Nùmero de control",
        readonly=True
    )

    codigo_tipo_documento_display = fields.Char(
        string="Tipo de documento",
        compute='_compute_codigo_tipo_documento_display',
        store=False
    )

    clase_documento_id = fields.Many2one(
        comodel_name="account.clasificacion.facturacion",
        string="Clasificación",
        readonly=True,
    )

    clase_documento = fields.Char(
        string="Clase de documento",
        compute='_compute_get_clase_documento',
        readonly=True,
        store=False,
    )

    clase_documento_display = fields.Char(
        string="Clase de documento",
        compute='_compute_get_clase_documento_display',
        readonly=True,
        store=False,
    )

    numero_resolucion_consumidor_final = fields.Char(
        string="Clase de documento",
        compute='_compute_get_numero_resolucion_consumidor_final',
        readonly=True,
        store=False,
    )



    numero_control_interno_del = fields.Char(
        string="Numero de control interno DEL",
        readonly=True,
        store=False,
        compute='_compute_get_numero_control_documento_interno_del',
    )

    numero_control_interno_al = fields.Char(
        string="Numero de control interno AL",
        readonly=True,
        store=False,
        compute='_compute_get_numero_control_documento_interno_al',
    )



    numero_documento_del = fields.Char(
        compute='_compute_get_numero_documento_del',
    )

    numero_documento_al = fields.Char(
        compute='_compute_get_numero_documento_al',
    )


    # hacienda_selloRecibido = fields.Char(
    #     string="Sello recibido",
    #     readonly=True,
    #     store=True
    # )

    hacienda_selloRecibido = fields.Char(
        string="Sello Recibido",
        compute="_compute_hacienda_selloRecibido",
        store=False,
    )

    @api.depends('name', 'invoice_date')
    def _compute_hacienda_selloRecibido(self):
        for record in self:
            move = self.env['account.move'].search([
                ('invoice_date', '=', record.invoice_date),
                ('name', '=', record.name)
            ], order='invoice_date ASC', limit=1)
            record.hacienda_selloRecibido = move.hacienda_selloRecibido or ''

    cantidad_facturas = fields.Integer("Cantidad de facturas", readonly=True)

    monto_total_operacion = fields.Monetary("Monto total operación", readonly=True)
    monto_total_impuestos = fields.Monetary("IVA operación", readonly=True)
    total_exento = fields.Monetary("Ventas exentas", readonly=True)
    total_no_sujeto = fields.Monetary("Ventas no sujetas", readonly=True)
    total_gravado = fields.Monetary("Ventas gravadas", readonly=True)
    total_operacion = fields.Monetary("Total de ventas", readonly=True)

    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)

    @api.depends('name')
    def _compute_get_clase_documento(self):
        for record in self:
            if record.name and record.name.startswith("DTE"):
                record.clase_documento = '4'
            else:
                record.clase_documento = '1'

    @api.depends('clase_documento')
    def _compute_get_clase_documento_display(self):
        for record in self:
            if record.clase_documento == '4':
                record.clase_documento_display = '4. Documento tributario electrónico (DTE)'
            else:
                record.clase_documento_display = '1. Impreso por imprenta o tiquetes'

    @api.depends('codigo_tipo_documento', 'journal_id')
    def _compute_codigo_tipo_documento_display(self):
        for record in self:
            codigo = record.codigo_tipo_documento or ""
            nombre = record.journal_id.name or ""
            record.codigo_tipo_documento_display = f"{codigo} {nombre}".strip()

    @api.depends('codigo_tipo_documento', 'journal_id')
    def _compute_get_numero_resolucion_consumidor_final(self):
        for record in self:
            record.numero_resolucion_consumidor_final = record.name

    @api.depends( )
    def _compute_get_numero_control_documento_interno_del(self):
        for record in self:
            move = self.env['account.move'].search([
                ('invoice_date', '=', record.invoice_date)
            ], order='invoice_date ASC', limit=1)
            if record.clase_documento == "1":
                record.numero_control_interno_del = move.hacienda_codigoGeneracion_identificacion
            else:
                record.numero_control_interno_del = ""

    @api.depends()
    def _compute_get_numero_control_documento_interno_al(self):
        for record in self:
            move = self.env['account.move'].search([
                ('invoice_date', '=', record.invoice_date)
            ], order='invoice_date DESC', limit=1)
            if record.clase_documento == "1":
                record.numero_control_interno_al = move.hacienda_codigoGeneracion_identificacion
            else:
                record.numero_control_interno_al = ""

    @api.depends('invoice_date', 'journal_id', 'codigo_tipo_documento')
    def _compute_get_numero_documento_del(self):
        for record in self:
            move_del = self.env['account.move'].search([
                ('invoice_date', '=', record.invoice_date),
                ('journal_id', '=', record.journal_id.id),
                ('codigo_tipo_documento', '=', record.codigo_tipo_documento)
            ], order='name ASC', limit=1)

            record.numero_documento_del = move_del.hacienda_codigoGeneracion_identificacion or ''
            _logger.info("➡️ DEL grupo [%s - %s - %s] → %s",
                         record.invoice_date, record.journal_id.display_name, record.codigo_tipo_documento,
                         move_del.name)

    @api.depends('invoice_date', 'journal_id', 'codigo_tipo_documento')
    def _compute_get_numero_documento_al(self):
        for record in self:
            move_al = self.env['account.move'].search([
                ('invoice_date', '=', record.invoice_date),
                ('journal_id', '=', record.journal_id.id),
                ('codigo_tipo_documento', '=', record.codigo_tipo_documento)
            ], order='name DESC', limit=1)

            record.numero_documento_al = move_al.hacienda_codigoGeneracion_identificacion or ''
            _logger.info("⬅️ AL grupo [%s - %s - %s] → %s",
                         record.invoice_date, record.journal_id.display_name, record.codigo_tipo_documento,
                         move_al.name)

    def init(self):
        self.env.cr.execute("""
                            CREATE
                            OR REPLACE VIEW report_account_move_consumidor_final_agrupado AS (
                SELECT
                    MIN(am.id) AS id,
                    am.invoice_date::date AS invoice_date,
                    am.journal_id,
                    am.codigo_tipo_documento,
                    am.clase_documento_id,

                    MIN(am.name) AS name,

                    COUNT(am.id) AS cantidad_facturas,

                    -- ✅ Primera y última factura del día
                    MIN(am.name) AS numero_resolucion_consumidor_final,
                    --MIN(am.hacienda_codigoGeneracion_identificacion) AS numero_documento_del,
                    --MAX(am.hacienda_codigoGeneracion_identificacion) AS numero_documento_al,

                    -- ✅ Si quieres también por número de control interno
                    MIN(am.name) AS numero_control_interno_del,
                    MAX(am.name) AS numero_control_interno_al,

                    -- Totales
                    SUM(am.total_operacion) AS monto_total_operacion,
                    SUM(am.amount_tax) AS monto_total_impuestos,
                    SUM(am.total_exento) AS total_exento,
                    SUM(am.total_no_sujeto) AS total_no_sujeto,
                    SUM(am.total_gravado) AS total_gravado,
                    SUM(am.total_operacion) AS total_operacion,

                    (SELECT id FROM res_currency WHERE name='USD' LIMIT 1) as currency_id
                FROM account_move am
                WHERE am.codigo_tipo_documento IN ('01','11','03','05')
                GROUP BY am.invoice_date::date, am.journal_id, am.codigo_tipo_documento, am.clase_documento_id
            )
                            """)

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

