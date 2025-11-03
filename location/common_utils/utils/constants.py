TRANSMISION_NORMAL = 1
TRANSMISION_CONTINGENCIA = 2
TIPO_CONTIN_OTRO = 5
MOT_CONTIN_OTRO = "05"
COD_DTE_FE = "01"
COD_DTE_CCF = "03"
COD_DTE_NC = "05"
COD_DTE_ND = "06"
COD_DTE_FEX = "11"
COD_DTE_FSE = "14"
COD_TIPO_DOCU_DUI = "13"
COD_TIPO_ITEM = "4"
COD_TIPO_DOC_GENERACION_DTE = 2
TIPO_VENTA_PROD_GRAV = "gravado"
TIPO_VENTA_PROD_EXENTO = "exento"
TIPO_VENTA_PROD_NO_SUJETO = "no_sujeto"
AMBIENTE_TEST = "00"

#Modulo de retenciones
DEDUCCION_EMPLEADO = "empleado"
RET_MENSUAL = "a"
RET_QUINCENAL = "b"
RET_SEMANAL = "c"
TIPO_DED_ISSS = "isss"
TIPO_DED_AFP = "afp"
DEDUCCION_EMPLEADOR = "patron"
DEDUCCION_INCAF = "incaf"
SERVICIOS_PROFESIONALES = "professional_services"
TIPOENT_FALTA = "FALTA"
REGLASAL_DESC_SEPTIMO = "DESC_FALTA_SEPTIMO"
REGLASAL_VACACION = "VACACIONES"
AFP_IPSFA = "ipsfa"
AFP_CONFIA = "confia"
AFP_CRECER = "crecer"
DEDUCCION_IPSFA_EMPLEADO = "ipsfa_empleado"
DEDUCCION_IPSFA_EMPLEADOR = "ipsfa_empleador"
DEDUCCION_AFP_CONF_EMPLEADO = "empleado_conf"
DEDUCCION_AFP_CONF_EMPLEADOR = "patron_conf"
# Deducciones comunes a todos menos servicios profesionales
BASE_DEDUCCIONES = [
    ('RENTA', 'renta', -1),
    ('ISSS', 'isss', -1),
    ('ISSS_EMP', 'isss_patronal', 1),
    ('INCAF', 'incaf', -1),
]

# AFP según tipo
AFP_IPSFA_CODES = [
    ('IPSFA', 'afp', -1),
    ('IPSFA_EMP', 'afp_patronal', 1),
]

AFP_REGULAR_CODES = [
    ('AFP', 'afp_conf', -1),
    ('AFP_EMP', 'afp_conf_patronal', 1),
]

AFP_CONF_REGULAR_CODES = [
    ('AFP_CONF', 'afp_conf', -1),
    ('AFP_CONF_EMP', 'afp_conf_patronal', 1),
]

# Todos los códigos usados
DEDUCCION_CODES = list(set(
    [c[0] for c in BASE_DEDUCCIONES + AFP_IPSFA_CODES + AFP_REGULAR_CODES + AFP_CONF_REGULAR_CODES] + ['RENTA_SP']
))

CONST_CODIGOS_APORTES_PATRONALES = ['AFP_EMP', 'AFP_CONF_EMP', 'ISSS_EMP', 'INCAF', 'IPSFA_EMP']
CONST_CODIGOS_DEDUCCIONES_EMPLEADO = ['AFP', 'AFP_CONF', 'ISSS', 'RENTA', 'FSV', 'FONDO_PENSIONES', 'PRESTAMOS', 'VENTA_EMPLEADOS', 'OTROS', 'RENTA_SP', 'BANCO', 'DESC_FALTA_SEPTIMO', 'FALTA_INJ', 'IPSFA']
COD_ISSS_EMP = "ISSS_EMP"
COD_AFP_EMP = "AFP_EMP"
COD_AFP_CONF_EMP = "AFP_CONF_EMP"
COD_IPSFA_EMP = "IPSFA_EMP"
REGLAS_EXCLUIR_SERVICIOS_PROFESIONALES = {'RENTA', 'ISSS', 'AFP', 'AFP_EMP', 'AFP_CONF', 'AFP_CONF_EMP', 'ISSS_EMP', 'INCAF', 'IPSFA', 'IPSFA_EMP'}
CAMPOS_MANY2ONE_REGLAS = {'category_id', 'account_debit', 'account_credit', 'amount_other_input_id', 'condition_other_input_id'}

