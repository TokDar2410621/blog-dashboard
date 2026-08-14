"""Tests for the JSON-LD builders and the Product merchant validator.

Pure data in, pure data out: nothing here touches the network, the ORM or the
filesystem, so no mocking is needed at all.

Run all:
    python manage.py test sites_mgmt.tests_schema_builder
"""
from django.test import SimpleTestCase

from .schema_builder import (
    build_area_served, build_profile_page, build_service,
    has_blocking_findings, summarize_findings, validate_product,
)


def _rules(findings):
    return [f['rule'] for f in findings]


def _by_rule(findings, rule):
    return [f for f in findings if f['rule'] == rule]


class BuildProfilePageTests(SimpleTestCase):
    def test_minimal_profile(self):
        page = build_profile_page({'name': 'Marie Tremblay'})
        self.assertEqual(page['@context'], 'https://schema.org')
        self.assertEqual(page['@type'], 'ProfilePage')
        self.assertEqual(page['mainEntity']['@type'], 'Person')
        self.assertEqual(page['mainEntity']['name'], 'Marie Tremblay')
        self.assertEqual(page['inLanguage'], 'fr-CA')

    def test_name_is_required(self):
        with self.assertRaises(ValueError):
            build_profile_page({'url': 'https://exemple.ca/a-propos'})

    def test_reads_site_model_field_names(self):
        """An integrator hands over Site.* fields without remapping them."""
        page = build_profile_page({
            'default_author': 'Darius Tokam',
            'author_role': 'Fondateur',
            'author_bio': 'Il construit des outils SEO.',
            'author_image_url': 'https://gridar.app/darius.jpg',
            'author_linkedin': 'https://linkedin.com/in/darius',
            'author_website': 'https://gridar.app/a-propos',
        })
        entity = page['mainEntity']
        self.assertEqual(entity['name'], 'Darius Tokam')
        self.assertEqual(entity['jobTitle'], 'Fondateur')
        self.assertEqual(entity['description'], 'Il construit des outils SEO.')
        self.assertEqual(entity['image'], 'https://gridar.app/darius.jpg')
        self.assertEqual(entity['url'], 'https://gridar.app/a-propos')

    def test_same_as_dedupes_and_drops_non_urls(self):
        page = build_profile_page({
            'name': 'Marie Tremblay',
            'url': 'https://exemple.ca/marie',
            'same_as': ['https://github.com/marie', 'https://github.com/marie',
                        '/relative', 'ftp://exemple.ca/x', ''],
            'linkedin': 'https://linkedin.com/in/marie',
        })
        self.assertEqual(page['mainEntity']['sameAs'], [
            'https://github.com/marie', 'https://linkedin.com/in/marie',
        ])

    def test_same_as_never_points_back_at_the_profile(self):
        page = build_profile_page({
            'name': 'Marie Tremblay',
            'url': 'https://exemple.ca/marie',
            'same_as': ['https://exemple.ca/marie/'],
        })
        self.assertNotIn('sameAs', page['mainEntity'])

    def test_knows_about_keeps_entity_links(self):
        page = build_profile_page({
            'name': 'Marie Tremblay',
            'knows_about': [
                'SEO local',
                {'name': 'Fiscalite quebecoise',
                 'same_as': ['https://fr.wikipedia.org/wiki/Impot_au_Quebec',
                             'https://www.wikidata.org/wiki/Q1']},
            ],
        })
        topics = page['mainEntity']['knowsAbout']
        self.assertEqual(topics[0], 'SEO local')
        self.assertEqual(topics[1]['@type'], 'Thing')
        self.assertEqual(len(topics[1]['sameAs']), 2)

    def test_credentials_textarea_becomes_credential_nodes(self):
        page = build_profile_page({
            'name': 'Marie Tremblay',
            'author_credentials': 'Membre du Barreau du Quebec\nMBA HEC Montreal\n',
        })
        credentials = page['mainEntity']['hasCredential']
        self.assertEqual(len(credentials), 2)
        self.assertEqual(credentials[0]['@type'], 'EducationalOccupationalCredential')
        self.assertEqual(credentials[1]['name'], 'MBA HEC Montreal')

    def test_person_gets_a_stable_id_anchored_on_the_url(self):
        page = build_profile_page({'name': 'Marie', 'url': 'https://exemple.ca/marie'})
        self.assertEqual(page['mainEntity']['@id'], 'https://exemple.ca/marie#person')

    def test_no_id_without_a_url(self):
        page = build_profile_page({'name': 'Marie'})
        self.assertNotIn('@id', page['mainEntity'])

    def test_bare_domain_is_promoted_to_https(self):
        page = build_profile_page({'name': 'Marie', 'url': 'exemple.ca/marie'})
        self.assertEqual(page['url'], 'https://exemple.ca/marie')

    def test_language_override(self):
        page = build_profile_page({'name': 'Marie', 'language': 'en'})
        self.assertEqual(page['inLanguage'], 'en-CA')

    def test_organization_profile(self):
        page = build_profile_page({'name': 'Gridar', 'entity_type': 'Organization',
                                   'url': 'https://gridar.app'})
        self.assertEqual(page['mainEntity']['@type'], 'Organization')
        self.assertEqual(page['mainEntity']['@id'], 'https://gridar.app#organization')
        self.assertNotIn('jobTitle', page['mainEntity'])

    def test_unknown_entity_type_refused(self):
        with self.assertRaises(ValueError):
            build_profile_page({'name': 'Gridar', 'entity_type': 'Robot'})

    def test_empty_fields_never_reach_the_output(self):
        page = build_profile_page({'name': 'Marie', 'bio': '', 'image': None,
                                   'knows_about': [], 'email': '   '})
        self.assertEqual(set(page['mainEntity']), {'@type', 'name'})


