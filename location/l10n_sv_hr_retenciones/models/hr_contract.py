import logging
from odoo import models, fields
from odoo.tools import float_round

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    from odoo.addons.common_utils.utils import config_utils
    _logger.info("SIT Modulo config_utils l10n_sv_haciendaws_fe")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    constants = None
    config_utils = None

class HrContract(models.Model):
    _inherit = 'hr.contract'

    #Opcion de servicios profesionales en campo tipo de salario del contrato
    wage_type = fields.Selection(
        selection_add=[('professional_services', 'Salario por servicios profesionales')],
        string='Tipo de salario'
    )

    hourly_wage = fields.Float(
        string="Salario por hora",
        digits=(16, 4),  # Ahora permite 4 decimales
    )

    afp_id = fields.Selection([
        ('crecer', 'AFP CRECER'),
        ('confia', 'AFP CONFIA'),
        ('ipsfa', 'IPSFA'),
    ], string="AFP", default='crecer')

    def get_salario_bruto_total(self, payslip=None, salario_bruto_payslip=None):
        """
        Retorna el salario base + total de asignaciones sujetas a retención,
        incluyendo horas extra, comisiones y bonos. Si se proporciona `salario_bruto_payslip`,
        se usa como salario base en lugar de self.wage.
        """
        self.ensure_one()
        _logger.info("Salario: %.2f", salario_bruto_payslip)

        fecha_inicio = payslip.date_from if payslip else None
        fecha_fin = payslip.date_to if payslip else None

        # Determinar la empresa correcta
        company_id = payslip.company_id.id if payslip else self.env.company.id

        # Usa bruto de payslip si está definido, de lo contrario usa wage
        bruto = salario_bruto_payslip if salario_bruto_payslip is not None else payslip.basic_wage or 0.0
        _logger.info("Salario base del contrato ID PRIEMRA QUINCEAN %s = %.2f", self.id, bruto)

        if not self.employee_id:
            _logger.warning("Contrato %s no tiene empleado asignado. Retornando solo salario base.", self.id)
            return bruto  # Ya está definido

        tipos_incluidos = [
            constants.ASIGNACION_HORAS_EXTRA.upper(),
            constants.ASIGNACION_BONOS.upper(),
            constants.ASIGNACION_COMISIONES.upper(),
        ]

        faltas_codes = []
        code_desc_septimo = getattr(constants, 'REGLASAL_DESC_SEPTIMO', None)
        if code_desc_septimo:
            faltas_codes.append(str(code_desc_septimo).upper())
        else:
            faltas_codes.append('DESC_FALTA_SEPTIMO')

        if payslip and payslip.is_vacation_payslip:
            faltas_codes.append(constants.REGLASAL_VACACION.upper())

        _logger.info("Buscando asignaciones (%s) para empleado ID %s", tipos_incluidos, self.employee_id.id)

        domain = [
            ('employee_id', '=', self.employee_id.id),
            ('tipo', 'in', tipos_incluidos),
            ('company_id', '=', company_id),
        ]

        if fecha_inicio and fecha_fin:
            domain.append(('periodo', '>=', fecha_inicio))
            domain.append(('periodo', '<=', fecha_fin))

        try:
            asignaciones = self.env['hr.salary.assignment'].search(domain)
            # tabla hr_playslip_input y hr_playslip_input_type buscar
            _logger.info(
                "Se encontraron %d asignaciones para contrato ID %s en el rango %s - %s (empresa %s)",
                len(asignaciones), self.id, fecha_inicio, fecha_fin, company_id
            )
        except Exception as e:
            _logger.error("Error al buscar asignaciones para contrato %s: %s", self.id, e)
            asignaciones = []

        # ----- Buscar faltas en hr.payslip.input, validando contra hr.payslip.input.type.code -----
        faltas_total = 0.0
        if payslip:
            # 1) Buscar los tipos de input cuyo code esté en faltas_codes
            input_types = self.env['hr.payslip.input.type'].search([
                ('code', 'in', faltas_codes),
                ('company_id', '=', company_id),
            ])
            if not input_types:
                _logger.warning(
                    "No existen hr.payslip.input.type para códigos %s en empresa %s",
                    faltas_codes, company_id
                )
            else:
                # 2) Buscar inputs del payslip que pertenezcan a esos tipos
                inputs_faltas = self.env['hr.payslip.input'].search([
                    ('payslip_id', '=', payslip.id),
                    ('input_type_id', 'in', input_types.ids),
                    ('company_id', '=', company_id),
                ])
                # Importante: en tu implementación de séptimos, pones los montos en negativo.
                # Aquí simplemente sumamos (serán negativos y por tanto restarán al bruto).
                faltas_total = sum(inp.amount for inp in inputs_faltas)

                _logger.info(
                    "Faltas detectadas para payslip %s (empresa %s): tipos=%s | inputs=%d | total=%.2f",
                    payslip.number or payslip.id, company_id,
                    [t.code for t in input_types], len(inputs_faltas), faltas_total
                )

        monto_extra = sum(asignacion.monto for asignacion in asignaciones)
        _logger.info("monto_extra %s: %s", self.id, monto_extra)
        bruto_total = bruto + monto_extra + faltas_total
        _logger.info(
            "Bruto total para contrato ID %s (empresa %s): salario base %.2f + faltas_total %.2f + asignaciones %.2f = %.2f",
            self.id, company_id, bruto, faltas_total, monto_extra, bruto_total
        )

        return bruto_total

    def calculo_afp_mensual(self, salario_mensual, payslip):

        afp_empleado = None
        if self.afp_id and self.afp_id == constants.AFP_IPSFA:
            afp_empleado = self.env['hr.retencion.afp'].search([('tipo', '=', constants.DEDUCCION_IPSFA_EMPLEADO)], limit=1)
        elif self.afp_id and self.afp_id == constants.AFP_CONFIA:
            afp_empleado = self.env['hr.retencion.afp'].search([('tipo', '=', constants.DEDUCCION_AFP_CONF_EMPLEADO)], limit=1)
        else:
            afp_empleado = self.env['hr.retencion.afp'].search([('tipo', '=', constants.DEDUCCION_EMPLEADO)], limit=1)

        if not afp_empleado:
            # Si no se encuentra configuración para AFP, se registra una advertencia y se retorna 0.0
            _logger.warning("No se encontró configuración AFP para empleado.")
            return 0.0

        porcentaje_afp = afp_empleado.porcentaje or 0.0  # Porcentaje de deducción AFP
        techo = afp_empleado.techo or 0.0  # Techo máximo de deducción AFP

        primera_quincena = self.env['hr.payslip'].search(
            [('employee_id', '=', payslip.employee_id.id), ('period_quincena', '=', '1'),
             ('period_month', '=', payslip.period_month),  ('company_id', '=', payslip.company_id.id),], limit=1)

        afp_names = ["Deducción AFP","AFP CRECER", "AFP CONFIA", "AIPSFA"]
        afp_primera_quincena = primera_quincena.input_line_ids.filtered(
            lambda l: l.name in afp_names
        )

        _logger.info("afp_primera_quincena ENCONTRADO= %s", afp_primera_quincena)

        _logger.info("PRIMERA CALCULO QUINCENA AFP= %.2f", afp_primera_quincena.amount)
        _logger.info("SAlARIO MENSUAL %s = %.2f", self.id, salario_mensual)
        _logger.info("SAlARIO TECHO %s = %.2f", self.id, techo)
        base_mensual = min(salario_mensual, techo * 2) if techo > 0 else salario_mensual
        _logger.info("base= %.2f", base_mensual)
        deduccion_mensual_aux = base_mensual * (porcentaje_afp / 100.0)  # Cálculo de la deducción ISSS mensual
        deduccion_segunda_quincena = deduccion_mensual_aux

        return deduccion_segunda_quincena

    # Método para calcular la deducción AFP (Administradora de Fondos de Pensiones)
    def calcular_afp(self, salario_bruto=None, payslip=None):
        self.ensure_one()  # Garantiza que el cálculo se realice solo en un solo registro
        if self.wage_type == constants.SERVICIOS_PROFESIONALES:
            _logger.info("Contrato con servicios profesionales, no se aplica AFP.")
            return 0.0

        salario_mensual_bruto = 0.0
        salario_mensual = 0.0
        primera_quincena = None
        salario_bruto_q1 = 0.0
        salario_bruto_mensual = 0.0
        if payslip.period_quincena == '2':
            primera_quincena = self.env['hr.payslip'].search(
                [('employee_id', '=', payslip.employee_id.id), ('period_quincena', '=', '1'),
                 ('period_month', '=', payslip.period_month), ('company_id', '=', payslip.company_id.id), ], limit=1)

            _logger.info(">>>  %s primera_quincena", primera_quincena)

            if primera_quincena:
                bono = primera_quincena.input_line_ids.filtered(lambda l: l.name == "Bono")
                comisiones = primera_quincena.input_line_ids.filtered(lambda l: l.name == "Comision")
                salario_bruto_q1 = self.get_salario_bruto_total(payslip=primera_quincena, salario_bruto_payslip=primera_quincena.basic_wage)

            salario_bruto_q2 = self.get_salario_bruto_total(payslip=payslip, salario_bruto_payslip=salario_bruto)
            salario_bruto_mensual = salario_bruto_q1 + salario_bruto_q2

        salario = self.get_salario_bruto_total(payslip=payslip, salario_bruto_payslip=salario_bruto)

        _logger.info("AFP: salario bruto =%s", salario_bruto)
        _logger.info("AFP: salario base para contrato ID %s = %.2f", self.id, salario)
        _logger.info("SAlARIO MENSUAL %s = %.2f", self.id, salario_mensual)

        # Buscar el porcentaje y techo configurado para el empleado
        afp_empleado = None
        if self.afp_id and self.afp_id == constants.AFP_IPSFA:
            afp_empleado = self.env['hr.retencion.afp'].search([('tipo', '=', constants.DEDUCCION_IPSFA_EMPLEADO)], limit=1)
        elif self.afp_id and self.afp_id == constants.AFP_CONFIA:
            afp_empleado = self.env['hr.retencion.afp'].search([('tipo', '=', constants.DEDUCCION_AFP_CONF_EMPLEADO)], limit=1)
        else:
            afp_empleado = self.env['hr.retencion.afp'].search([('tipo', '=', constants.DEDUCCION_EMPLEADO)], limit=1)

        _logger.info("AFP EMPLEADO %s", afp_empleado)
        _logger.info("AFP EMPLEADO TIPO%s", afp_empleado.tipo)
        if not afp_empleado:
            # Si no se encuentra configuración para AFP, se registra una advertencia y se retorna 0.0
            _logger.warning("No se encontró configuración AFP para empleado.")
            return 0.0

        _logger.info("Config AFP encontrada: techo=%.2f, porcentaje=%.2f%%", afp_empleado.techo, afp_empleado.porcentaje)

        porcentaje_afp = afp_empleado.porcentaje or 0.0  # Porcentaje de deducción AFP
        techo = afp_empleado.techo or 0.0  # Techo máximo de deducción AFP

        _logger.info("salario %.2f", salario)
        # Si hay techo definido (> 0), se aplica como límite para la base de cálculo
        base = min(salario, techo) if techo > 0 else salario
        deduccion = base * (porcentaje_afp / 100.0)  # Cálculo de la deducción AFP

        afp_primera_quincena = None
        if payslip.period_quincena == '2':
            _logger.info("AFP PRIMERA QUINCENA IDDDDDDD= %s", primera_quincena)

            if primera_quincena:
                afp_names = ["Deducción AFP","AFP CRECER", "AFP CONFIA", "AIPSFA"]
                afp_primera_quincena = primera_quincena.input_line_ids.filtered(
                    lambda l: l.name in afp_names
                )

            _logger.info("afp_primera_quincena ENCONTRADO= %s", afp_primera_quincena)

            _logger.info("AFP PRIMERA QUINCENA = %.2f", afp_primera_quincena.amount if afp_primera_quincena else 0.0)
            _logger.info("AFP MENSUAL = %.2f", self.calculo_afp_mensual(salario_bruto_mensual,payslip))
            deduccion_segunda_quincena = self.calculo_afp_mensual(salario_bruto_mensual,payslip) - abs(afp_primera_quincena.amount if afp_primera_quincena else 0.0)
            _logger.info("AFP base deduccion_segunda_quincena = %.2f", deduccion_segunda_quincena)
            return deduccion_segunda_quincena
        _logger.info("AFP base calculada = %.2f", base)

        _logger.info("base %.2f", base)
        _logger.info("deduccion %.2f", deduccion)

        _logger.info("AFP para contrato ID %d: base %.2f * %.2f%% = %.2f", self.id, base, porcentaje_afp, deduccion)
        return deduccion

    def calculo_de_techo_mensual(self, payslip, deduccion):
        primera_quincena = self.env['hr.payslip'].search(
            [('employee_id', '=', payslip.employee_id.id), ('period_quincena', '=', '1'),
             ('period_month', '=', payslip.period_month), ('company_id', '=', payslip.company_id.id), ], limit=1)

        _logger.info(">>>  %s primera_quincena", primera_quincena)
        return deduccion.techo * 2

    def calcular_isss_mensual(self, payslip, salario_mensual, mensauje = "nada"):
        _logger.info("MENSAJE %s", mensauje)
        isss_empleado = self.env['hr.retencion.isss'].search([('tipo', '=', constants.DEDUCCION_EMPLEADO)], limit=1)
        if not isss_empleado:
            # Si no se encuentra configuración para ISSS, se registra una advertencia y se retorna 0.0
            _logger.warning("No se encontró configuración ISSS para empleado.")
            return 0.0

        _logger.info("Config ISSS encontrada: techo=%.2f, porcentaje=%.2f%%", isss_empleado.techo, isss_empleado.porcentaje)

        porcentaje = isss_empleado.porcentaje or 0.0  # Porcentaje de deducción ISSS
        techo = isss_empleado.techo or 0.0  # Techo máximo de deducción ISSS
        primera_quincena = self.env['hr.payslip'].search(
            [('employee_id', '=', payslip.employee_id.id), ('period_quincena', '=', '1'),
            ('period_month', '=', payslip.period_month), ('company_id', '=', payslip.company_id.id), ], limit=1)

        isss_primera_quincena = primera_quincena.input_line_ids.filtered(lambda l: l.name == "Deducción ISSS")
        _logger.info("PRIMERA CALCULO QUINCENA ISSS= %.2f", isss_primera_quincena.amount)

        base = min(salario_mensual, techo * 2) if techo > 0 else salario_mensual
        deduccion_mensual_aux = base * (porcentaje / 100.0)  # Cálculo de la deducción ISSS mensual
        deduccion_segunda_quincena = deduccion_mensual_aux

        _logger.info("ISSS MENSUAL AJUSTADO PRUEBA BASE= %.2f", salario_mensual)
        _logger.info("ISSS MENSUAL deduccion_segunda_quincena= %.2f", deduccion_segunda_quincena)
        _logger.info("ISSS MENSUAL AJUSTADO PRUEBA 2= %.2f", salario_mensual * 0.03)

        return deduccion_segunda_quincena

    # Método para calcular la deducción ISSS (Instituto Salvadoreño del Seguro Social)
    def calcular_isss(self, salario_bruto=None, payslip=None):
        self.ensure_one()  # Garantiza que el cálculo se realice solo en un solo registro
        if self.wage_type == constants.SERVICIOS_PROFESIONALES:
            _logger.info("Contrato con servicios profesionales, no se aplica ISSS.")
            return 0.0

        salario_mensual_bruto = 0.0
        salario_mensual = 0.0
        primera_quincena = None
        salario_bruto_q1 = 0.0
        salario_bruto_mensual = 0.0
        if payslip.period_quincena == '2':
            primera_quincena = self.env['hr.payslip'].search(
                [('employee_id', '=', payslip.employee_id.id), ('period_quincena', '=', '1'),
                ('period_month', '=', payslip.period_month), ('company_id', '=', payslip.company_id.id), ], limit=1)

            _logger.info(">>>  %s primera_quincena", primera_quincena)

            if primera_quincena:
                bono = primera_quincena.input_line_ids.filtered(lambda l: l.name == "Bono")
                comisiones = primera_quincena.input_line_ids.filtered(lambda l: l.name == "Comision")
                salario_bruto_q1 = self.get_salario_bruto_total(payslip=primera_quincena, salario_bruto_payslip=primera_quincena.basic_wage)

            salario_bruto_q2 = self.get_salario_bruto_total(payslip=payslip, salario_bruto_payslip=salario_bruto)
            _logger.info(">>> Total salario Q1= %s | Total salario b. Q2= %s ", salario_bruto_q1, salario_bruto_q2)
            salario_bruto_mensual = salario_bruto_q1 + salario_bruto_q2

        salario = self.get_salario_bruto_total(payslip=payslip, salario_bruto_payslip=salario_bruto)

        _logger.info("ISSS: salario bruto =%s", salario_bruto)
        _logger.info("ISSS: salario base para contrato ID %s = %.2f", self.id, salario)
        _logger.info("SAlARIO MENSUAL %s = %.2f", self.id, salario_mensual)

        # Buscar la configuración de ISSS para el empleado
        isss_empleado = self.env['hr.retencion.isss'].search([('tipo', '=', constants.DEDUCCION_EMPLEADO)], limit=1)
        if not isss_empleado:
            # Si no se encuentra configuración para ISSS, se registra una advertencia y se retorna 0.0
            _logger.warning("No se encontró configuración ISSS para empleado.")
            return 0.0

        _logger.info("Config ISSS encontrada: techo=%.2f, porcentaje=%.2f%%", isss_empleado.techo, isss_empleado.porcentaje)

        porcentaje = isss_empleado.porcentaje or 0.0  # Porcentaje de deducción ISSS
        techo = isss_empleado.techo or 0.0   # Techo máximo de deducción ISSS

        base = min(salario, techo) if techo > 0 else salario
        deduccion = base * (porcentaje / 100.0)  # Cálculo de la deducción ISSS

        isss_primera_quincena = None
        deduccion_segunda_quincena = 0.0
        if payslip.period_quincena == '2':
            if primera_quincena:
                isss_primera_quincena = primera_quincena.input_line_ids.filtered(lambda l: l.name == "Deducción ISSS")

            deduccion_segunda_quincena = self.calcular_isss_mensual(payslip, salario_bruto_mensual, "desde calculo de ISSS") - abs(isss_primera_quincena.amount if isss_primera_quincena else 0.0)  # Caluclo real para segunda quincena
            _logger.info("isss_primera_quincena.amount= %.2f", isss_primera_quincena.amount if isss_primera_quincena else 0.0)
            _logger.info("deduccion_segunda_quincena = %.2f", deduccion_segunda_quincena)
            return deduccion_segunda_quincena

        # Se aplica el techo si está definido

        _logger.info("ISSS base calculada = %.2f", base)
        _logger.info("deduccion= %.2f", deduccion)

        # Registro de la información de la deducción para referencia
        _logger.info("ISSS empleado para contrato ID %d: base %.2f * %.2f%% = %.2f", self.id, base, porcentaje, deduccion)
        return deduccion

    # Método para calcular la deducción de renta del empleado
    def calcular_deduccion_renta(self, salario_bruto=None, payslip=None):
        self.ensure_one()  # Garantiza que el cálculo se realice solo en un solo registro
        _logger.info("############################## CALCULO DE RENTA para contrato ID %s | base imponible=%s ", self.id, salario_bruto)

        primera_quincena = None
        salario_bruto_q1 = 0.0
        salario_bruto_mensual = 0.0
        if payslip.period_quincena == '2':
            primera_quincena = self.env['hr.payslip'].search(
                [('employee_id', '=', payslip.employee_id.id), ('period_quincena', '=', '1'),
                ('period_month', '=', payslip.period_month), ('company_id', '=', payslip.company_id.id), ], limit=1)
            _logger.info(">>>  %s primera_quincena", primera_quincena)

            if primera_quincena:
                bono = primera_quincena.input_line_ids.filtered(lambda l: l.name == "Bono")
                comisiones = primera_quincena.input_line_ids.filtered(lambda l: l.name == "Comision")
                salario_bruto_q1= self.get_salario_bruto_total(payslip=primera_quincena, salario_bruto_payslip=primera_quincena.basic_wage)

            salario_bruto_q2 = self.get_salario_bruto_total(payslip=payslip, salario_bruto_payslip=salario_bruto)
            salario_bruto_mensual = salario_bruto_q1 + salario_bruto_q2
            _logger.info(">>>  RENTA: salario_bruto_mensual =%s", salario_bruto_mensual)
            _logger.info(">>>  RENTA: salario_bruto_q1 =%s", salario_bruto_q1)
            _logger.info(">>>  RENTA: salario_bruto_q2 =%s", salario_bruto_q2)

        salario = self.get_salario_bruto_total(payslip=payslip, salario_bruto_payslip=salario_bruto)  # bruto if bruto is not None else self.get_salario_bruto_total()
        _logger.info(">>>  RENTA: salario= %s", salario)

        # Si es servicios profesionales: 10% directo
        if self.wage_type == constants.SERVICIOS_PROFESIONALES:
            porcentaje_renta = float(config_utils.get_config_value(self.env, 'renta_servicios_profesionales', self.company_id.id) or 0.0)

            resultado = salario * (porcentaje_renta / 100)
            _logger.info("Contrato de servicios profesionales: renta fija 10%% sobre %.2f = %.2f", salario_bruto, resultado)
            return resultado

        # Verifica si el contrato tiene definida la frecuencia de pago
        if not self.schedule_pay:
            # Si no tiene definida la frecuencia de pago, se registra una advertencia y se retorna 0.0
            _logger.warning("El contrato no tiene definida la frecuencia de pago.")
            return 0.0

        # Mapeo de las frecuencias de pago a códigos para la tabla de retención de renta
        codigo_mapeo = {
            'monthly': constants.RET_MENSUAL,  # Mensual
            'semi-monthly': constants.RET_QUINCENAL,  # Quincenal(medio mes)
            'weekly': constants.RET_SEMANAL,  # Semanal
        }

        # Se obtiene el código de tabla correspondiente a la frecuencia de pago
        codigo = codigo_mapeo.get(self.schedule_pay)
        _logger.info("Frecuencia de pago: %s → Código tabla: %s", self.schedule_pay, codigo)

        if not codigo:
            # Si no se encuentra un código para la frecuencia de pago, se registra una advertencia y se retorna 0.0
            _logger.warning("No se encontró código de tabla para la frecuencia de pago '%s'", self.schedule_pay)
            return 0.0

        # Buscar la tabla de remuneración gravada según el código
        tabla_mensual = None
        if payslip.period_quincena == '2':
            tabla_mensual = self.env['hr.retencion.renta'].search([('codigo', '=', constants.RET_MENSUAL)], limit=1)
            _logger.warning("tabla mensual 1'%s'", tabla_mensual)

        tabla = self.env['hr.retencion.renta'].search([('codigo', '=', codigo)], limit=1)
        _logger.warning("quincenal '%s'", tabla)
        if not tabla:
            # Si no se encuentra la tabla correspondiente, se registra una advertencia y se retorna 0.0
            _logger.warning("No se encontró tabla de remuneración gravada con código '%s'", codigo)
            return 0.0


        # Calcular base imponible restando AFP e ISSS
        afp = self.calcular_afp(salario_bruto=salario_bruto, payslip=payslip)
        isss = self.calcular_isss(salario_bruto=salario_bruto, payslip=payslip)
        base_imponible = float_round( (salario - afp - isss), precision_digits=2)

        base_imponible_mensual = 0.0

        if payslip.period_quincena == '2' and len(primera_quincena) != 0: #calculo de afp, iss y base imponible mensual
            # primera_quincena = self.env['hr.payslip'].search(
            #     [('employee_id', '=', payslip.employee_id.id), ('period_quincena', "=", '1'),
            #      ('period_month', "=", payslip.period_month)], limit=1)

            _logger.info(">>>  %s Renta: primera_quincena", primera_quincena)

            # Calcular base imponible restando AFP e ISSS
            isss_mensual= self.calcular_isss_mensual(payslip, salario_bruto_mensual, "desde deduccion de renta")
            afp_mensual =  self.calculo_afp_mensual(salario_bruto_mensual, payslip)

            _logger.info("isss_mensual AJUSTADO %f", isss_mensual)
            _logger.info("afp_mensual AJUSTADO %f", afp_mensual)
            _logger.warning("salario_mensual '%s'", salario_bruto_mensual)

            base_imponible_mensual = float_round((salario_bruto_mensual - afp_mensual - isss_mensual), precision_digits=2)

            _logger.info("###### AFP = %.2f ", afp)
            _logger.info("###### isss = %.2f ", isss)
            _logger.info("###### base_imponible = %.2f ",  base_imponible)

        _logger.info("Base imponible renta = %.2f - %.2f - %.2f = %.2f", salario, afp, isss, base_imponible)

        renta = 0.0
        devolucion_renta = 0.0
        # Se itera sobre los tramos de la tabla para determinar el tramo aplicable
        tramos = tabla.tramo_ids.sorted(key=lambda t: t.desde)
        for tramo in tramos:
            # Verificar si la base imponible cae dentro del tramo
            if (not tramo.hasta or base_imponible <= tramo.hasta) and base_imponible >= tramo.desde:
                # Si es así, calcular la deducción de renta basada en el tramo
                exceso = float_round(base_imponible - tramo.exceso_sobre, precision_digits=2)
                _logger.info("tramo.exceso_sobre %f", tramo.exceso_sobre)
                _logger.info("exceso %f", exceso)
                resultado = tramo.cuota_fija + (exceso * tramo.porcentaje_excedente / 100)
                _logger.info("Deducción de renta calculada: %.2f (tramo aplicado)", resultado)
                renta = resultado

        _logger.info("RENTA NORMAL %f", renta)

        if payslip.period_quincena == '2' and len(primera_quincena) != 0: #calculo de afp, iss y base imponible mensual
            # primera_quincena = self.env['hr.payslip'].search(
            #     [('employee_id', '=', payslip.employee_id.id), ('period_quincena', "=", '1'),
            #      ('period_month', "=", payslip.period_month)], limit=1)
            tramos_mensual = []
            if tabla_mensual:
                tramos_mensual = tabla_mensual.tramo_ids.sorted(key=lambda t: t.desde)

            if tramos_mensual:
                for tramo in tramos_mensual:
                    # Verificar si la base imponible cae dentro del tramo
                    if (not tramo.hasta or base_imponible_mensual <= tramo.hasta) and base_imponible_mensual >= tramo.desde:
                        # Si es así, calcular la deducción de renta basada en el tramo
                        exceso = float_round(base_imponible_mensual - tramo.exceso_sobre, precision_digits=2)
                        _logger.info("tramo.exceso_sobre AJUSTADO %f", tramo.exceso_sobre)

                        _logger.info("base_imponible_mensual AJUSTADO %f", base_imponible_mensual)
                        _logger.info("tramo.exceso_sobre %f", exceso)
                        _logger.info("base imponible AJUSTADo %f", base_imponible_mensual)
                        resultado = tramo.cuota_fija + (exceso * tramo.porcentaje_excedente / 100)
                        _logger.info("Deducción de renta calculada AJUSTADA: %.2f (tramo aplicado)", resultado)

                        renta_primera_quincena = primera_quincena.input_line_ids.filtered(
                            lambda l: l.name == "Deducción Renta")

                        _logger.info("RENTA PRIMERA QUINCENA AJUSTADA: %.2f (tramo aplicado)", renta_primera_quincena.amount if renta_primera_quincena else 0.0)


                        renta = resultado - abs(renta_primera_quincena.amount if renta_primera_quincena else 0.0)
                        _logger.info("REEEE: %.2f ", renta_primera_quincena.amount if renta_primera_quincena else 0.0)
                        _logger.info("RESULTSSS: %.2f ", resultado)

                        if renta_primera_quincena and abs(renta_primera_quincena.amount) > abs(resultado):
                            _logger.info("RENTA FINAL %f", - renta)
                            devolucion_renta = abs(renta)
                            renta = 0.0
                            # AGREGAR LA REGLA SALARIAL PARA ASIGNACION

        _logger.info("RENTA AJUSTADO %f", renta)

        return renta, devolucion_renta

    # Método para calcular el aporte patronal ISSS (empleador)
    def calcular_aporte_patronal(self, tipo, salario_bruto=None, payslip=None):
        """
        Calcula el aporte patronal (ISSS o AFP) según el salario y los techos definidos.
        - tipo: constants.TIPO_DED_ISSS o constants.TIPO_DED_AFP
        - salario_bruto: base opcional. Si no se pasa, usa el salario bruto total del contrato.
        """
        self.ensure_one()
        _logger.info(">>>  %s payslippayslip", payslip)

        if self.wage_type == constants.SERVICIOS_PROFESIONALES:
            _logger.info("Contrato con servicios profesionales, no se aplica INCAF.")
            return 0.0

        # Si me pasaron salario_bruto, usarlo. Si no, calcular salario bruto total del contrato
        primera_quincena = None
        bono_lines = None
        bono_total = 0.0
        comisiones_total = 0.0
        salario_bruto_q1 = 0.0

        if payslip.period_quincena == '2':
            primera_quincena = self.env['hr.payslip'].search(
                [('employee_id', '=', payslip.employee_id.id), ('period_quincena', '=', '1'),
                 ('period_month', '=', payslip.period_month), ('company_id', '=', payslip.company_id.id), ], limit=1)
            _logger.info(">>>  %s primera_quincena", primera_quincena)

            # líneas calculadas (hr.payslip.line) dentro del slip
            if primera_quincena:
                bono_lines = primera_quincena.line_ids.filtered(lambda l: (l.code or '').upper() == 'BONO')
                # ejemplo: total del bono
                bono_total = sum(bono_lines.mapped('total'))

                # líneas calculadas (hr.payslip.line) dentro del slip
                comisiones_lines = primera_quincena.line_ids.filtered(lambda l: (l.code or '').upper() == 'COMISION')
                # ejemplo: total del comisiones
                comisiones_total = sum(comisiones_lines.mapped('total'))
                # comisiones = primera_quincena.input_line_ids.filtered(lambda l: l.code == "Comision")

                salario_bruto_q1 = self.get_salario_bruto_total(payslip=primera_quincena, salario_bruto_payslip=(primera_quincena.basic_wage))

            _logger.info(">>> bono %s", bono_total)
            _logger.info(">>> comisiones_total %s", comisiones_total)

            salario_bruto_q2 = self.get_salario_bruto_total(payslip=payslip, salario_bruto_payslip=salario_bruto)
            salario = salario_bruto_q1 + salario_bruto_q2
            _logger.info(">>>  RENTA: salario_bruto_mensual =%s", salario)
            _logger.info(">>>  RENTA: salario_bruto_q1 patorn =%s", salario_bruto_q1)
            _logger.info(">>>  RENTA: salario_bruto_q2 oatirn =%s", salario_bruto_q2)
        else:
            salario = self.get_salario_bruto_total(payslip=payslip, salario_bruto_payslip=salario_bruto)
        _logger.info("Aporte patronal: salario bruto =%s", salario)

        _logger.info("Cálculo de aporte patronal para contrato ID %s. Tipo: %s. Salario base: %.2f", self.id, tipo, salario)

        tipo_isss = None
        if tipo == constants.TIPO_DED_ISSS:
            tipo_isss = self.env['hr.retencion.isss'].search([('tipo', '=', constants.DEDUCCION_EMPLEADOR)], limit=1)

            if tipo_isss:
                rete_patronal_isss = 0.0
                if payslip.period_quincena == '2':
                    if primera_quincena:
                        _logger.info(">>>  %s primera_quincena", primera_quincena)

                        # líneas calculadas (hr.payslip.line) dentro del slip
                        rete_patronal_isss_line = primera_quincena.line_ids.filtered(lambda l: (l.code or '').upper() == 'ISSS_EMP')
                        # ejemplo: total del bono
                        rete_patronal_isss = sum(rete_patronal_isss_line.mapped('total'))

                    base = salario if tipo_isss.techo == 0.0 else min(salario, tipo_isss.techo * 2)
                    resultado = base * (tipo_isss.porcentaje / 100)
                    _logger.info("ISSS Patronal: base=%.2f, porcentaje=%.2f%%, resultado=%.2f", base,
                                 tipo_isss.porcentaje * 100, resultado)

                    _logger.info("2 quincena patronal isss =%.2f", resultado - rete_patronal_isss)
                    return float_round(resultado - rete_patronal_isss, precision_digits=2)

                base = salario if tipo_isss.techo == 0.0 else min(salario, tipo_isss.techo)
                resultado = base * (tipo_isss.porcentaje / 100)
                _logger.info("ISSS Patronal: base=%.2f, porcentaje=%.2f%%, resultado=%.2f", base, tipo_isss.porcentaje * 100, resultado)
                return float_round(resultado, precision_digits=2)
            _logger.warning("No se encontró configuración ISSS para empleador.")
            return 0.0
        elif tipo != constants.TIPO_DED_ISSS:  # afp
            tipo_afp = None
            tipo_af_ded = None
            if self.afp_id and self.afp_id == constants.AFP_IPSFA:
                tipo_afp = self.env['hr.retencion.afp'].search([('tipo', '=', constants.DEDUCCION_IPSFA_EMPLEADOR)], limit=1)
                tipo_af_ded = constants.COD_IPSFA_EMP
            elif self.afp_id and self.afp_id == constants.AFP_CONFIA:
                tipo_afp = self.env['hr.retencion.afp'].search([('tipo', '=', constants.DEDUCCION_AFP_CONF_EMPLEADOR)], limit=1)
                tipo_af_ded = constants.COD_AFP_CONF_EMP
            else:
                tipo_afp = self.env['hr.retencion.afp'].search([('tipo', '=', constants.DEDUCCION_EMPLEADOR)], limit=1)
                tipo_af_ded = constants.COD_AFP_EMP
            _logger.info("TIPO AFP: %s | COD TIPO DE ENTRADA: %s", tipo_afp, tipo_af_ded)
            _logger.info("TIPO AFP %s", tipo_afp.porcentaje)

            if tipo_afp:
                rete_patronal_afp = 0.0
                if payslip.period_quincena == '2':
                    if primera_quincena:
                        _logger.info(">>>  %s primera_quincena afp", primera_quincena)

                        # líneas calculadas (hr.payslip.line) dentro del slip
                        rete_patronal_afp_line = primera_quincena.line_ids.filtered(lambda l: (l.code or '').upper() == tipo_af_ded)
                        # ejemplo: total del bono
                        rete_patronal_afp = sum(rete_patronal_afp_line.mapped('total'))

                    base = salario if tipo_afp.techo == 0.0 else min(salario, tipo_afp.techo * 2)
                    resultado = base * (tipo_afp.porcentaje / 100)
                    _logger.info("AFP Patronal: base=%.2f, porcentaje=%.2f%%, resultado=%s, retencion patronical=%s", base, tipo_afp.porcentaje * 100, resultado, rete_patronal_afp)

                    _logger.info("2 quincena patronal afp =%s", resultado - rete_patronal_afp)
                    return float_round((resultado - rete_patronal_afp), precision_digits=2)

                base = salario if tipo_afp.techo == 0.0 else min(salario, tipo_afp.techo)
                resultado = base * (tipo_afp.porcentaje / 100)
                _logger.info("AFP Patronal: base=%.2f, porcentaje=%.2f%%, resultado=%.2f", base, tipo_afp.porcentaje * 100, resultado)
                return float_round(resultado, precision_digits=2)
            _logger.warning("No se encontró configuración AFP para empleador.")
            return 0.0

        _logger.warning("Tipo de aporte patronal desconocido o sin configuración.")
        return 0.0

    def calcular_incaf(self, salario_bruto=None, payslip=None):
        """
        Calcula la deducción del INCAF (1% del salario bruto total del empleado),
        solo si la empresa tiene activado el campo 'pago_incaf'.
        Retorna 0.0 si no aplica o si ocurre un error.
        """
        self.ensure_one()
        if self.wage_type == constants.SERVICIOS_PROFESIONALES:
            _logger.info("Contrato con servicios profesionales, no se aplica INCAF.")
            return 0.0

        try:
            empresa = self.company_id or self.employee_id.company_id
            if not empresa or not empresa.pago_incaf:
                _logger.info("Empresa no paga INCAF, se omite deducción para contrato ID %s.", self.id)
                return 0.0

            salario = self.get_salario_bruto_total(payslip=payslip, salario_bruto_payslip=salario_bruto)
            _logger.info("INCAF: salario bruto =%s", salario_bruto)
            _logger.info("INCAF: salario base para contrato ID %s = %.2f", self.id, salario)

            # Buscar la configuración de ISSS para el incaf
            isss_incaf = self.env['hr.retencion.isss'].search([('tipo', '=', constants.DEDUCCION_INCAF)], limit=1)
            if not isss_incaf:
                # Si no se encuentra configuración para INCAF, se registra una advertencia y se retorna 0.0
                _logger.warning("No se encontró configuración INCAF para empleado.")
                return 0.0

            _logger.info("Config INCAF encontrada: porcentaje=%.2f%%", isss_incaf.porcentaje)

            porcentaje = isss_incaf.porcentaje or 0.0  # Porcentaje de deducción INCAF
            techo = isss_incaf.techo or 0.0

            base = min(salario, techo) if techo > 0 else salario
            resultado = base * (porcentaje / 100.0)
            _logger.info("INCAF para contrato ID %s: %.2f * 1%% = %.2f", self.id, salario, resultado)
            return resultado

        except Exception as e:
            _logger.error("Error general al calcular INCAF para contrato ID %s: %s", self.id, e)
            return 0.0
