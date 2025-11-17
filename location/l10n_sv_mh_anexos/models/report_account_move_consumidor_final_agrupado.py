from odoo import fields, models, api, tools
import logging
import base64
from datetime import date

_logger = logging.getLogger(__name__)


class ReportAccountMoveConsumidorFinalAgrupado(models.TransientModel):
    _name = "report.account.move.consumidor.final.agrupado"
    _description = "Facturas consumidor final agrupadas por día, tipo y clase de documento"

    sit_evento_invalidacion = fields.Many2one(
        'account.move.invalidation',
        string='Evento de invalidación',
        readonly=True,
        ondelete='set null',
        index=True,
    )

    monto_total_operacion = fields.Monetary("Monto total operación")
    clase_documento_display = fields.Char("clase documento display")
    clase_documento_codigo = fields.Char("clase documento display")
    clase_documento_valor = fields.Char("clase documento valor")
    codigo_tipo_documento_codigo = fields.Char("codigo tipo documento codigo")
    codigo_tipo_documento_valor = fields.Char("codigo tipo documento valor")
    codigo_tipo_documento_display = fields.Char("codigo tipo documento display")

    invoice_year = fields.Char(string="Año", compute="_compute_invoice_year", store=False)
    invoice_month = fields.Char(string="Mes", compute="_compute_invoice_month", store=False)

    numero_anexo = fields.Char(
        string="Número del anexo",
        default=lambda self: str(self.env.context.get("numero_anexo", "")),
    )

    @api.depends("invoice_date")
    def _compute_invoice_date_str(self):
        for r in self:
            r.invoice_date_str = r.invoice_date.strftime("%d/%m/%Y") if r.invoice_date else ""

    @api.depends("invoice_date")
    def _compute_invoice_year(self):
        for r in self:
            r.invoice_year = r.invoice_date.strftime("%Y") if r.invoice_date else ""

    @api.depends("invoice_date")
    def _compute_invoice_month(self):
        for r in self:
            r.invoice_month = r.invoice_date.strftime("%m") if r.invoice_date else ""

    has_sello_anulacion = fields.Boolean(
        compute="_compute_has_sello_anulacion",
        search="_search_has_sello_anulacion",
        store=False,
    )

    def _search_has_sello_anulacion(self, operator, value):
        Inv = self.env['account.move.invalidation']
        inv_ids = Inv.search([('hacienda_selloRecibido_anulacion', '!=', False)]).ids
        if (operator, bool(value)) in [('=', True), ('!=', False)]:
            return [('sit_evento_invalidacion', 'in', inv_ids)]
        elif (operator, bool(value)) in [('=', False), ('!=', True)]:
            return ['|', ('sit_evento_invalidacion', '=', False),
                    ('sit_evento_invalidacion', 'not in', inv_ids)]
        _logger.info("datos %s ", self)
        return []

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

    # clase_documento_display = fields.Char(
    #     string="Clase de documento",
    #     compute='_compute_get_clase_documento_display',
    #     readonly=True,
    #     store=False,
    # )

    numero_resolucion_consumidor_final = fields.Char(
        string="Número de resolución"
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

    # numero_anexo = fields.Char(
    #     string="Número del anexo",
    #     compute='_compute_get_numero_anexo',
    #     readonly=True,
    # )

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

    @api.depends('invoice_date', 'journal_id', 'codigo_tipo_documento', 'clase_documento_id')
    def _compute_hacienda_selloRecibido(self):
        Move = self.env['account.move']
        for record in self:
            record.hacienda_selloRecibido = ''

            # Si falta algo clave del grupo, no buscamos nada
            if not record.invoice_date or not record.journal_id or not record.codigo_tipo_documento:
                continue

            domain = [
                ('invoice_date', '=', record.invoice_date),
                ('journal_id', '=', record.journal_id.id),
                ('codigo_tipo_documento', '=', record.codigo_tipo_documento),
                ('state', '=', 'posted'),
            ]

            # Si la agrupación lleva clase_documento_id, filtramos también por eso
            if record.clase_documento_id:
                domain.append(('clase_documento_id', '=', record.clase_documento_id.id))

            # "Primero": por número de documento (name) ascendente
            move = Move.search(domain, order='name ASC, id ASC', limit=1)

            record.hacienda_selloRecibido = move.hacienda_selloRecibido or ''

    total_gravado_local = fields.Monetary(
        string="Ventas gravadas locales",
        compute="_compute_total_gravado_local",
        store=False,
    )

    cantidad_facturas = fields.Integer("Cantidad de facturas", readonly=True)

    serie_documento_consumidor_final = fields.Char("Serie de documento",
                                                   compute="_compute_serie_documento_consumidor_final", readonly=True)

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

    invoice_date_str = fields.Char("Fecha", compute="_compute_invoice_date_str", store=False)

    @api.depends("invoice_date")
    def _compute_invoice_date_str(self):
        for r in self:
            r.invoice_date_str = r.invoice_date.strftime("%d/%m/%Y") if r.invoice_date else ""

    @api.depends('hacienda_selloRecibido')
    def _compute_serie_documento_consumidor_final(self):
        for record in self:
            if record.name and record.name.startswith("DTE"):
                record.serie_documento_consumidor_final = "N/A"
            else:
                record.serie_documento_consumidor_final = record.hacienda_selloRecibido

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

    @api.depends('name', 'invoice_date', 'journal_id', 'codigo_tipo_documento')
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

    @api.depends('clase_documento')
    def _compute_get_clase_documento_display(self):
        for record in self:
            if record.clase_documento == '4':
                record.clase_documento_display = '4. Documento tributario electrónico (DTE)'
            else:
                record.clase_documento_display = '1. Impreso por imprenta o tiquetes'

    @api.depends()
    def _compute_get_numero_control_documento_interno_del(self):
        for record in self:
            move = self.env['account.move'].search([
                ('invoice_date', '=', record.invoice_date)
            ], order='invoice_date ASC', limit=1)
            if record.clase_documento == "4":
                record.numero_control_interno_del = "N/A"
            else:
                record.numero_control_interno_del = move.hacienda_codigoGeneracion_identificacion

    @api.depends()
    def _compute_get_numero_control_documento_interno_al(self):
        for record in self:
            move = self.env['account.move'].search([
                ('invoice_date', '=', record.invoice_date)
            ], order='invoice_date DESC', limit=1)
            if record.clase_documento == "4":
                record.numero_control_interno_al = "N/A"
            else:
                record.numero_control_interno_al = move.hacienda_codigoGeneracion_identificacion

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

    # @api.depends('journal_id')
    # def _compute_get_numero_anexo(self):
    #     for record in self:
    #         ctx = self.env.context
    #         if ctx.get('numero_anexo'):
    #             record.numero_anexo = str(ctx['numero_anexo'])

    @api.depends('journal_id')
    def _compute_get_ventas_exentas_no_sujetas(self):
        for record in self:
            record.ventas_exentas_no_sujetas = 0.00

    # def init(self):
    #     tools.drop_view_if_exists(self.env.cr, 'report_account_move_consumidor_final_agrupado')
    #     self.env.cr.execute("""
    #         CREATE OR REPLACE VIEW report_account_move_consumidor_final_agrupado AS (
    #             SELECT
    #                 MIN(am.id)                      AS id,
    #                 am.company_id                   AS company_id,
    #                 am.invoice_date::date           AS invoice_date,
    #                 am.journal_id                   AS journal_id,
    #                 am.codigo_tipo_documento        AS codigo_tipo_documento,
    #                 am.clase_documento_id           AS clase_documento_id,
    #
    #                 MIN(am.hacienda_estado)         AS hacienda_estado,
    #                 MIN(am.name)                    AS name,
    #                 MIN(am."hacienda_selloRecibido")              AS "hacienda_selloRecibido",
    #                 MIN(am."sit_evento_invalidacion")    AS "sit_evento_invalidacion",
    #                 MIN(am.tipo_operacion)  AS tipo_operacion,
    #                 COUNT(am.id)                    AS cantidad_facturas,
    #
    #                 -- rangos del día
    #                 MIN(am.name)                    AS numero_resolucion_consumidor_final,
    #                 MIN(am.name)                    AS numero_control_interno_del,
    #                 MAX(am.name)                    AS numero_control_interno_al,
    #
    #                 -- totales
    #                 SUM(am.amount_tax)              AS monto_total_impuestos,
    #                 SUM(am.total_exento)            AS total_exento,
    #                 SUM(am.total_no_sujeto)         AS total_no_sujeto,
    #                 SUM(am.total_gravado)           AS total_gravado,
    #                 SUM(am.total_operacion)         AS total_operacion,
    #
    #                 (SELECT id FROM res_currency WHERE name='USD' LIMIT 1) AS currency_id
    #             FROM account_move am
    #             WHERE am.state = 'posted'
    #               AND am.invoice_date IS NOT NULL
    #               AND am.codigo_tipo_documento IN ('01','11')
    #               AND am.move_type IN ('out_invoice','out_refund')
    #               AND am.hacienda_estado IN ('PROCESADO')
    #               AND am.sit_evento_invalidacion IS NULL
    #               AND am."hacienda_selloRecibido" IS NOT NULL
    #
    #             GROUP BY
    #                 am.company_id,
    #                 am.invoice_date::date,
    #                 am.journal_id,
    #                 am.codigo_tipo_documento,
    #                 am.clase_documento_id
    #         )
    #     """)

    @api.model
    def action_open_report(self, *args, **kwargs):

        self.search([]).unlink()

        Move = self.env["account.move"]

        # 1. Ajuste del Dominio
        domain = [
            ("move_type", "=", "out_invoice"),
            ("hacienda_estado", "=", "PROCESADO"),
            ("has_sello_anulacion", "=", False),

            '|',
            ('hacienda_selloRecibido', '!=', False),  # Documentos electrónicos (DTE)
            ('clase_documento_id', '!=', False),  # Documentos impresos (como tus nóminas)
        ]

        # Realizar las operaciones de suma y conteo en los siguientes campos
        agg_fields = [
            "amount_untaxed:sum",
            "amount_tax:sum",
            "id:count",
            "clase_documento_id:min",
            "journal_id",
            "codigo_tipo_documento:min",
            "sit_tipo_documento_id:min",
            "name:min"
        ]

        # 2. Ajuste del Groupby
        # Se añaden journal_id y codigo_tipo_documento para asegurar grupos únicos
        # y para que las computadas que usan estos campos funcionen correctamente.
        groupby = ["invoice_date:day", "clase_documento_id", "journal_id", "codigo_tipo_documento"]

        _logger.info("INICIO: Ejecutando read_group con DOMAIN: %s", domain)
        _logger.info("INICIO: Agrupando por: %s", groupby)

        rows = Move.read_group(
            domain=domain,
            fields=agg_fields,
            groupby=groupby,
            orderby="invoice_date:day",
        )

        _logger.info(": rows del read_group (%s grupos): %s", len(rows), rows)

        for r in rows:
            # ... (Lógica de fechas y año/mes omitida para brevedad) ...

            range_info = r.get("__range", {}).get("invoice_date:day")
            _logger.info(" RRRRRRRR: %s", r)

            if range_info:
                d = fields.Date.to_date(range_info["from"])
            else:
                continue
            numero_anexo = str(self.env.context.get("numero_anexo") or "")

            year = d.year
            month = d.month

            clase_documento_info = r.get("clase_documento_id")
            tipo_documento_info = r.get("sit_tipo_documento_id")

            if clase_documento_info:
                clase_documento_table = self.env["account.clase.documento"]
                _logger.info("DDDD clase_documento_table%s", clase_documento_table)

                domain = [("id", "=", clase_documento_info),]
                agg_fields = ["codigo:min", "valor:min"]

                groupby = ["codigo"]
                rows_clase_documento = clase_documento_table.read_group(
                    domain=domain,
                    fields=agg_fields,
                    groupby=groupby
                )

            if clase_documento_info:
                tipo_documento_table = self.env["account.journal.tipo_documento.field"] # obtener tabla donde se obtendran los datos

                domain = [("id", "=", tipo_documento_info)] # dominio obtener el tipo de documento que tenga el mismo id que el documento actual
                agg_fields = ["codigo:min", "valores:min"]

                groupby = ["codigo"]
                rows_tipo_documentos = tipo_documento_table.read_group(
                    domain=domain,
                    fields=agg_fields,
                    groupby=groupby
                )
            _logger.info('tipo_documento_info.get(codigo) %s', tipo_documento_info)
            _logger.info('r.get("name") %s', r.get("name"))
            _logger.info('AAAAAAAAAAAAA %s', r)

            _logger.info('numero_resolucion %s', r.get("name"))



            if tipo_documento_info == "4":
                numero_resolucion =  "N/A"
            else:
                numero_resolucion = r.get("name")

            journal_info = r.get("journal_id")
            journal_id = journal_info[0] if isinstance(journal_info, tuple) else False
            codigo_tipo_documento_codigo = rows_tipo_documentos[0].get("codigo")
            codigo_tipo_documento_valores = rows_tipo_documentos[0].get("valores")

            _logger.info("numero_resolucion ------------ %s",numero_resolucion)
            _logger.info("DENTRO DE TIPO codigo_tipo_documento_valores %s", codigo_tipo_documento_valores)
            _logger.info("DISPLAYSSS %s", f"{codigo_tipo_documento_codigo}. {codigo_tipo_documento_valores}")

            clase_documento_codigo = rows_clase_documento[0].get("codigo")
            clase_documento_valor = rows_clase_documento[0].get("valor")

            new_record = self.create({
                "invoice_date": d,
                "clase_documento_codigo": clase_documento_codigo,
                "clase_documento_valor": clase_documento_valor,
                "clase_documento_display": f"{clase_documento_codigo}. {clase_documento_valor}",
                "journal_id": journal_id,
                "codigo_tipo_documento_codigo": codigo_tipo_documento_codigo,
                "codigo_tipo_documento_valor": codigo_tipo_documento_valores,
                "codigo_tipo_documento_display": f"{codigo_tipo_documento_codigo}. {codigo_tipo_documento_valores}",
                "numero_resolucion_consumidor_final": numero_resolucion,
                # "rows_tipo_documentos_valor"
                "cantidad_facturas": r.get("id_count", r.get("__count", 0)),
                "monto_total_operacion": r.get("amount_untaxed", 0.0),
                "monto_total_impuestos": r.get("amount_tax", 0.0),
                "invoice_year_agrupado": str(year),
                "invoice_month_agrupado": f"{month:02d}",
                "invoice_year_sel": str(year),
                "invoice_month_sel": f"{month:02d}",
                "numero_anexo": numero_anexo,
            })

            _logger.info("CREACIÓN: Nuevo registro (ID: %s, Clase ID: %s, Diario: %s, Tipo Doc: %s)",
                         new_record.id, new_record.clase_documento_id.id if new_record.clase_documento_id else False,
                         new_record.journal_id.id if new_record.journal_id else False,
                         new_record.codigo_tipo_documento)

        final_context = dict(
            self.env.context,
            numero_anexo=numero_anexo,
            # Se mueven aquí las propiedades que causan la advertencia:
            replace_existing_action=True,
            tag='reload',
        )

        return {
            "type": "ir.actions.act_window",
            "name": "Anexo de Ventas a Consumidor Final",
            "res_model": "report.account.move.consumidor.final.agrupado",
            "view_mode": "list",
            "view_id": self.env.ref(
                "l10n_sv_mh_anexos.view_report_account_move_consumidor_final_agrupado_list"
            ).id,
            "target": "current",
            "context": final_context,
        }

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

    # --- Campos para agrupar (store=True) ---
    invoice_year_agrupado = fields.Char(string="Año", index=True)
    invoice_semester_agrupado = fields.Selection(
        [('1', '1.º semestre'), ('2', '2.º semestre')],
        string="Semestre", index=True
    )
    invoice_month_agrupado = fields.Char(string="Mes", index=True)

    # --- Wrappers para SearchPanel (Selection) ---
    invoice_year_sel = fields.Selection(
        selection=lambda self: [(str(y), str(y)) for y in range(2018, 2040)],
        string='Año (sel)', index=True
    )
    invoice_month_sel = fields.Selection(
        selection=[(f'{m:02d}', f'{m:02d}') for m in range(1, 13)],
        string='Mes (sel)', index=True
    )

    @api.depends('invoice_date')
    def _compute_periods(self):
        for r in self:
            if r.invoice_date:
                r.invoice_year_agrupado = str(r.invoice_date.year)
                r.invoice_semester_agrupado = '1' if r.invoice_date.month <= 6 else '2'
                r.invoice_month_agrupado = f'{r.invoice_date.month:02d}'
            else:
                r.invoice_year_agrupado = False
                r.invoice_semester_agrupado = False
                r.invoice_month_agrupado = False

    @api.depends('invoice_date')
    def _compute_periods_sel(self):
        for r in self:
            if r.invoice_date:
                r.invoice_year_sel = str(r.invoice_date.year)
                r.invoice_month_sel = f'{r.invoice_date.month:02d}'
            else:
                r.invoice_year_sel = False
                r.invoice_month_sel = False