class BuildAreaServedTests(SimpleTestCase):
    def test_known_city_is_nested_in_quebec_and_canada(self):
        node = build_area_served('Montreal')
        self.assertEqual(node['@type'], 'City')
        self.assertEqual(node['name'], 'Montréal')
        self.assertEqual(node['containedInPlace']['name'], 'Québec')
        self.assertEqual(node['containedInPlace']['containedInPlace']['name'], 'Canada')

    def test_matching_ignores_accents_case_and_punctuation(self):
        for raw in ('Trois-Rivieres', 'trois rivières', 'TROIS-RIVIÈRES'):
            self.assertEqual(build_area_served(raw)['name'], 'Trois-Rivières', raw)

    def test_saint_abbreviations_resolve(self):
        for raw in ('St-Jerome', 'st jérôme', 'Saint-Jérôme'):
            self.assertEqual(build_area_served(raw)['name'], 'Saint-Jérôme', raw)
        self.assertEqual(build_area_served('Ste-Julie')['name'], 'Sainte-Julie')

    def test_bare_quebec_is_the_province(self):
        """Alone, 'Québec' means the province far more often than the city."""
        for raw in ('Québec', 'quebec', 'QC'):
            node = build_area_served(raw)
            self.assertEqual(node['@type'], 'State', raw)
            self.assertEqual(node['name'], 'Québec')

    def test_explicit_forms_give_the_city(self):
        for raw in ('Ville de Québec', 'Quebec City'):
            node = build_area_served(raw)
            self.assertEqual(node['@type'], 'City', raw)
            self.assertEqual(node['name'], 'Québec')

    def test_administrative_regions(self):
        node = build_area_served('monteregie')
        self.assertEqual(node['@type'], 'AdministrativeArea')
        self.assertEqual(node['name'], 'Montérégie')
        self.assertEqual(
            build_area_served('Saguenay-Lac-St-Jean')['name'], 'Saguenay-Lac-Saint-Jean',
        )

    def test_informal_zones_stay_places(self):
        node = build_area_served('rive sud')
        self.assertEqual(node['@type'], 'Place')
        self.assertEqual(node['name'], 'Rive-Sud')
        self.assertEqual(node['containedInPlace']['name'], 'Québec')

    def test_postal_prefix_becomes_a_geoshape(self):
        self.assertEqual(build_area_served('h2x'), {
            '@type': 'GeoShape', 'addressCountry': 'CA', 'postalCode': 'H2X',
        })
        self.assertEqual(build_area_served('J4K 2N1')['postalCode'], 'J4K')

    def test_country(self):
        self.assertEqual(build_area_served('Canada'), {'@type': 'Country', 'name': 'Canada'})

    def test_unknown_zone_is_kept_verbatim(self):
        """An unknown area is worth less than a known one and more than nothing."""
        node = build_area_served('Secteur des Deux-Rives')
        self.assertEqual(node, {'@type': 'Place', 'name': 'Secteur des Deux-Rives'})

    def test_prebuilt_node_passes_through(self):
        given = {'@type': 'GeoCircle', 'geoRadius': '25000'}
        self.assertEqual(build_area_served(given), given)

    def test_dict_with_explicit_type(self):
        node = build_area_served({'name': 'Ottawa', 'type': 'City'})
        self.assertEqual(node, {'@type': 'City', 'name': 'Ottawa'})

    def test_empty_zone(self):
        self.assertEqual(build_area_served('   '), {})


