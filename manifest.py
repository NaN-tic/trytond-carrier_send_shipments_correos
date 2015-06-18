# This file is part of carrier_send_shipments_correos module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from correos import Picking
from trytond.pool import PoolMeta
from trytond.transaction import Transaction
from base64 import decodestring

__all__ = ['CarrierManifest']
__metaclass__ = PoolMeta


class CarrierManifest:
    __name__ = 'carrier.manifest'

    @classmethod
    def __setup__(cls):
        super(CarrierManifest, cls).__setup__()
        cls._error_messages.update({
                'not_correos_manifest': 'Correos Manifest service is not available.',
                })

    def get_manifest_correos(self, api, from_date, to_date):
        self.raise_user_error('not_correos_manifest')