#Modulo de asignaciones salariales
ASIGNACION_COMISIONES = "comision"
ASIGNACION_VIATICOS = "viatico"
ASIGNACION_BONOS = "bono"
ASIGNACION_HORAS_EXTRA = "overtime"
HORAS_DIURNAS = "horas_diurnas"
HORAS_NOCTURNAS = "horas_nocturnas"
HORAS_DIURNAS_DESCANSO = "horas_diurnas_descanso"
HORAS_NOCTURNAS_DESCANSO = "horas_nocturnas_descanso"
HORAS_DIURNAS_ASUETO = "horas_diurnas_asueto"
HORAS_NOCTURNAS_ASUETO = "horas_nocturnas_asueto"
PERIODO = "periodo"
NOMBRE_PLANTILLA_ASIGNACIONES = "Plantilla de Asignaciones"
NOMBRE_PLANTILLA_ASISTENCIA = "Plantilla de Asistencia"
NOMBRE_PLANTILLA_DEDUCCIONES = "Plantilla de deducciones"
NOMBRE_PLANTILLA_TIEMPO_PERSONAL = "Plantilla tiempo personal"
CODES_VACACIONES = ['VAC', 'VACACIONES']

CUENTAS_ASIGNACIONES = {
    'cuenta_salarial_deducciones_credito': 'cuenta_salarial_deducciones',
    'cuenta_salarial_deducciones_debito': 'cuenta_salarial_debito',
}
CODIGOS_REGLAS_ASIGNACIONES = ['COMISION', 'VIATICO', 'BONO', 'OVERTIME', 'DEV_RENTA']

# Conversión de schedule_pay → factor para convertir a salario mensual
SCHEDULE_PAY_CONVERSION = {
    'monthly': 1,
    'semi-monthly': 2,        # quincenal
    'bi-weekly': 52 / 12 / 2,   # 26 pagos/año → mensual ≈ 2.1666
    'weekly': 52 / 12,          # 4.3333 semanas por mes
    'daily': 30,              # 30 días promedio en un mes
    'bimonthly': 0.5,           # cada 2 meses
    'quarterly': 1 / 3,
    'semi-annually': 1 / 6,
    'annually': 1 / 12,
}

# Mapping estructuras
STRUCTURE_MAPPING = {'INCOE': ['PLAN_VAC', 'PLAN_PRO']}
STRUCTURE_PLAN_PROD = "PLAN_PRO"

ITEM_SERVICIOS = "2"
COD_TD_DUI = "13"

DEVOLUCION_RENTA_CODE = 'DEV_RENTA'

TYPE_REPORT_CCF = "ccf"
TYPE_REPORT_NDC = "ndc"

# Tipos de movimiento
IN_INVOICE = "in_invoice"
IN_REFUND = "in_refund"
OUT_INVOICE = "out_invoice"
OUT_REFUND = "out_refund"
TYPE_VENTA = "sale"
TYPE_COMPRA = "purchase"
TYPE_ENTRY = "entry"
OUT_RECEIPT = "out_receipt"
IN_RECEIPT = "in_receipt"
TYPE_SALIDA = "outgoing"
TYPE_RECEPCION = "incoming"

# Identificacion documentos electronicos
DTE_COD = 4

#Clave de porcentajes configurados desde compañía
config_percepcion = "percepcion"
config_retencion_iva = "retencion_iva"
config_iva_rete = "retencion_iva_venta"
config_retencion_venta = "retencion_venta"
config_iva_percibido_venta = "iva_percibido_venta"