class BuildServiceTests(SimpleTestCase):
    site = {
        'name': 'Plomberie Tremblay',
        'domain': 'plomberietremblay.ca',
        'telephone': '+1-514-555-0142',
    }

    def test_minimal_service(self):
        payload = build_service(self.site, {'name': 'Debouchage de drain'})
        self.assertEqual(payload['@context'], 'https://schema.org')
        self.assertEqual(payload['@type'], 'Service')
        self.assertEqual(payload['name'], 'Debouchage de drain')
        self.assertEqual(payload['provider']['name'], 'Plomberie Tremblay')
        self.assertEqual(payload['provider']['url'], 'https://plomberietremblay.ca')

    def test_service_type_defaults_to_the_name(self):
        payload = build_service(self.site, {'name': 'Debouchage de drain'})
        self.assertEqual(payload['serviceType'], 'Debouchage de drain')
        payload = build_service(self.site, {'name': 'Debouchage de drain',
                                            'service_type': 'Plomberie'})
        self.assertEqual(payload['serviceType'], 'Plomberie')

    def test_provider_is_local_business_only_with_an_address(self):
        without = build_service(self.site, {'name': 'X'})
        self.assertEqual(without['provider']['@type'], 'Organization')

        with_address = build_service(
            dict(self.site, address={'street': '12 rue Principale',
                                     'city': 'Longueuil', 'region': 'QC',
                                     'postal_code': 'J4K 2N1'}),
            {'name': 'X'},
        )
        self.assertEqual(with_address['provider']['@type'], 'LocalBusiness')
        self.assertEqual(with_address['provider']['address'], {
            '@type': 'PostalAddress',
            'streetAddress': '12 rue Principale',
            'addressLocality': 'Longueuil',
            'addressRegion': 'QC',
            'postalCode': 'J4K 2N1',
            'addressCountry': 'CA',
        })

    def test_address_country_defaults_to_ca_but_region_is_never_guessed(self):
        payload = build_service(
            dict(self.site, address={'street': '5 rue Bank', 'city': 'Ottawa'}),
            {'name': 'X'},
        )
        address = payload['provider']['address']
        self.assertEqual(address['addressCountry'], 'CA')
        self.assertNotIn('addressRegion', address)

    def test_quebec_zones_resolve_through_area_served(self):
        payload = build_service(self.site, {
            'name': 'Debouchage', 'area_served': ['montreal', 'Monteregie', 'Rive-Sud'],
        })
        self.assertEqual(
            [(a['@type'], a['name']) for a in payload['areaServed']],
            [('City', 'Montréal'), ('AdministrativeArea', 'Montérégie'),
             ('Place', 'Rive-Sud')],
        )

    def test_zones_fall_back_to_the_site_level(self):
        payload = build_service(dict(self.site, area_served=['Laval']), {'name': 'X'})
        self.assertEqual(payload['areaServed'][0]['name'], 'Laval')

    def test_relative_service_url_is_joined_to_the_domain(self):
        payload = build_service(self.site, {'name': 'X', 'url': '/services/debouchage'})
        self.assertEqual(payload['url'], 'https://plomberietremblay.ca/services/debouchage')

    def test_french_price_is_normalized_and_priced_in_cad(self):
        payload = build_service(self.site, {'name': 'X', 'price': '1 299,99 $'})
        self.assertEqual(payload['offers'],
                         {'@type': 'Offer', 'priceCurrency': 'CAD', 'price': '1299.99'})

    def test_price_range_becomes_a_price_specification(self):
        payload = build_service(self.site, {'name': 'X', 'price_min': '150',
                                            'price_max': '450,50'})
        self.assertEqual(payload['offers']['priceSpecification'], {
            '@type': 'PriceSpecification', 'priceCurrency': 'CAD',
            'minPrice': '150', 'maxPrice': '450.50',
        })

    def test_no_offer_without_a_price(self):
        self.assertNotIn('offers', build_service(self.site, {'name': 'X'}))

    def test_french_availability_is_mapped_to_the_enum(self):
        payload = build_service(self.site, {'name': 'X', 'price': '99',
                                            'availability': 'En stock'})
        self.assertEqual(payload['offers']['availability'], 'https://schema.org/InStock')

    def test_offer_catalog(self):
        payload = build_service(self.site, {
            'name': 'Plomberie',
            'catalog': ['Inspection par camera',
                        {'name': 'Nettoyage haute pression', 'price': '250,00 $'}],
        })
        catalog = payload['hasOfferCatalog']
        self.assertEqual(catalog['@type'], 'OfferCatalog')
        self.assertEqual(catalog['itemListElement'][0]['itemOffered']['name'],
                         'Inspection par camera')
        self.assertEqual(catalog['itemListElement'][1]['price'], '250.00')
        self.assertEqual(catalog['itemListElement'][1]['priceCurrency'], 'CAD')

    def test_available_channel_carries_the_language(self):
        payload = build_service(self.site, {'name': 'X'})
        self.assertEqual(payload['availableChannel']['availableLanguage'],
                         {'@type': 'Language', 'name': 'French', 'alternateName': 'fr-CA'})
        english = build_service(dict(self.site, default_language='en'), {'name': 'X'})
        self.assertEqual(
            english['availableChannel']['availableLanguage']['alternateName'], 'en-CA',
        )

    def test_provider_same_as_excludes_the_site_url_and_the_author_socials(self):
        payload = build_service(
            dict(self.site, facebook='https://facebook.com/tremblay',
                 author_linkedin='https://linkedin.com/in/darius',
                 website='https://plomberietremblay.ca'),
            {'name': 'X'},
        )
        self.assertEqual(payload['provider']['sameAs'], ['https://facebook.com/tremblay'])

    def test_names_are_required(self):
        with self.assertRaises(ValueError):
            build_service(self.site, {'description': 'sans nom'})
        with self.assertRaises(ValueError):
            build_service({'domain': 'exemple.ca'}, {'name': 'X'})


