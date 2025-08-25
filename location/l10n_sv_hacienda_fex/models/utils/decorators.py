import logging
_logger = logging.getLogger(__name__)
# DECORADOR PARA VALIDAR SI LA EMPRESA TIENE FACTURACION ELECTRONICA ACTIVADA
def only_fe(func):
    def wrapper(self, *args, **kwargs):
        if not self.company_id.sit_facturacion:
            _logger.info(
                "SIT Facturación electrónica desactivada en %s, se omite %s",
                self.company_id.name, func.__name__
            )
            return False
        return func(self, *args, **kwargs)
    return wrapper