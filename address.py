# This file is part of the carrier_send_shipments_correos module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta

__all__ = ['Address']


class Address:
    __metaclass__ = PoolMeta
    __name__ = 'party.address'
    correos = fields.Char('Correos',
        help='Office Correos code to delivery shipment')