class ValidateProductRetiredTypesTests(SimpleTestCase):
    def test_june_2025_retirements_are_critical(self):
        for kind in ('Vehicle', 'VehicleListing', 'ClaimReview',
                     'EstimatedSalary', 'LearningVideo'):
            findings = validate_product({'@type': kind})
            retired = _by_rule(findings, 'retired-type')
            self.assertEqual(len(retired), 1, kind)
            self.assertEqual(retired[0]['severity'], 'critical', kind)
            self.assertTrue(retired[0]['critical'], kind)
            self.assertEqual(retired[0]['retired'], '2025-06', kind)

    def test_special_announcement_is_the_july_2025_retirement(self):
        finding = _by_rule(validate_product({'@type': 'SpecialAnnouncement'}),
                           'retired-type')[0]
        self.assertEqual(finding['severity'], 'critical')
        self.assertEqual(finding['retired'], '2025-07')
        self.assertIn('juillet 2025', finding['message'])

    def test_course_is_flagged_without_blocking(self):
        """Only the Course Info carousel went away; the rich result still runs."""
        finding = _by_rule(validate_product({'@type': 'Course'}), 'retired-type')[0]
        self.assertEqual(finding['severity'], 'medium')
        self.assertFalse(finding['critical'])

    def test_retired_type_nested_in_a_graph_is_caught(self):
        payload = {'@context': 'https://schema.org', '@graph': [
            {'@type': 'WebPage', 'mainEntity': {'@type': 'ClaimReview'}},
        ]}
        self.assertIn('retired-type', _rules(validate_product(payload)))

    def test_live_types_are_not_flagged(self):
        findings = validate_product({'@type': 'Product', 'name': 'X'})
        self.assertNotIn('retired-type', _rules(findings))


