from odoo import fields, models, api, tools
import logging
import base64
from datetime import date

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    from odoo.addons.common_utils.utils import config_utils

    _logger.info("SIT Modulo config_utils [hacienda invalidacion]")
except ImportError as e:
    _logger.error(f"Error al importar 'constants': {e}")
    constants = None
    config_utils = None


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

    numero_resolucion_consumidor_final = fields.Char(
        string="Número de resolución"
    )

    numero_control_interno_del = fields.Char(
        string="Numero de control interno DEL",
        readonly=True,
    )

    numero_control_interno_al = fields.Char(
        string="Numero de control interno AL",
        readonly=True,
    )

    numero_documento_del = fields.Char(string="Número de documento (DEL)")

    numero_documento_al = fields.Char(string="Número de documento (AL)")

    hacienda_sello_recibido = fields.Char(
        string="Sello Recibido",
    )

    exportaciones_dentro_centroamerica = fields.Monetary(
        string="Exportaciones dentro del area de centroamerica",
        readonly=True,
    )

    exportaciones_fuera_centroamerica = fields.Monetary(
        string="Exportaciones fuera del area de centroamerica",
        readonly=True,
    )

    ventas_tasa_cero = fields.Monetary(
        string="Ventas a zonas francas y DPA (tasa cero)",
        readonly=True,
    )

    ventas_exentas_no_sujetas = fields.Monetary(
        string="Ventas internas exentas no sujetas a proporcionalidad",
        readonly=True,
    )

    total_ventas_exentas = fields.Monetary(string="Ventas exentas")

    tipo_ingreso_id = fields.Many2one(
        comodel_name="account.tipo.ingreso",
        string="Tipo de Ingreso"
    )

    tipo_ingreso_display = fields.Char(
        string="Tipo de Ingreso",
        readonly=True,
    )

    tipo_ingreso_codigo = fields.Char(
        string="Tipo ingreso codigo",
        readonly=True,
    )

    tipo_ingreso_valor = fields.Char(
        string="Tipo ingreso valor",
        readonly=True,
    )

    tipo_operacion = fields.Many2one(
        comodel_name="account.tipo.operacion",
        string="Tipo Operacion"
    )

    tipo_operacion_codigo = fields.Char(
        string="Tipo operacion codigo",
        readonly=True,
    )

    tipo_operacion_valor = fields.Char(
        string="Tipo operacion valor",
        readonly=True,
    )

    tipo_operacion_display = fields.Char(
        string="Tipo de Operación",
    )

    numero_maquina_registradora = fields.Char(
        string="Nùmero de maquina registradora",
        readonly=True,
    )

    ventas_cuenta_terceros = fields.Char(
        string="ventas a cuenta de terceros no domiciliados",
        readonly=True,
    )

    total_gravado_local = fields.Monetary(
        string="Ventas gravadas locales",
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

    @api.model
    def _rebuild_report(self):
        """Borra y vuelve a generar las líneas del anexo."""
        # 1) Limpiar el wizard
        self.search([]).unlink()

        Move = self.env["account.move"]
        Line = self.env["account.move.line"]
        Product = self.env["product.product"]
        has_detailed = 'detailed_type' in Product._fields

        # 1) Dominio base para facturas
        base_domain = [
            ("move_type", "=", "out_invoice"),
            ("hacienda_estado", "=", "PROCESADO"),
            ("has_sello_anulacion", "=", False),
            ("hacienda_selloRecibido", "!=", False),
            ("invoice_date", "!=", False),
            ("state", "=", "posted" ),
            ("codigo_tipo_documento", "in", ('01', '11', '02, ''10'))
        ]

        # 2) Traer todas las facturas y luego agruparlas en Python
        moves = Move.search(
            base_domain,
            order="invoice_date asc, codigo_tipo_documento asc, id asc",
        )
        _logger.info("ANEXO CF | moves encontrados=%s", len(moves))

        # key = (fecha, codigo_tipo_documento)
        grupos = {}
        for m in moves:
            key = (m.invoice_date, m.codigo_tipo_documento or "")
            grupos.setdefault(key, []).append(m.id)

        _logger.info("ANEXO CF | grupos formados=%s", len(grupos))

        numero_anexo = str(self.env.context.get("numero_anexo") or "")
        CA_CODES = getattr(constants, "CA_CODES", ['GT', 'HN', 'NI', 'CR', 'PA'])

        # 3) Recorrer cada grupo (fecha + código) y crear el registro del wizard
        #    Ordenado por fecha y luego por código
        for (inv_date, codigo_doc_raw), move_ids in sorted(
                grupos.items(),
                key=lambda it: (it[0][0] or date.min, str(it[0][1] or "")),
        ):
            d = inv_date
            if not d:
                continue

            moves_group = Move.browse(move_ids)
            if not moves_group:
                continue

            year = d.year
            month = d.month

            first_move = moves_group[0]
            last_move = moves_group[-1]

            # ------------------------------------------------------------------
            # 1) Resolver clase_documento (código y valor)
            # ------------------------------------------------------------------
            clase_documento_info = first_move.clase_documento_id.id
            if clase_documento_info:
                clase_documento_table = self.env["account.clase.documento"]
                domain_clase = [("id", "=", clase_documento_info)]
                agg_fields_clase = ["codigo:min", "valor:min"]
                groupby_clase = ["codigo"]

                rows_clase_documento = clase_documento_table.read_group(
                    domain=domain_clase,
                    fields=agg_fields_clase,
                    groupby=groupby_clase,
                )
            else:
                # Fallback por prefijo DTE en el número de control
                numero_control_aux = first_move.name or ""
                if numero_control_aux.startswith("DTE"):
                    codigo_clase = 4
                else:
                    codigo_clase = 1

                clase_documento_table = self.env["account.clase.documento"]
                domain_clase = [("codigo", "=", codigo_clase)]
                agg_fields_clase = ["codigo:min", "valor:min"]
                groupby_clase = ["codigo"]

                rows_clase_documento = clase_documento_table.read_group(
                    domain=domain_clase,
                    fields=agg_fields_clase,
                    groupby=groupby_clase,
                )

            clase_documento_codigo = rows_clase_documento[0].get("codigo") if rows_clase_documento else False
            clase_documento_valor = rows_clase_documento[0].get("valor") if rows_clase_documento else False

            # ------------------------------------------------------------------
            # 2) Resolver tipo_documento (código y valores) a partir del código del grupo
            # ------------------------------------------------------------------
            codigo_tipo_documento_info = codigo_doc_raw
            if codigo_tipo_documento_info:
                tipo_documento_table = self.env["account.journal.tipo_documento.field"]
                domain_tipo = [("codigo", "=", codigo_tipo_documento_info)]
                agg_fields_tipo = ["codigo:min", "valores:min"]
                groupby_tipo = ["codigo"]

                rows_tipo_documentos = tipo_documento_table.read_group(
                    domain=domain_tipo,
                    fields=agg_fields_tipo,
                    groupby=groupby_tipo,
                )
            else:
                rows_tipo_documentos = []

            codigo_tipo_documento_codigo = rows_tipo_documentos[0].get("codigo") if rows_tipo_documentos else False
            codigo_tipo_documento_valores = rows_tipo_documentos[0].get("valores") if rows_tipo_documentos else False

            _logger.info(
                "GRUPO -> fecha=%s cod_doc_mov=%s cod_doc_map=%s count=%s",
                d,
                codigo_doc_raw,
                codigo_tipo_documento_codigo,
                len(moves_group),
            )

            # ------------------------------------------------------------------
            # 3) Primer y último hacienda_codigoGeneracion_identificacion
            # ------------------------------------------------------------------
            numero_control_interno_del = "N/A"
            numero_control_interno_al = "N/A"
            numero_documento_del = ""
            numero_documento_al = ""

            first_code = first_move.hacienda_codigoGeneracion_identificacion or ""
            last_code = last_move.hacienda_codigoGeneracion_identificacion or ""

            if first_code and clase_documento_codigo == 4:
                numero_control_interno_del = "N/A"
            else:
                numero_control_interno_del = first_code
            numero_documento_del = first_code

            if last_code and clase_documento_codigo == 4:
                numero_control_interno_al = "N/A"
            else:
                numero_control_interno_al = last_code
            numero_documento_al = last_code

            _logger.info(
                "   DEL=%s AL=%s ids=%s",
                first_code, last_code, moves_group.ids,
            )

            # ------------------------------------------------------------------
            # 4) Totales (solo facturas del grupo fecha + código)
            # ------------------------------------------------------------------
            total_exento_group = sum(m.amount_exento or 0.0 for m in moves_group)
            total_no_sujeto_group = sum(m.total_no_sujeto or 0.0 for m in moves_group)
            moves_local = moves_group.filtered(lambda m: m.partner_id.country_id.code == 'SV')
            total_gravado_local_group = sum(m.total_gravado or 0.0 for m in moves_local)
            monto_total_op_sum = sum(m.amount_total or 0.0 for m in moves_group)
            monto_total_impuestos_sum = sum(m.amount_tax or 0.0 for m in moves_group)
            cantidad_facturas = len(moves_group)

            # ------------------------------------------------------------------
            # 5) Exportaciones (solo si código doc = 11)
            # ------------------------------------------------------------------
            exportaciones_dentro_centroamerica = 0.0
            exportaciones_fuera_centroamerica = 0.0
            exportaciones_servicio_group = 0.0

            codigo_doc_str = str(codigo_tipo_documento_codigo or codigo_doc_raw or "").strip()
            if codigo_doc_str == '11':
                moves_exp_centroamerica = moves_group.filtered(
                    lambda m: m.partner_id.country_id
                              and m.partner_id.country_id.code in CA_CODES
                )
                exportaciones_dentro_centroamerica = sum(
                    m.amount_total or 0.0 for m in moves_exp_centroamerica
                )

                moves_exp_fuera_centroamerica = moves_group.filtered(
                    lambda m: m.partner_id.country_id
                              and m.partner_id.country_id.code not in CA_CODES
                )
                exportaciones_fuera_centroamerica = sum(
                    m.amount_total or 0.0 for m in moves_exp_fuera_centroamerica
                )

                line_domain = [
                    ('move_id', 'in', moves_group.ids),
                    ('product_id', '!=', False),
                ]
                if has_detailed:
                    line_domain.append(('product_id.detailed_type', '=', 'service'))
                else:
                    line_domain.append(('product_id.product_tmpl_id.type', '=', 'service'))

                data_servicio = Line.read_group(
                    line_domain,
                    ['price_subtotal:sum'],
                    []
                )

                if data_servicio:
                    row_serv = data_servicio[0]
                    exportaciones_servicio_group = (
                            (row_serv.get('price_subtotal_sum')
                             if row_serv.get('price_subtotal_sum') is not None else
                             row_serv.get('price_subtotal'))
                            or 0.0
                    )
                else:
                    exportaciones_servicio_group = 0.0

            # ------------------------------------------------------------------
            # 6) Datos de tipo de ingreso / tipo de operación
            # ------------------------------------------------------------------
            tipo_ingreso_id = first_move.tipo_ingreso_id.id
            if tipo_ingreso_id:
                tipo_ingreso_table = self.env["account.tipo.ingreso"]
                rows_tipo_ingreso = tipo_ingreso_table.read_group(
                    domain=[("id", "=", tipo_ingreso_id)],
                    fields=["codigo:min", "valor:min"],
                    groupby=["codigo"],
                )
            else:
                rows_tipo_ingreso = []

            tipo_ingreso_codigo = rows_tipo_ingreso[0].get("codigo") if rows_tipo_ingreso else False
            tipo_ingreso_valor = rows_tipo_ingreso[0].get("valor") if rows_tipo_ingreso else False

            tipo_operacion_info = first_move.tipo_operacion.id
            if tipo_operacion_info:
                tipo_operacion_table = self.env["account.tipo.operacion"]
                row_tipo_operacion = tipo_operacion_table.read_group(
                    domain=[("id", "=", tipo_operacion_info)],
                    fields=["codigo:min", "valor:min"],
                    groupby=["codigo"],
                )
            else:
                row_tipo_operacion = []

            tipo_operacion_codigo = row_tipo_operacion[0].get("codigo") if row_tipo_operacion else False
            tipo_operacion_valor = row_tipo_operacion[0].get("valor") if row_tipo_operacion else False

            # ------------------------------------------------------------------
            # 7) Resolver número de resolución y sello recibido
            # ------------------------------------------------------------------
            if clase_documento_codigo == 4:
                numero_resolucion = first_move.name
                hacienda_sello_recibido = "N/A"
                numero_control_interno_del = "N/A"
                numero_control_interno_al = "N/A"
            else:
                numero_resolucion = first_move.name
                hacienda_sello_recibido = first_move.hacienda_selloRecibido

            journal_id = first_move.journal_id.id if first_move.journal_id else False

            numero_maquina_registradora = ""
            ventas_exentas_no_sujetas_aux = ""
            ventas_tasa_cero = ""
            ventas_cuenta_terceros = ""

            # ------------------------------------------------------------------
            # 8) Crear registro del wizard
            # ------------------------------------------------------------------
            self.create({
                "invoice_date": d,
                "clase_documento_codigo": clase_documento_codigo,
                "clase_documento_valor": clase_documento_valor,
                "clase_documento_display": f"{clase_documento_codigo}. {clase_documento_valor}",
                "journal_id": journal_id,
                "codigo_tipo_documento_codigo": codigo_tipo_documento_codigo or codigo_doc_raw,
                "codigo_tipo_documento_valor": codigo_tipo_documento_valores,
                "codigo_tipo_documento_display": (
                    f"{codigo_tipo_documento_codigo or codigo_doc_raw}. {codigo_tipo_documento_valores or ''}"
                ).strip(),
                "numero_resolucion_consumidor_final": numero_resolucion,
                "hacienda_sello_recibido": hacienda_sello_recibido,
                "numero_control_interno_del": numero_control_interno_del,
                "numero_control_interno_al": numero_control_interno_al,
                "numero_documento_del": numero_documento_del,
                "numero_documento_al": numero_documento_al,
                "numero_maquina_registradora": numero_maquina_registradora,
                "total_exento": total_exento_group,
                "ventas_exentas_no_sujetas": ventas_exentas_no_sujetas_aux,
                "total_no_sujeto": total_no_sujeto_group,
                "total_gravado_local": total_gravado_local_group,
                "exportaciones_dentro_centroamerica": exportaciones_dentro_centroamerica,
                "exportaciones_fuera_centroamerica": exportaciones_fuera_centroamerica,
                "exportaciones_de_servicio": exportaciones_servicio_group,
                "ventas_tasa_cero": ventas_tasa_cero,
                "ventas_cuenta_terceros": ventas_cuenta_terceros,
                "cantidad_facturas": cantidad_facturas,
                "monto_total_operacion": monto_total_op_sum,
                "monto_total_impuestos": monto_total_impuestos_sum,
                "tipo_ingreso_codigo": tipo_ingreso_codigo,
                "tipo_ingreso_valor": tipo_ingreso_valor,
                "tipo_ingreso_display": f"{tipo_ingreso_codigo}. {tipo_ingreso_valor}" if tipo_ingreso_codigo else "",
                "tipo_operacion_codigo": tipo_operacion_codigo,
                "tipo_operacion_display": f"{tipo_operacion_codigo}. {tipo_operacion_valor}" if tipo_operacion_codigo else "",
                "invoice_year_agrupado": str(year),
                "invoice_month_agrupado": f"{month:02d}",
                "invoice_year_sel": str(year),
                "invoice_month_sel": f"{month:02d}",
                "numero_anexo": numero_anexo,
            })

        final_context = dict(
            self.env.context,
            numero_anexo=numero_anexo,
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

    @api.model
    def action_open_report(self, *args, **kwargs):
        # reconstruir datos
        self._rebuild_report()

        numero_anexo = str(self.env.context.get("numero_anexo") or "")

        final_context = dict(
            self.env.context,
            numero_anexo=numero_anexo,
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

    def action_refresh_report(self):
        """Botón 'Actualizar' desde la vista: recalcula y recarga sin nuevo breadcrumb."""
        self._rebuild_report()
        return {
            "type": "ir.actions.client",
            "tag": "reload",
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
