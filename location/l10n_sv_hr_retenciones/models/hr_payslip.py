from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
from odoo.tools import float_round
from datetime import time, timedelta
import pytz
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    from odoo.addons.common_utils.utils import config_utils
    _logger.info("SIT Modulo config_utils")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    constants = None
    config_utils = None

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    # Filtrado líneas salariales (solo las reglas que aparecen en payslip)
    line_ids_filtered = fields.One2many(
        comodel_name='hr.payslip.line',
        compute='_compute_line_ids_filtered',
        string='Cálculo del salario (filtrado)',
        store=False,
    )

    # Filtrado líneas de inputs según códigos de reglas visibles
    input_line_ids_filtered = fields.One2many(
        comodel_name='hr.payslip.input',
        compute='_compute_input_line_ids_filtered',
        string='Entradas filtradas',
        store=False,
    )

    is_vacation_payslip = fields.Boolean(
        string="¿Es recibo de vacaciones?",
        help="Marca esta opción si este recibo corresponde a vacaciones."
    )

    @api.onchange('worked_days_line_ids')
    def _onchange_worked_days_vacations(self):
        """
        Si en los días trabajados hay vacaciones, marcamos is_vacation_payslip=True.
        """
        for slip in self:
            _logger.info("=== ONCHANGE worked_days_line_ids para nómina %s ===", slip.name)

            # Buscar si hay líneas de vacaciones en worked_days_line_ids
            tiene_vacaciones = any(
                line.code in constants.CODES_VACACIONES
                for line in slip.worked_days_line_ids
            )

            # Marcar el campo si se detectan vacaciones
            slip.is_vacation_payslip = bool(tiene_vacaciones)
            _logger.info("¿Tiene vacaciones en worked_days_line_ids? %s → is_vacation_payslip=%s", tiene_vacaciones, slip.is_vacation_payslip)

    @api.depends('line_ids.salary_rule_id.appears_on_payslip')
    def _compute_line_ids_filtered(self):
        """
        Computa las líneas de la nómina (`line_ids_filtered`) que deben mostrarse en el recibo de pago.

        Este campo computado filtra las líneas de salario (`hr.payslip.line`) cuya regla salarial
        asociada (`salary_rule_id`) tenga el campo `appears_on_payslip=True`.

        Esto permite separar visualmente, por ejemplo, descuentos patronales u otras reglas técnicas
        que no deben mostrarse al empleado en el recibo.
        """
        for rec in self:
            rec.line_ids_filtered = rec.line_ids.filtered(
                lambda l: l.salary_rule_id and l.salary_rule_id.appears_on_payslip
            )

    @api.depends('input_line_ids', 'line_ids.salary_rule_id.appears_on_payslip')
    def _compute_input_line_ids_filtered(self):
        """
        Computa las entradas (inputs) filtradas (`input_line_ids_filtered`) que deben mostrarse.

        Se basa en los códigos de las reglas salariales visibles (definidas por `appears_on_payslip=True`).
        Solo los inputs (`hr.payslip.input`) cuyo código coincida con una regla visible serán incluidos.

        Esto permite que, por ejemplo, los aportes del empleador (que no deben mostrarse) también
        se filtren de la vista de otras entradas.
        """
        for rec in self:
            # Obtiene los códigos de las líneas de nómina visibles
            visible_codes = rec.line_ids.filtered(
                lambda l: l.salary_rule_id and l.salary_rule_id.appears_on_payslip
            ).mapped('code')

            # Filtra las líneas de input que coinciden con esos códigos
            rec.input_line_ids_filtered = rec.input_line_ids.filtered(
                lambda i: i.code in visible_codes
            )

    # Método sobrescrito para calcular la nómina (payslip) personalizada
    def compute_sheet(self):
        # Registra el inicio del cálculo personalizado de la nómina
        _logger.info(">>> [INICIO] compute_sheet personalizado para %d nóminas", len(self))

        # 3. Aplicar descuento de séptimo por faltas injustificadas
        self._aplicar_descuento_septimo_por_faltas()

        # 1. Crear inputs necesarios ANTES del cálculo estándar
        for payslip in self:

            if self.es_nomina_de_vacacion(payslip):
                _logger.info("Detectada nómina de vacaciones %s → preparando inputs antes del cálculo", payslip.name)

                # if not payslip.struct_id.is_vacation:
                #     raise UserError(
                #         "La estructura seleccionada (%s) no está configurada como de vacaciones. "
                #         "Por favor, seleccione una estructura válida." % (payslip.struct_id.name or "N/A")
                #     )
                payslip._agregar_regla_vacaciones(payslip)
            contract = payslip.contract_id
            _logger.info("Procesando nómina normal: %s para contrato %s", payslip.name, contract.name if contract else "N/A")

            if not contract:
                _logger.warning("Nómina %s sin contrato → solo cálculo base", payslip.name)
                continue

            # Calcular base imponible acumulada
            if contract.wage <= 0:
                raise UserError(
                    "El contrato de %s no tiene definido un salario base válido (campo 'Salario'). "
                    "Por favor configure un salario base en el contrato para calcular las deducciones correctamente." % contract.employee_id.name
                )

            base_imponible = sum(payslip.worked_days_line_ids.mapped('amount'))
            _logger.info("Base imponible (total días trabajados) = %.2f", base_imponible)
            _logger.info("period_quincena = %s", payslip.period_quincena)

            # Usar el método centralizado para crear los inputs
            self._crear_inputs_deducciones(payslip, contract, base_imponible)
            _logger.info("period_quincena = %s", payslip.period_quincena)
            #Obtener la nomina de la primera quincena
            if payslip.period_quincena == '2' :
                primera_quincena = self.env['hr.payslip'].search(
                    [('employee_id', '=', payslip.employee_id.id), ('period_quincena', '=', '1'),
                    ('period_month', '=', payslip.period_month), ('company_id', '=', payslip.company_id.id), ], limit=1)

                _logger.info(">>>  %s primera_quincena", primera_quincena)

                ISSS_anterior = primera_quincena.input_line_ids.filtered(lambda l: l.name == "Deducción ISSS")
                _logger.info(">>>Quincena anterior: %s ", ISSS_anterior)

                ISSS_actual = payslip.input_line_ids.filtered(lambda l: l.name == "Deducción ISSS")

                _logger.info(">>>  %s ISS quincena anterior", ISSS_anterior.amount)
                _logger.info(">>>  %s ISS quincena actual", ISSS_actual.amount)

                #_logger.info(">>>  %s pago mensual", contract.monthly_yearly_costs)





        # 2. Llamar al cálculo estándar, que ahora usará los inputs ya creados
        res = super(HrPayslip, self).compute_sheet()

        _logger.info(">>> [FIN] compute_sheet personalizado completado")
        return res

    def _obtener_deducciones(self, payslip, contract, base_imponible):
        try:
            renta, devolucion_renta = contract.calcular_deduccion_renta(salario_bruto=base_imponible, payslip=payslip)
            afp = contract.calcular_afp(salario_bruto=base_imponible, payslip=payslip)
            isss = contract.calcular_isss(salario_bruto=base_imponible, payslip=payslip)
            afp_patronal = contract.calcular_aporte_patronal(constants.TIPO_DED_AFP, salario_bruto=base_imponible, payslip=payslip)
            isss_patronal = contract.calcular_aporte_patronal(constants.TIPO_DED_ISSS, salario_bruto=base_imponible, payslip=payslip)
            incaf = contract.calcular_incaf(salario_bruto=base_imponible, payslip=payslip)
        except Exception as e:
            _logger.error("Error al calcular deducciones para contrato %s: %s", contract.id, e)
            raise UserError(_("Ocurrió un error al calcular deducciones: %s") % str(e))

        return renta, devolucion_renta, afp, isss, afp_patronal, isss_patronal, incaf

    def _crear_inputs_deducciones(self, slip, contract, base_total):
        """
        Método reutilizable para crear los inputs de deducciones (RENTA, AFP, ISSS, etc.)
        a partir de una base imponible.
        """
        _logger.info("Iniciando creación de inputs de deducción para nómina ID=%s | contrato ID=%s | base_total=%.2f", slip.id, contract.id, base_total)

        # Primero eliminamos entradas previas para evitar duplicados
        for code in (constants.DEDUCCION_CODES + [constants.DEVOLUCION_RENTA_CODE]):
            old_inputs = slip.input_line_ids.filtered(lambda l: l.code == code)
            if old_inputs:
                _logger.info("Eliminando %d inputs previos con código %s para nómina ID=%d", len(old_inputs), code, slip.id)
                old_inputs.unlink()

        # Obtener valores de deducciones
        renta, devolucion_renta, afp, isss, afp_patronal, isss_patronal, incaf = self._obtener_deducciones(payslip=slip, contract=contract, base_imponible=base_total)

        _logger.info( "Deducciones obtenidas → renta=%.2f, afp=%.2f, isss=%.2f, afp_patronal=%.2f, isss_patronal=%.2f, incaf=%.2f", renta, afp, isss, afp_patronal, isss_patronal, incaf)

        tipos = {
            code: self.env['hr.payslip.input.type'].search([('code', '=', code)], limit=1)
            for code in (constants.DEDUCCION_CODES + [constants.DEVOLUCION_RENTA_CODE])
        }

        # Validar existencia de tipos de input
        for code, tipo in tipos.items():
            if not tipo:
                _logger.error("No se encontró tipo de input con código %s", code)
                raise UserError(_("No se encontró el tipo de input para %s.") % code)
            else:
                _logger.debug("Tipo de input encontrado → código=%s, nombre=%s", code, tipo.name)

        # Determinar si es contrato profesional
        is_professional = contract.wage_type == constants.SERVICIOS_PROFESIONALES
        _logger.info("Tipo de contrato: %s", "Servicios Profesionales" if is_professional else "Regular")

        variables = {
            'renta': renta,
            'afp': afp,
            'isss': isss,
            'afp_patronal': afp_patronal,
            'isss_patronal': isss_patronal,
            'incaf': incaf,
            'afp_conf': afp,
            'afp_conf_patronal': afp_patronal,
        }

        valores = []

        if is_professional:
            valores.append(('RENTA_SP', -abs(renta)))
            _logger.info("Contrato de servicios profesionales → Solo se agrega RENTA_SP con valor %.2f", -abs(renta))
        else:
            # === Ajuste clave: si hay devolución, anular RENTA e inyectar DEV_RENTA ===
            if devolucion_renta and devolucion_renta > 0:
                _logger.info("Se detectó DEVOLUCIÓN de renta=%.2f → anular RENTA en 2Q y crear DEV_RENTA",
                             devolucion_renta)
                variables['renta'] = 0.0  # ← anula RENTA para que BASE_DEDUCCIONES no descuente
            # -------------------------------------------------------------------------

            # Deducciones base
            base_vals = [
                (code, abs(variables[var]) * sign)
                for code, var, sign in constants.BASE_DEDUCCIONES
            ]
            valores += base_vals
            _logger.info("Deducciones BASE: %s", base_vals)

            # Deducciones según tipo de AFP
            afp_name = (contract.afp_id  or '').strip().lower()

            if afp_name == constants.AFP_IPSFA:
                afp_rules = constants.AFP_IPSFA_CODES
            elif afp_name == constants.AFP_CONFIA:
                afp_rules = constants.AFP_CONF_REGULAR_CODES
            elif afp_name == constants.AFP_CRECER:
                afp_rules = constants.AFP_REGULAR_CODES
            else:
                _logger.warning("Tipo de AFP no reconocido: '%s'. No se aplicarán deducciones AFP.", afp_name)
                afp_rules = []

            afp_vals = [
                (code, abs(variables[var]) * sign)
                for code, var, sign in afp_rules
            ]
            valores += afp_vals
            _logger.info("Deducciones AFP: %s", afp_vals)


        # EXTRA: crear input de asignación por devolución (positivo)
        if devolucion_renta and devolucion_renta > 0:
            valores.append((constants.DEVOLUCION_RENTA_CODE, float_round(abs(devolucion_renta), 2)))
            _logger.info("Asignación DEV_RENTA=+%.2f agregada", devolucion_renta)

        # Crear inputs en la nómina
        for code, valor in valores:
            tipo = tipos.get(code)
            if tipo:
                slip.input_line_ids.create({
                    'name': tipo.name,
                    'code': code,
                    'amount': float_round(valor, precision_digits=2),
                    'payslip_id': slip.id,
                    'input_type_id': tipo.id,
                    'company_id': slip.company_id.id,  # <-- agregamos la empresa
                })
                _logger.info("Input agregado: código=%s, nombre=%s, monto=%.2f, nómina ID=%d", code, tipo.name, valor, slip.id)
            else:
                _logger.warning("Tipo de input para código %s no encontrado, no se creó input", code)


    # ==========FALTAS INJUSTIFICADAS
    def _aplicar_descuento_septimo_por_faltas(self):
        """
        Si hay al menos 1 entrada de trabajo con código FALTA en una semana ISO,
        se pierde el séptimo (domingo) de esa semana.
        En una quincena (15 días) solo se pueden descontar máximo 2 domingos.
        Si la nómina es mensual, se divide en 2 quincenas y se aplica el límite por cada quincena.
        """
        _logger.info(">>> Evaluando descuento de séptimo por faltas injustificadas")

        for slip in self:
            contract = slip.contract_id
            if not contract:
                _logger.warning("Nómina %s sin contrato. Se omite cálculo de séptimo.", slip.name)
                continue

            # Obtener salario mensual según la frecuencia del contrato
            salario_mensual = config_utils.get_monthly_wage_from_contract(contract)

            # De ahí derivamos el salario diario promedio
            dias_promedio = config_utils.get_dias_promedio_salario(self.env, slip.company_id.id)
            salario_diario = salario_mensual / dias_promedio
            _logger.info("[%s] Salario mensual=%.2f | divisor=%d días | salario diario=%.2f", slip.employee_id.name, salario_mensual, dias_promedio, salario_diario)
            # Determinar subperíodos (quincenas)
            quincenas = []

            # Si es mensual → dividir en dos quincenas
            if contract.schedule_pay == 'monthly':
                primera_quincena_fin = slip.date_from + relativedelta(days=14)
                segunda_quincena_ini = primera_quincena_fin + relativedelta(days=1)

                quincenas.append((slip.date_from, primera_quincena_fin))
                quincenas.append((segunda_quincena_ini, slip.date_to))
            else:
                # Si es quincenal o semanal, es solo un período
                quincenas.append((slip.date_from, slip.date_to))

            # Buscar solo las FALTAS injustificadas en el periodo de la nómina
            falta_code = constants.TIPOENT_FALTA or 'FALTA'
            desc_sept_code = constants.REGLASAL_DESC_SEPTIMO or 'DESC_FALTA_SEPTIMO'
            tipo_input = self.env['hr.payslip.input.type'].search([('code', '=', desc_sept_code)], limit=1)

            if not tipo_input:
                _logger.warning("[%s] Tipo de entrada %s no existe en BD → revisar XML", slip.employee_id.name, desc_sept_code)
                continue

            monto_total_descuento = 0.0

            # Procesar cada quincena por separado
            for fecha_ini, fecha_fin in quincenas:
                # Buscar solo faltas injustificadas en esta quincena
                faltas_entries = self.env['hr.work.entry'].search([
                    ('employee_id', '=', slip.employee_id.id),
                    ('date_start', '>=', fecha_ini),
                    ('date_stop', '<=', fecha_fin),
                    ('work_entry_type_id.code', '=', falta_code),
                    ('company_id', '=', slip.company_id.id),
                ])

                if not faltas_entries:
                    _logger.info("[%s] No hay faltas en quincena %s → no descuenta séptimo", slip.employee_id.name, f"{fecha_ini} a {fecha_fin}")
                    continue
                _logger.info("faltas_entries %s", faltas_entries)
                # Agrupar las semanas ISO en las que hubo al menos una falta
                semanas_con_falta = set()
                for entry in faltas_entries:
                    fecha_falta = fields.Date.to_date(entry.date_start)
                    _logger.info("fecha_falta %s", fecha_falta)
                    # semana_iso = fecha_falta.isocalendar()[1]
                    # _logger.info("semana_iso %s", semana_iso)
                    semanas_con_falta.add(fecha_falta)

                _logger.info("semanas_con_falta %s", semanas_con_falta)
                total_semanas_afectadas = len(semanas_con_falta)
                _logger.info("[%s] Quincena %s → semanas con faltas: %d", slip.employee_id.name, f"{fecha_ini} a {fecha_fin}", total_semanas_afectadas)

                # Límite máximo de 2 domingos por quincena
                if total_semanas_afectadas > 2:
                    _logger.info("[%s] Más de 2 domingos afectados (%d) en quincena, se limita a 2", slip.employee_id.name, total_semanas_afectadas)

                # Límite por quincena = 2 domingos
                dias_perdidos_quincena = min(total_semanas_afectadas, 2)
                # Calcular descuento final con el límite aplicado

                monto_total_descuento += float_round(salario_diario * dias_perdidos_quincena, precision_digits=2)

                _logger.info("[%s] Pierde %d domingos (de %d posibles) → descuento %.2f", slip.employee_id.name, dias_perdidos_quincena, total_semanas_afectadas, monto_total_descuento)

            if monto_total_descuento <= 0:
                _logger.info("[%s] Monto total de descuento = 0 → no se crea input", slip.employee_id.name)
                continue

            # Buscar o crear el input en la nómina
            input_line = slip.input_line_ids.filtered(lambda inp: inp.code == tipo_input.code)
            if input_line:
                input_line.amount = -abs(monto_total_descuento)
                _logger.info("[%s] Actualizado input %s con %.2f", slip.employee_id.name, tipo_input.code, monto_total_descuento)
            else:
                self.env['hr.payslip.input'].create({
                    'amount': -abs(monto_total_descuento),
                    'payslip_id': slip.id,
                    'input_type_id': tipo_input.id,
                    'name': tipo_input.name,
                })
                _logger.info("[%s] Creado input %s con %.2f", slip.employee_id.name, tipo_input.code, monto_total_descuento)

    # ==========VACACIONES
    def calcular_vacaciones(self, salario_mensual, meses_trabajados, company_id, dias_tomados=None, base_vacaciones=None):
        """
        Calcula el pago de vacaciones en El Salvador.

        - salario_mensual: importe total base del slip (worked_days)
        - meses_trabajados: número de meses trabajados
        - company_id: ID de la compañía del slip
        - dias_tomados: días efectivos que se gozan en esta nómina (si es parcial)

        Retorna dict con:
            dias_vacaciones, pago_base, extra_30, total
        """

        dias_promedio = config_utils.get_dias_promedio_salario(self.env, company_id)
        salario_diario = salario_mensual / dias_promedio

        # Determinar si ya tiene derecho completo
        meses_derecho = int(config_utils.get_config_value(self.env, 'vacaciones_meses_derecho', company_id) or 12)
        dias_derecho = int(config_utils.get_config_value(self.env, 'vacaciones_dias_derecho', company_id) or 15)
        extra_pct = int(config_utils.get_config_value(self.env, 'vacaciones_extra_porcentaje', company_id) or 30)

        tiene_derecho_completo = meses_trabajados >= meses_derecho

        # Caso 1: Ya cumplió tiempo y son vacaciones parciales
        _logger.info("=== Tiene derecho completo: %s | Días tomados: %s | base vacacion: %s ===", tiene_derecho_completo, dias_tomados, base_vacaciones)

        # Si ya tenemos el importe real del slip, usamos ese como base
        if base_vacaciones and dias_tomados:
            dias_vacaciones = dias_tomados
            pago_base = base_vacaciones
            extra_30 = pago_base * (extra_pct / 100.0)
            total = pago_base + extra_30
        else:
            # Caso vacaciones completas
            dias_vacaciones = dias_derecho
            pago_base = salario_diario * dias_vacaciones
            extra_30 = pago_base * (extra_pct / 100.0)
            total = pago_base + extra_30

        _logger.info(f"Vacaciones calculadas: {dias_vacaciones:.2f} días | base={pago_base:.2f} | extra_30={extra_30:.2f} | total={total:.2f} | salario diario={salario_diario:.2f}")
        return {
            "dias_vacaciones": round(dias_vacaciones, 2),
            "pago_base": round(pago_base, 2),
            "extra_30": round(extra_30, 2),
            "total": round(total, 2)
        }

    def _agregar_regla_vacaciones(self, slip):
        contract = slip.contract_id
        if not contract:
            return

        # Salario mensual real desde contrato
        salario_mensual = config_utils.get_monthly_wage_from_contract(contract)
        dias_promedio = config_utils.get_dias_promedio_salario(self.env, slip.company_id.id)

        # Calcular meses trabajados
        meses_trabajados = 0
        if contract.date_start:
            diff_days = (fields.Date.today() - contract.date_start).days
            meses_trabajados = diff_days / dias_promedio

        # Obtener días tomados desde ausencias aprobadas
        dias_tomados = self._get_dias_vacaciones_tomados(slip)

        # Primero ajusta las líneas worked_days según work_entries reales
        #self._ajustar_lineas_vacaciones()

        # NUEVO: obtener el importe real ya calculado en worked_days_line_ids para vacaciones
        base_vacaciones = sum(
            slip.worked_days_line_ids.filtered(
                lambda l: l.work_entry_type_id.leave_type_ids.is_vacation
            ).mapped('amount')
        )
        _logger.info("Base imponible (total días trabajados) = %.2f ", base_vacaciones)

        _logger.info("=== Meses trabajados %.2f | días tomados detectados=%s | salario mensual contrato=%.2f ===", meses_trabajados, dias_tomados, salario_mensual)

        # Calcular vacaciones completas o parciales según días_tomados
        datos_vac = self.calcular_vacaciones(
            salario_mensual,
            meses_trabajados,
            slip.company_id.id,
            dias_tomados=dias_tomados,
            base_vacaciones=base_vacaciones
        )

        # Solo creamos input si hay extra_30
        if datos_vac["extra_30"] > 0:
            # Buscar el tipo de otras entradas VACACIONES
            vacacion = constants.REGLASAL_VACACION or 'VACACIONES'
            tipo_vacaciones = self.env['hr.payslip.input.type'].search([('code', '=', vacacion)], limit=1)
            _logger.info(f"Tipo vacaciones DD {tipo_vacaciones}")
            if not tipo_vacaciones:
                _logger.error("No existe tipo de entrada VACACIONES en Otras Entradas")
                return

            # Buscar si ya existe input VACACIONES en este slip
            input_existente = slip.input_line_ids.filtered(lambda i: i.code == vacacion)
            _logger.info(f"Tipo vacaciones DD {tipo_vacaciones}")
            if input_existente:
                input_existente.write({'amount': float_round(datos_vac["extra_30"], precision_digits=2)})
                _logger.info(f"input existente {datos_vac['extra_30']}")
            else:
                slip.input_line_ids.create({
                    'name': tipo_vacaciones.name,
                    'code': tipo_vacaciones.code,
                    'amount': float_round(datos_vac["extra_30"], precision_digits=2),
                    'payslip_id': slip.id,
                    'input_type_id': tipo_vacaciones.id,
                    'company_id': slip.company_id.id,
                })
                _logger.info(f"Creado input VACACIONES en {slip.name} → días={datos_vac['dias_vacaciones']} extra={datos_vac['extra_30']}")

    def _ajustar_lineas_vacaciones(self):# No se esta utilizando
        # Obtener las horas diarias configuradas, si no existe usar 8 por defecto
        horas_diarias = config_utils.get_config_value(self.env, 'horas_diarias', self.company_id.id) or 8.0
        try:
            horas_diarias = float(horas_diarias)
        except ValueError:
            _logger.warning("La configuración 'horas_diarias' no es numérica, usando 8.0 por defecto")
            horas_diarias = 8.0

        for slip in self:
            contract = slip.contract_id
            if not contract:
                continue

            # Buscar si hay alguna ausencia (tiempo personal) en el período del slip
            # leave = self.env['hr.leave'].search([
            #     ('employee_id', '=', slip.employee_id.id),
            #     ('date_from', '<=', slip.date_to),
            #     ('date_to', '>=', slip.date_from),
            #     ('holiday_status_id.is_vacation', '=', True),  # solo vacaciones
            # ], limit=1)

            # Si tiene vacation_full = True, NO ajustamos
            # if leave and leave.vacation_full:
            #     _logger.info("Vacaciones registradas como COMPLETAS (vacation_full=True) → NO se ajusta importe para %s", slip.name)
            #     continue

            # --- SOLO sigue si no es vacation_full ---
            _logger.info("=== Ajustando línea de asistencia SOLO para vacaciones parciales en %s ===", slip.name)

            # Obtener salario mensual y valor hora usando las utilidades
            salario_mensual = config_utils.get_monthly_wage_from_contract(contract)
            valor_hora = config_utils.get_hourly_rate_from_contract(contract)

            # Si quieres loguear también el factor de conversión:
            factor = constants.SCHEDULE_PAY_CONVERSION.get(contract.schedule_pay or 'monthly', 1.0)
            _logger.info("Frecuencia pago=%s | salario_base=%.2f | factor=%.4f → salario_mensual=%.2f | valor_hora=%.4f", contract.schedule_pay, contract.wage, factor, salario_mensual, valor_hora)

            # Buscar work.entries en el período
            date_to_plus = slip.date_to + timedelta(days=1)
            work_entries = self.env['hr.work.entry'].search([
                ('employee_id', '=', slip.employee_id.id),
                ('date_start', '>=', slip.date_from),
                ('date_start', '<', date_to_plus),
                ('company_id', '=', slip.company_id.id),
            ]).filtered(lambda we: we.duration > 0)

            # Filtrar solo entradas que cuentan como asistencia
            _logger.info("Entradas de trabajo encontradas: %d para %s (%s → %s)", len(work_entries), slip.employee_id.name, slip.date_from, slip.date_to)

            _logger.info("Entradas de trabajo encontradas: %d para %s (%s → %s)", len(work_entries), slip.employee_id.name, slip.date_from, slip.date_to)

            # Calcular horas totales
            total_hours = sum(we.duration for we in work_entries)

            dias_reales = total_hours / horas_diarias
            monto_proporcional = total_hours * valor_hora

            _logger.info("TOTAL → horas=%.2f | días reales=%.2f | monto proporcional=%.2f", total_hours, dias_reales, monto_proporcional)

            # Buscar línea a ajustar (cualquier línea con importe > 0)
            asistencia_line = slip.worked_days_line_ids.filtered(lambda l: l.amount > 0)

            if asistencia_line:
                for line in asistencia_line:
                    line.number_of_days = dias_reales
                    line.amount = monto_proporcional
                    _logger.info("Línea actualizada: days=%.2f amount=%.2f", line.number_of_days, line.amount)
            else:
                _logger.warning("No se encontró línea de asistencia para actualizar en %s", slip.name)

    def _get_dias_vacaciones_tomados(self, slip):
        """
        Obtiene automáticamente los días de vacaciones tomados en el período del slip
        leyendo ausencias hr.leave validadas.
        """
        # Buscar ausencias tipo VACACIONES aprobadas dentro del período del slip
        vac_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', slip.employee_id.id),
            ('state', '=', 'validate'),
            ('holiday_status_id.is_vacation', '=', True),
            ('date_from', '<=', slip.date_to),
            ('date_to', '>=', slip.date_from),
            ('company_id', '>=', slip.company_id.id),
        ])

        # Sumar los días aprobados en ese período
        dias_tomados = sum(vac_leaves.mapped('number_of_days'))
        _logger.info("Vacaciones detectadas en %s: %s días (de %s ausencias)", slip.name, dias_tomados, len(vac_leaves))

        return dias_tomados if dias_tomados > 0 else None

    def es_nomina_de_vacacion(self, slip):
        """
        Detecta si la nómina es de vacaciones revisando las worked_days_line_ids.
        Se busca si el work_entry_type está vinculado a un leave_type con is_vacation.
        """
        for line in slip.worked_days_line_ids:
            work_type = line.work_entry_type_id
            # Buscar leave_type asociado a este work_entry_type
            leave_type = self.env['hr.leave.type'].search([
                ('work_entry_type_id', '=', work_type.id),
                ('is_vacation', '=', True)
            ], limit=1)
            if leave_type:
                return True
        return False




########################################################################################################################
