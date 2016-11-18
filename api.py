# This file is part of the carrier_send_shipments_correos module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Not, Equal
import logging

try:
    from correos.picking import *
except ImportError:
    logger = logging.getLogger(__name__)
    message = 'Install Correos from Pypi: pip install correos'
    logger.error(message)
    raise Exception(message)

__all__ = ['CarrierApi']


class CarrierApi:
    __metaclass__ = PoolMeta
    __name__ = 'carrier.api'
    correos_code = fields.Char('Code', states={
            'required': Eval('method') == 'correos',
            }, help='Correos Code (CodeEtiquetador)')
    correos_cc = fields.Char('CC', states={
            'required': Eval('method') == 'correos',
            }, help='Correos Bank Number')

    @classmethod
    def get_carrier_app(cls):
        '''
        Add Carrier Correos APP
        '''
        res = super(CarrierApi, cls).get_carrier_app()
        res.append(('correos', 'Correos'))
        return res

    @classmethod
    def view_attributes(cls):
        return super(CarrierApi, cls).view_attributes() + [
            ('//page[@id="correos"]', 'states', {
                    'invisible': Not(Equal(Eval('method'), 'correos')),
                    })]

    def test_correos(self, api):
        '''
        Test Correos connection
        :param api: obj
        '''
        message = 'Connection unknown result'
        
        with API(api.username, api.password, api.correos_code, api.debug) as correos_api:
            message = correos_api.test_connection()
        self.raise_user_error(message)