def _valid_product():
    return {
        '@context': 'https://schema.org',
        '@type': 'Product',
        'name': 'Tuque en laine merinos',
        'description': 'Tuque tricotee au Quebec, laine merinos.',
        'image': ['https://boutique.ca/tuque.jpg'],
        'hasMemberProgram': {'@type': 'MemberProgram', 'name': 'Club'},
        'offers': {
            '@type': 'Offer',
            'price': '49.99',
            'priceCurrency': 'CAD',
            'availability': 'https://schema.org/InStock',
            'hasMerchantReturnPolicy': {
                '@type': 'MerchantReturnPolicy',
                'applicableCountry': ['CA'],
                'returnPolicyCategory': 'https://schema.org/MerchantReturnFiniteReturnWindow',
                'merchantReturnDays': 30,
            },
            'shippingDetails': {
                '@type': 'OfferShippingDetails',
                'shippingDestination': {'@type': 'DefinedRegion', 'addressCountry': 'CA'},
                'deliveryTime': {'@type': 'ShippingDeliveryTime'},
            },
        },
    }


class ValidateProductMerchantRulesTests(SimpleTestCase):
    def test_a_complete_product_has_nothing_blocking(self):
        findings = validate_product(_valid_product())
        self.assertFalse(has_blocking_findings(findings), _rules(findings))
        self.assertEqual(_rules(findings), ['no-product-group'])

    def test_missing_required_fields(self):
        findings = validate_product({'@type': 'Product'})
        for rule in ('missing-product-name', 'missing-product-image',
                     'missing-product-offers'):
            self.assertIn(rule, _rules(findings))
        self.assertTrue(has_blocking_findings(findings))

    def test_missing_description_is_only_recommended(self):
        product = _valid_product()
        del product['description']
        finding = _by_rule(validate_product(product), 'recommended-product-description')[0]
        self.assertEqual(finding['severity'], 'medium')

    def test_no_product_block_at_all(self):
        findings = validate_product({'@type': 'Service', 'name': 'Plomberie'})
        self.assertIn('missing-product', _rules(findings))

    def test_aggregate_offer_is_refused(self):
        product = _valid_product()
        product['offers']['@type'] = 'AggregateOffer'
        finding = _by_rule(validate_product(product), 'merchant-listing-offer-type')[0]
        self.assertEqual(finding['severity'], 'high')
        self.assertIn('AggregateOffer', finding['message'])

    def test_relative_image_is_refused(self):
        product = _valid_product()
        product['image'] = ['/media/tuque.jpg']
        self.assertIn('image-not-absolute', _rules(validate_product(product)))

    def test_missing_return_policy_and_shipping(self):
        product = _valid_product()
        del product['offers']['hasMerchantReturnPolicy']
        del product['offers']['shippingDetails']
        rules = _rules(validate_product(product))
        self.assertIn('missing-return-policy', rules)
        self.assertIn('missing-shipping-details', rules)

    def test_return_policy_subfields(self):
        product = _valid_product()
        product['offers']['hasMerchantReturnPolicy'] = {'@type': 'MerchantReturnPolicy'}
        rules = _rules(validate_product(product))
        self.assertIn('return-policy-applicableCountry', rules)
        self.assertIn('return-policy-returnPolicyCategory', rules)

    def test_member_program_is_only_informational(self):
        product = _valid_product()
        del product['hasMemberProgram']
        finding = _by_rule(validate_product(product), 'missing-member-program')[0]
        self.assertEqual(finding['severity'], 'info')

    def test_product_group_note_disappears_when_declared(self):
        payload = {'@type': 'ProductGroup', 'hasVariant': [_valid_product()]}
        self.assertNotIn('no-product-group', _rules(validate_product(payload)))

    def test_eu_energy_class_is_opt_in(self):
        product = _valid_product()
        self.assertNotIn('missing-eu-energy-class', _rules(validate_product(product)))
        self.assertIn('missing-eu-energy-class',
                      _rules(validate_product(product, require_eu_energy=True)))

    def test_findings_are_sorted_critical_first(self):
        payload = {'@type': ['Product', 'ClaimReview']}
        severities = [f['severity'] for f in validate_product(payload)]
        self.assertEqual(severities[0], 'critical')
        self.assertEqual(severities, sorted(
            severities, key=['critical', 'high', 'medium', 'info'].index,
        ))

    def test_summary(self):
        summary = summarize_findings(validate_product({'@type': 'Product'}))
        self.assertEqual(summary['high'], 3)
        self.assertFalse(summary['ok'])
        self.assertEqual(summary['total'], summary['critical'] + summary['high']
                         + summary['medium'] + summary['info'])


