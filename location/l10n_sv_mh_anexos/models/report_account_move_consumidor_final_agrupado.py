# -*- coding: utf-8 -*-
from odoo import fields, models, api
import logging
import base64
from datetime import date

_logger = logging.getLogger(__name__)


class ReportAccountMoveConsumidorFinalAgrupado(models.Model):
    _name = "report.account.move.consumidor.final.agrupado"
    _description = "Facturas consumidor final agrupadas por día, tipo y clase de documento"
    _auto = False

    hacienda_estado = fields.Char(string="Hacienda estado", readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)

    invoice_date = fields.Date("Fecha", readonly=True)

    hacienda_codigoGeneracion_identificacion = fields.Char("Codigo generación", readonly=True)
    total_gravado = fields.Monetary("Total gravado", readonly=True)

    exportaciones_de_servicio = fields.Monetary(
        string="Exportaciones de servicio",
        compute="_compute_get_exportaciones_de_servicio",
        store=False,
        readonly=True,
    )



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

    hacienda_selloRecibido = fields.Char(
        string="Sello Recibido",
        compute="_compute_hacienda_selloRecibido",
    )

    sit_evento_invalidacion = fields.Integer(
        string="Evento de invalidacion",
        readonly=True,
    )


    exportaciones_dentro_centroamerica = fields.Monetary(
        string="Exportaciones dentro del area de centroamerica",
        compute='_compute_get_exportaciones_dentro_centroamerica',
        readonly=True,
        store=False,
    )

    exportaciones_fuera_centroamerica = fields.Monetary(
        string="Exportaciones fuera del area de centroamerica",
        compute='_compute_get_exportaciones_fuera_centroamerica',
        readonly=True,
        store=False,
    )

    ventas_tasa_cero = fields.Monetary(
        string="Ventas a zonas francas y DPA (tasa cero)",
        compute='_compute_get_ventas_tasa_cero',
        readonly=True,
        store=False,
    )

    ventas_exentas_no_sujetas = fields.Monetary(
        string="Ventas internas exentas no sujetas a proporcionalidad",
        compute='_compute_get_ventas_exentas_no_sujetas',
        readonly=True,
        store=False,
    )

    numero_anexo = fields.Char(
        string="Número del anexo",
        compute='_compute_get_numero_anexo',
        readonly=True,
    )

    tipo_ingreso_id = fields.Many2one(
        comodel_name="account.tipo.ingreso",
        string="Tipo de Ingreso"
    )

    tipo_ingreso_display = fields.Char(
        string="Tipo de Ingreso",
        compute="_compute_tipo_ingreso_display",
        store=False
    )

    tipo_ingreso_codigo = fields.Char(
        string="Tipo ingreso codigo",
        compute='_compute_get_tipo_ingreso_codigo',
        readonly=True,
        store=False,
    )

    tipo_operacion = fields.Many2one(
        comodel_name="account.tipo.operacion",
        string="Tipo Operacion"
    )

    tipo_operacion_codigo = fields.Char(
        string="Tipo operacion codigo",
        compute='_compute_get_tipo_operacion_codigo',
        readonly=True,
        store=False,
    )

    tipo_operacion_display = fields.Char(
        string="Tipo de Operación",
        compute="_compute_tipo_operacion_display",
        store=False
    )

    # tipo_operacion_renta = fields.Monetary(
    #     string="Tipo de operacion (renta)",
    #     compute='_compute_get_tipo_operacion_renta',
    #     readonly=True,
    #     store=False,
    # )

    numero_maquina_registradora = fields.Char(
        string="Numero de maquina registradora",
        compute='_compute_get_numero_maquina_registradora',
        readonly=True,
        store=False,
    )

    ventas_cuenta_terceros = fields.Char(
        string="ventas a cuenta de terceros no domiciliados",
        compute='_compute_get_ventas_cuenta_terceros',
        readonly=True,
        store=False,
    )

    @api.depends('journal_id')
    def _compute_get_numero_maquina_registradora(self):
        for record in self:
            record.numero_maquina_registradora = ''

    @api.depends('journal_id')
    def _compute_get_ventas_cuenta_terceros(self):
        for record in self:
            record.ventas_cuenta_terceros = 0.00

    @api.depends('invoice_date', 'journal_id', 'codigo_tipo_documento')
    def _compute_get_tipo_ingreso_codigo(self):
        Move = self.env['account.move']
        limite = date(2025, 1, 1)
        for rec in self:
            rec.tipo_ingreso_codigo = "0"  # fallback
            if not (rec.invoice_date and rec.journal_id and rec.codigo_tipo_documento):
                continue

            mv = Move.search([
                ('invoice_date', '=', rec.invoice_date),
                ('journal_id', '=', rec.journal_id.id),
                ('codigo_tipo_documento', '=', rec.codigo_tipo_documento),
                ('state', '=', 'posted'),
            ], order='name ASC', limit=1)

            if rec.invoice_date >= limite and mv and mv.tipo_ingreso_id:
                cod = getattr(mv.tipo_ingreso_id, 'codigo', None)
                rec.tipo_ingreso_codigo = str(cod) if cod is not None else "0"

    @api.depends('invoice_date', 'journal_id', 'codigo_tipo_documento')
    def _compute_tipo_ingreso_display(self):
        Move = self.env['account.move']
        limite = date(2025, 1, 1)
        for rec in self:
            rec.tipo_ingreso_display = "0"  # fallback
            if not (rec.invoice_date and rec.journal_id and rec.codigo_tipo_documento):
                continue

            mv = Move.search([
                ('invoice_date', '=', rec.invoice_date),
                ('journal_id', '=', rec.journal_id.id),
                ('codigo_tipo_documento', '=', rec.codigo_tipo_documento),
                ('state', '=', 'posted'),
            ], order='name ASC', limit=1)

            if rec.invoice_date >= limite and mv and mv.tipo_ingreso_id:
                codigo = getattr(mv.tipo_ingreso_id, 'codigo', None) or ''
                valor = getattr(mv.tipo_ingreso_id, 'valor', None) or ''
                rec.tipo_ingreso_display = (f"{codigo}. {valor}".strip('. ').strip()) if (codigo or valor) else "0"

    @api.depends('name', 'invoice_date')
    def _compute_hacienda_selloRecibido(self):
        for record in self:
            move = self.env['account.move'].search([
                ('invoice_date', '=', record.invoice_date),
                ('name', '=', record.name)
            ], order='invoice_date ASC', limit=1)
            record.hacienda_selloRecibido = move.hacienda_selloRecibido or ''

    total_gravado_local = fields.Monetary(
        string="Ventas gravadas locales",
        compute="_compute_total_gravado_local",
        store=False,
    )

    cantidad_facturas = fields.Integer("Cantidad de facturas", readonly=True)

    monto_total_impuestos = fields.Monetary("IVA operación", readonly=True)
    total_exento = fields.Monetary("Ventas exentas", readonly=True)
    total_no_sujeto = fields.Monetary("Ventas no sujetas", readonly=True)
    total_operacion = fields.Monetary("Total de ventas", readonly=True)
    total_operacion_suma = fields.Monetary(
        string="Total operación",
        compute="_compute_total_operacion_suma",
        currency_field="currency_id",
        readonly=True,
        store=False,  # en _auto=False normalmente lo dejamos en memoria
    )

    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)

    @api.depends('total_operacion', 'currency_id')
    def _compute_total_operacion_suma(self):
        for rec in self:
            rec.total_operacion_suma = (rec.total_operacion or 0.0)

    @api.depends('name')
    def _compute_get_clase_documento(self):
        for record in self:
            if record.name and record.name.startswith("DTE"):
                record.clase_documento = '4'
            else:
                record.clase_documento = '1'

    @api.depends('name','invoice_date', 'journal_id', 'codigo_tipo_documento')
    def _compute_total_gravado_local(self):
        Move = self.env['account.move']
        for rec in self:
            if not rec.invoice_date or not rec.journal_id:
                rec.total_gravado_local = 0.0
                continue
            moves = Move.search([
                ('invoice_date', '=', rec.invoice_date),
                ('journal_id', '=', rec.journal_id.id),
                ('partner_id.country_id.code', '=', 'SV'),
            ])
            rec.total_gravado_local = sum(m.total_gravado or 0.0 for m in moves)

    @api.depends('invoice_date', 'journal_id', 'codigo_tipo_documento')
    def _compute_get_exportaciones_dentro_centroamerica(self):
        Move = self.env['account.move']
        CA = ['GT', 'HN', 'NI', 'CR', 'PA']
        for rec in self:
            if rec.codigo_tipo_documento != '11' or not rec.invoice_date or not rec.journal_id:
                rec.exportaciones_dentro_centroamerica = 0.0
                continue
            moves = Move.search([
                ('invoice_date', '=', rec.invoice_date),
                ('journal_id', '=', rec.journal_id.id),
                ('codigo_tipo_documento', '=', '11'),
                ('partner_id.country_id.code', 'in', CA),
            ])
            rec.exportaciones_dentro_centroamerica = sum(m.total_gravado or 0.0 for m in moves)

    @api.depends('invoice_date', 'journal_id', 'codigo_tipo_documento')
    def _compute_get_exportaciones_fuera_centroamerica(self):
        Move = self.env['account.move']
        NOT_CA = ['SV', 'GT', 'HN', 'NI', 'CR', 'PA']
        for rec in self:
            if rec.codigo_tipo_documento != '11' or not rec.invoice_date or not rec.journal_id:
                rec.exportaciones_fuera_centroamerica = 0.0
                continue
            moves = Move.search([
                ('invoice_date', '=', rec.invoice_date),
                ('journal_id', '=', rec.journal_id.id),
                ('codigo_tipo_documento', '=', '11'),
                ('partner_id.country_id.code', 'not in', NOT_CA),
            ])
            rec.exportaciones_fuera_centroamerica = sum(m.total_gravado or 0.0 for m in moves)

    @api.depends('invoice_date', 'journal_id', 'codigo_tipo_documento')
    def _compute_get_exportaciones_de_servicio(self):
        Move = self.env['account.move']
        Line = self.env['account.move.line']
        has_detailed = 'detailed_type' in self.env['product.product']._fields

        for rec in self:
            if rec.codigo_tipo_documento != '11' or not rec.invoice_date or not rec.journal_id:
                rec.exportaciones_de_servicio = 0.0
                continue

            move_ids = Move.search([
                ('invoice_date', '=', rec.invoice_date),
                ('journal_id', '=', rec.journal_id.id),
                ('codigo_tipo_documento', '=', '11'),
            ]).ids
            if not move_ids:
                rec.exportaciones_de_servicio = 0.0
                continue

            # Dominio base
            dom = [
                ('move_id', 'in', move_ids),
                ('product_id', '!=', False),
            ]
            # Filtro por servicio según versión
            if has_detailed:
                dom.append(('product_id.detailed_type', '=', 'service'))
            else:
                dom.append(('product_id.product_tmpl_id.type', '=', 'service'))

            data = Line.read_group(dom, ['price_subtotal:sum'], [])
            rec.exportaciones_de_servicio = (data and data[0].get('price_subtotal_sum') or 0.0)

    @api.depends('journal_id')
    def _compute_get_ventas_tasa_cero(self):
        for record in self:
            record.ventas_tasa_cero = 0.00

    @api.depends('invoice_date', 'journal_id', 'codigo_tipo_documento')
    def _compute_tipo_operacion_display(self):
        Move = self.env['account.move']
        limite = date(2025, 1, 1)
        for rec in self:
            rec.tipo_operacion_display = "0"  # fallback
            if not (rec.invoice_date and rec.journal_id and rec.codigo_tipo_documento):
                continue

            mv = Move.search([
                ('invoice_date', '=', rec.invoice_date),
                ('journal_id', '=', rec.journal_id.id),
                ('codigo_tipo_documento', '=', rec.codigo_tipo_documento),
                ('state', '=', 'posted'),
            ], order='name ASC', limit=1)

            if rec.invoice_date >= limite and mv and mv.tipo_operacion:
                codigo = getattr(mv.tipo_operacion, 'codigo', None) or ''
                valor = getattr(mv.tipo_operacion, 'valor', None) or ''
                rec.tipo_operacion_display = (f"{codigo}. {valor}".strip('. ').strip()) if (codigo or valor) else "0"

    @api.depends('invoice_date', 'journal_id', 'codigo_tipo_documento')
    def _compute_get_tipo_operacion_codigo(self):
        Move = self.env['account.move']
        limite = date(2025, 1, 1)
        for rec in self:
            rec.tipo_operacion_codigo = "0"  # fallback
            if not (rec.invoice_date and rec.journal_id and rec.codigo_tipo_documento):
                continue

            mv = Move.search([
                ('invoice_date', '=', rec.invoice_date),
                ('journal_id', '=', rec.journal_id.id),
                ('codigo_tipo_documento', '=', rec.codigo_tipo_documento),
                ('state', '=', 'posted'),
            ], order='name ASC', limit=1)

            if rec.invoice_date >= limite and mv and mv.tipo_operacion:
                cod = getattr(mv.tipo_operacion, 'codigo', None)
                rec.tipo_operacion_codigo = str(cod) if cod is not None else "0"

    # @api.depends('journal_id')
    # def _compute_get_tipo_operacion_renta(self):
    #     for record in self:
    #         move = self.env['account.move'].search([
    #             ('invoice_date', '=', record.invoice_date)
    #         ], order='invoice_date ASC', limit=1)
    #
    #         _logger.info("TIPO OPERACION %s", move.tipo_operacion)
    #
    #         record.tipo_operacion = move.tipo_operacion

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

    @api.depends('journal_id')
    def _compute_get_numero_anexo(self):
        for record in self:
            ctx = self.env.context
            if ctx.get('numero_anexo'):
                record.numero_anexo = str(ctx['numero_anexo'])

    @api.depends('journal_id')
    def _compute_get_ventas_exentas_no_sujetas(self):
        for record in self:
            record.ventas_exentas_no_sujetas = 0.00

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW report_account_move_consumidor_final_agrupado AS (
                SELECT
                    MIN(am.id)                      AS id,
                    am.company_id                   AS company_id,
                    am.invoice_date::date           AS invoice_date,
                    am.journal_id                   AS journal_id,
                    am.codigo_tipo_documento        AS codigo_tipo_documento,
                    am.clase_documento_id           AS clase_documento_id,

                    MIN(am.hacienda_estado)         AS hacienda_estado,
                    MIN(am.name)                    AS name,
                    MIN(am."hacienda_selloRecibido")              AS "hacienda_selloRecibido",
                    MIN(am."sit_evento_invalidacion")    AS "sit_evento_invalidacion",
                    MIN(am.tipo_operacion)  AS tipo_operacion,
                    COUNT(am.id)                    AS cantidad_facturas,

                    -- rangos del día
                    MIN(am.name)                    AS numero_resolucion_consumidor_final,
                    MIN(am.name)                    AS numero_control_interno_del,
                    MAX(am.name)                    AS numero_control_interno_al,

                    -- totales
                    SUM(am.amount_tax)              AS monto_total_impuestos,
                    SUM(am.total_exento)            AS total_exento,
                    SUM(am.total_no_sujeto)         AS total_no_sujeto,
                    SUM(am.total_gravado)           AS total_gravado,
                    SUM(am.total_operacion)         AS total_operacion,

                    (SELECT id FROM res_currency WHERE name='USD' LIMIT 1) AS currency_id
                FROM account_move am
                WHERE am.state = 'posted'
                  AND am.invoice_date IS NOT NULL
                  AND am.codigo_tipo_documento IN ('01','11')
                  AND am.move_type IN ('out_invoice','out_refund')
                  AND am.hacienda_estado IN ('PROCESADO')
                  AND am.sit_evento_invalidacion IS NULL
                  AND am."hacienda_selloRecibido" IS NOT NULL
                  
                GROUP BY
                    am.company_id,
                    am.invoice_date::date,
                    am.journal_id,
                    am.codigo_tipo_documento,
                    am.clase_documento_id
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

