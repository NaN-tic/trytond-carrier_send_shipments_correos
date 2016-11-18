# This file is part of the carrier_send_shipments_correos module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from correos.picking import Picking
from correos.utils import delivery_oficina
from trytond.modules.carrier_send_shipments.tools import unaccent
from base64 import decodestring
import logging
import tempfile

__all__ = ['ShipmentOut']
__metaclass__ = PoolMeta

logger = logging.getLogger(__name__)


class ShipmentOut:
    __name__ = 'stock.shipment.out'

    @classmethod
    def __setup__(cls):
        super(ShipmentOut, cls).__setup__()
        cls._error_messages.update({
            'correos_add_services': 'Select a service or default service in Correos API',
            'correos_not_country': 'Add country in shipment "%(name)s" delivery address',
            'correos_not_price': 'Shipment "%(name)s" not have price and send '
                'cashondelivery',
            'correos_error_zip': 'Correos not accept zip "%(zip)s"',
            'correos_not_send': 'Not send shipment %(name)s',
            'correos_not_send_error': 'Not send shipment %(name)s. %(error)s',
            'correos_not_label': 'Not available "%(name)s" label from Correos',
            'correos_add_oficina': 'Add a office Correos to delivery or change service',
            })

    @staticmethod
    def correos_picking_data(api, shipment, service, price=None, weight=False, correos_oficina=None):
        '''
        Correos Picking Data
        :param api: obj
        :param shipment: obj
        :param service: str
        :param price: string
        :param weight: bol
        :param correos_oficina: str
        Return data
        '''
        Uom = Pool().get('product.uom')

        packages = shipment.number_packages
        if not packages or packages == 0:
            packages = 1

        remitente_address = shipment.warehouse.address or shipment.company.party.addresses[0]
        
        if api.reference_origin and hasattr(shipment, 'origin'):
            code = shipment.origin and shipment.origin.rec_name or shipment.code
        else:
            code = shipment.code

        notes = ''
        if shipment.carrier_notes:
            notes = '%s\n' % shipment.carrier_notes

        data = {}
        data['TotalBultos'] = packages
        data['RemitenteNombre'] = shipment.company.party.name
        data['RemitenteNif'] = shipment.company.party.vat_code or shipment.company.party.identifier_code
        data['RemitenteDireccion'] = unaccent(remitente_address.street)
        data['RemitenteLocalidad'] = unaccent(remitente_address.city)
        data['RemitenteProvincia'] = remitente_address.subdivision and unaccent(remitente_address.subdivision.name) or ''
        data['RemitenteCP'] = remitente_address.zip
        data['RemitenteTelefonocontacto'] = remitente_address.phone or shipment.company.party.get_mechanism('phone')
        data['RemitenteEmail'] = remitente_address.email or shipment.company.party.get_mechanism('email')
        data['DestinatarioNombre'] = unaccent(shipment.customer.name)
        data['DestinatarioDireccion'] = unaccent(shipment.delivery_address.street)
        data['DestinatarioLocalidad'] = unaccent(shipment.delivery_address.city)
        data['DestinatarioProvincia'] = shipment.delivery_address.subdivision and unaccent(shipment.delivery_address.subdivision.name) or ''
        data['DestinatarioCP'] = shipment.delivery_address.zip
        data['DestinatarioPais'] = shipment.delivery_address.country and shipment.delivery_address.country.code or ''
        data['DestinatarioTelefonocontacto'] = shipment.delivery_address.phone or shipment.customer.get_mechanism('phone')
        data['DestinatarioNumeroSMS'] = shipment.delivery_address.mobile or shipment.customer.get_mechanism('mobile')
        data['DestinatarioEmail'] = shipment.delivery_address.email or shipment.customer.get_mechanism('email')
        data['CodProducto'] = service.code
        data['ReferenciaCliente'] = code
        data['Observaciones1'] =  unaccent(notes)

        if shipment.carrier_cashondelivery and price:
            data['Reembolso'] = True
            data['TipoReembolso'] = 'RC'
            data['Importe'] = price
            data['NumeroCuenta'] = api.correos_cc

        if weight and hasattr(shipment, 'weight_func'):
            weight = shipment.weight_func
            if weight == 0:
                weight = 1
            if api.weight_api_unit:
                if shipment.weight_uom:
                    weight = Uom.compute_qty(
                        shipment.weight_uom, weight, api.weight_api_unit)
                elif api.weight_unit:
                    weight = Uom.compute_qty(
                        api.weight_unit, weight, api.weight_api_unit)
            data['peso'] = str(weight)

        if correos_oficina:
            data['OficinaElegida'] = correos_oficina

        return data

    @classmethod
    def send_correos(self, api, shipments):
        '''
        Send shipments out to correos
        :param api: obj
        :param shipments: list
        Return references, labels, errors
        '''
        pool = Pool()
        CarrierApi = pool.get('carrier.api')
        ShipmentOut = pool.get('stock.shipment.out')

        references = []
        labels = []
        errors = []

        default_service = CarrierApi.get_default_carrier_service(api)
        dbname = Transaction().cursor.dbname

        with Picking(api.username, api.password, api.correos_code,
                timeout=api.timeout, debug=api.debug) as picking_api:
            for shipment in shipments:
                service = shipment.carrier_service or shipment.carrier.service or default_service
                if not service:
                    message = self.raise_user_error('correos_add_services', {},
                        raise_exception=False)
                    errors.append(message)
                    continue

                correos_oficina = None
                services_oficina = delivery_oficina()
                if service.code in services_oficina:
                    if not shipment.delivery_address.correos:
                        message = self.raise_user_error('correos_add_oficina', {},
                            raise_exception=False)
                        errors.append(message)
                        continue
                    correos_oficina = shipment.delivery_address.correos

                if not shipment.delivery_address.country:
                    message = self.raise_user_error('correos_not_country', {},
                        raise_exception=False)
                    errors.append(message)
                    continue

                price = None
                if shipment.carrier_cashondelivery:
                    price = ShipmentOut.get_price_ondelivery_shipment_out(shipment)
                    if not price:
                        message = self.raise_user_error('correos_not_price', {
                                'name': shipment.rec_name,
                                }, raise_exception=False)
                        errors.append(message)
                        continue

                data = self.correos_picking_data(api, shipment, service, price, api.weight, correos_oficina)
                reference, label, error = picking_api.create(data)

                if reference:
                    self.write([shipment], {
                        'carrier_tracking_ref': reference,
                        'carrier_service': service,
                        'carrier_delivery': True,
                        'carrier_printed': True,
                        'carrier_send_date': ShipmentOut.get_carrier_date(),
                        'carrier_send_employee': ShipmentOut.get_carrier_employee() or None,
                        })
                    logger.info('Send shipment %s' % (shipment.code))
                    references.append(shipment.code)
                else:
                    logger.error('Not send shipment %s.' % (shipment.code))

                if label:
                    with tempfile.NamedTemporaryFile(
                            prefix='%s-correos-%s-' % (dbname, reference),
                            suffix='.pdf', delete=False) as temp:
                        temp.write(decodestring(label))
                    logger.info('Generated tmp label %s' % (temp.name))
                    temp.close()
                    labels.append(temp.name)
                else:
                    message = self.raise_user_error('correos_not_label', {
                            'name': shipment.rec_name,
                            }, raise_exception=False)
                    errors.append(message)
                    logger.error(message)

                if error:
                    message = self.raise_user_error('correos_not_send_error', {
                            'name': shipment.rec_name,
                            'error': error,
                            }, raise_exception=False)
                    logger.error(message)
                    errors.append(message)

        return references, labels, errors

    @classmethod
    def print_labels_correos(self, api, shipments):
        '''
        Get labels from shipments out from Correos
        Not available labels from Correos API. Not return labels
        '''
        labels = []
        dbname = Transaction().cursor.dbname

        with Picking(api.username, api.password, api.correos_code,
                timeout=api.timeout, debug=api.debug) as picking_api:
            for shipment in shipments:
                if not shipment.carrier_tracking_ref:
                    logger.error(
                        'Shipment %s has not been sent by Correos.'
                        % (shipment.code))
                    continue

                reference = shipment.carrier_tracking_ref

                data = {}
                data['CodEnvio'] = reference
                label = picking_api.label(data)

                if not label:
                    logger.error(
                        'Label for shipment %s is not available from Correos.'
                        % shipment.code)
                    continue
                with tempfile.NamedTemporaryFile(
                        prefix='%s-correos-%s-' % (dbname, reference),
                        suffix='.pdf', delete=False) as temp:
                    temp.write(decodestring(label))
                logger.info(
                    'Generated tmp label %s' % (temp.name))
                temp.close()
                labels.append(temp.name)
            self.write(shipments, {'carrier_printed': True})

        return labels