class ValidateProductFrenchLocaleTests(SimpleTestCase):
    """The traps a Quebec catalogue exports: valid JSON, refused listing."""

    def test_french_availability_text(self):
        product = _valid_product()
        product['offers']['availability'] = 'En stock'
        finding = _by_rule(validate_product(product), 'availability-free-text')[0]
        self.assertEqual(finding['severity'], 'high')
        self.assertEqual(finding['suggestion'], 'https://schema.org/InStock')

    def test_other_french_availability_phrasings(self):
        cases = {
            'Rupture de stock': 'OutOfStock',
            'epuise': 'OutOfStock',
            'Sur commande': 'BackOrder',
            'En precommande': 'PreOrder',
            'Vendu au complet': 'SoldOut',
            'Quantite limitee': 'LimitedAvailability',
            'in stock': 'InStock',
        }
        for text, expected in cases.items():
            product = _valid_product()
            product['offers']['availability'] = text
            finding = _by_rule(validate_product(product), 'availability-free-text')[0]
            self.assertEqual(finding['suggestion'],
                             f'https://schema.org/{expected}', text)

    def test_unmappable_availability(self):
        product = _valid_product()
        product['offers']['availability'] = 'Nous appeler'
        self.assertIn('availability-unknown', _rules(validate_product(product)))

    def test_bare_enum_name_is_accepted(self):
        product = _valid_product()
        product['offers']['availability'] = 'InStock'
        rules = _rules(validate_product(product))
        self.assertNotIn('availability-free-text', rules)
        self.assertNotIn('availability-unknown', rules)

    def test_comma_decimal_price(self):
        product = _valid_product()
        product['offers']['price'] = '19,99 $'
        finding = _by_rule(validate_product(product), 'price-locale-format')[0]
        self.assertEqual(finding['severity'], 'high')
        self.assertEqual(finding['suggestion'], '19.99')

    def test_grouped_thousands_price(self):
        product = _valid_product()
        product['offers']['price'] = '1 299,99'
        self.assertEqual(
            _by_rule(validate_product(product), 'price-locale-format')[0]['suggestion'],
            '1299.99',
        )

    def test_unreadable_price(self):
        product = _valid_product()
        product['offers']['price'] = 'Sur demande'
        self.assertIn('price-not-numeric', _rules(validate_product(product)))

    def test_plain_prices_pass(self):
        for price in ('49.99', 49.99, 50, '0'):
            product = _valid_product()
            product['offers']['price'] = price
            rules = _rules(validate_product(product))
            self.assertNotIn('price-locale-format', rules, repr(price))
            self.assertNotIn('price-not-numeric', rules, repr(price))

    def test_currency_symbol_instead_of_iso_code(self):
        product = _valid_product()
        product['offers']['priceCurrency'] = '$'
        finding = _by_rule(validate_product(product), 'currency-not-iso')[0]
        self.assertEqual(finding['severity'], 'high')

    def test_currency_mismatch_is_a_warning(self):
        product = _valid_product()
        product['offers']['priceCurrency'] = 'USD'
        finding = _by_rule(validate_product(product), 'currency-unexpected')[0]
        self.assertEqual(finding['severity'], 'medium')
        self.assertEqual(
            _rules(validate_product(product, expected_currency='USD')).count(
                'currency-unexpected'), 0,
        )

    def test_french_return_policy_category(self):
        product = _valid_product()
        product['offers']['hasMerchantReturnPolicy']['returnPolicyCategory'] = '30 jours'
        finding = _by_rule(validate_product(product),
                           'return-policy-category-invalid')[0]
        self.assertEqual(finding['severity'], 'high')

    def test_return_policy_must_cover_canada(self):
        product = _valid_product()
        product['offers']['hasMerchantReturnPolicy']['applicableCountry'] = ['US']
        self.assertIn('return-policy-country-ca', _rules(validate_product(product)))

    def test_shipping_must_reach_canada(self):
        product = _valid_product()
        product['offers']['shippingDetails']['shippingDestination'] = {
            '@type': 'DefinedRegion', 'addressCountry': 'US',
        }
        self.assertIn('shipping-country-ca', _rules(validate_product(product)))
