"""Tests for the JSON-LD publication gate.

Everything here runs offline by construction: `schema_validator` opens no
socket and touches no model, so there is nothing to mock. The suite pins
the two directions that matter equally, that a broken block is caught and
that a correct Quebec block passes clean, because a validator that cries
wolf gets switched off.

Run all:
    python manage.py test sites_mgmt.tests_schema_validator
"""
from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from .schema_validator import (
    ERROR, WARNING, has_blocking_errors, validate_html_jsonld, validate_jsonld,
)


def _article(**overrides):
    """A complete BlogPosting, the shape Gridar ships for a blog post."""
    node = {
        '@context': 'https://schema.org',
        '@type': 'BlogPosting',
        'headline': 'Comment choisir un couvreur a Laval',
        'description': 'Les criteres qui comptent avant de signer.',
        'inLanguage': 'fr-CA',
        'image': 'https://gridar.app/img/couvreur.jpg',
        'datePublished': '2026-08-01',
        'dateModified': '2026-08-10T09:00:00-04:00',
        'author': {'@type': 'Person', 'name': 'Darius Tokam'},
        'publisher': {
            '@type': 'Organization',
            'name': 'Gridar',
            'url': 'https://gridar.app',
            'logo': {'@type': 'ImageObject', 'url': 'https://gridar.app/logo.png'},
        },
        'mainEntityOfPage': {'@type': 'WebPage', '@id': 'https://gridar.app/blog/couvreur'},
    }
    node.update(overrides)
    return node


def _local_business(**overrides):
    node = {
        '@context': 'https://schema.org',
        '@type': 'Plumber',
        'name': 'Plomberie Rive-Sud',
        'url': 'https://plomberie-rive-sud.ca',
        'image': 'https://plomberie-rive-sud.ca/photo.jpg',
        'telephone': '+1 450 555-0142',
        'priceRange': '$$',
        'geo': {'@type': 'GeoCoordinates', 'latitude': 45.53, 'longitude': -73.51},
        'openingHoursSpecification': [{
            '@type': 'OpeningHoursSpecification',
            'dayOfWeek': 'Monday',
            'opens': '08:00',
            'closes': '17:00',
        }],
        'address': {
            '@type': 'PostalAddress',
            'streetAddress': '120 rue Saint-Charles',
            'addressLocality': 'Longueuil',
            'addressRegion': 'QC',
            'postalCode': 'J4H 1C4',
            'addressCountry': 'CA',
        },
    }
    node.update(overrides)
    return node


class ValidatorTestCase(SimpleTestCase):
    """Assertions phrased over the issue list rather than over indexes."""

    def errors(self, issues):
        return [i for i in issues if i['level'] == ERROR]

    def warnings(self, issues):
        return [i for i in issues if i['level'] == WARNING]

    def assertNoError(self, issues):
        self.assertEqual(
            [], self.errors(issues),
            'aucune erreur attendue, obtenu: '
            + ' | '.join(f"{i['path']}: {i['message']}" for i in self.errors(issues)),
        )

    def assertIssue(self, issues, level, path=None, needle=None):
        for issue in issues:
            if issue['level'] != level:
                continue
            if path is not None and issue['path'] != path:
                continue
            if needle is not None and needle.lower() not in issue['message'].lower():
                continue
            return issue
        self.fail(
            f'aucun {level} sur path={path!r} contenant {needle!r}. Obtenu: '
            + ' | '.join(f"[{i['level']}] {i['path']}: {i['message']}" for i in issues)
        )

    def assertNoIssueMatching(self, issues, needle):
        for issue in issues:
            if needle.lower() in issue['message'].lower():
                self.fail(f'faux positif: [{issue["level"]}] {issue["path"]}: {issue["message"]}')


class HealthyPayloadTests(ValidatorTestCase):
    """A correct block must come back clean, warnings included where possible."""

    def test_complete_article_has_no_error(self):
        self.assertNoError(validate_jsonld(_article()))

    def test_complete_local_business_is_silent(self):
        self.assertEqual([], validate_jsonld(_local_business()))

    def test_complete_breadcrumb_is_silent(self):
        payload = {
            '@context': 'https://schema.org',
            '@type': 'BreadcrumbList',
            'itemListElement': [
                {'@type': 'ListItem', 'position': 1, 'name': 'Accueil',
                 'item': 'https://plomberie-rive-sud.ca/'},
                {'@type': 'ListItem', 'position': 2, 'name': 'Services',
                 'item': 'https://plomberie-rive-sud.ca/services'},
                {'@type': 'ListItem', 'position': 3, 'name': 'Debouchage de drain'},
            ],
        }
        self.assertEqual([], validate_jsonld(payload))

    def test_reference_node_is_not_asked_to_be_complete(self):
        """`mainEntityOfPage` points at a node, it does not describe one."""
        issues = validate_jsonld(_article())
        self.assertNoIssueMatching(issues, 'WebPage')


class ContextAndTypeTests(ValidatorTestCase):
    def test_missing_context_is_an_error(self):
        node = _article()
        del node['@context']
        self.assertIssue(validate_jsonld(node), ERROR, '$.@context', '@context')

    def test_http_context_is_a_warning(self):
        issues = validate_jsonld(_article(**{'@context': 'http://schema.org'}))
        self.assertIssue(issues, WARNING, '$.@context', 'http')

    def test_foreign_context_is_an_error(self):
        issues = validate_jsonld(_article(**{'@context': 'https://exemple.org'}))
        self.assertIssue(issues, ERROR, '$.@context')

    def test_context_object_referencing_schema_org_passes(self):
        node = _article(**{'@context': {'@vocab': 'https://schema.org/'}})
        self.assertNoIssueMatching(validate_jsonld(node), '@context')

    def test_missing_type_is_an_error(self):
        node = _article()
        del node['@type']
        self.assertIssue(validate_jsonld(node), ERROR, '$.@type', '@type')

    def test_empty_type_is_an_error(self):
        self.assertIssue(validate_jsonld(_article(**{'@type': ''})), ERROR, '$.@type')

    def test_lowercase_type_names_the_fix(self):
        issues = validate_jsonld(_article(**{'@type': 'article'}))
        self.assertIssue(issues, ERROR, '$', 'Article')

    def test_type_with_space_is_rejected(self):
        issues = validate_jsonld(_article(**{'@type': 'Blog Posting'}))
        self.assertIssue(issues, ERROR, '$', 'invalide')

    def test_full_iri_type_is_accepted(self):
        node = _article(**{'@type': 'https://schema.org/BlogPosting'})
        self.assertNoError(validate_jsonld(node))


class PlaceholderTests(ValidatorTestCase):
    def test_detects_english_template_labels(self):
        for value in ('[City]', '[Phone]', '[Business Name]', '[Your Name]',
                      '[INSERT ADDRESS]', '[URL]', '[YYYY-MM-DD]'):
            issues = validate_jsonld(_article(headline=f'Titre {value}'))
            self.assertIssue(issues, ERROR, '$.headline', 'placeholder')

    def test_detects_french_template_labels(self):
        for value in ('[Ville]', '[Telephone]', '[Téléphone]', '[Adresse]',
                      '[Nom de l entreprise]', '[Courriel]', '[votre ville]'):
            issues = validate_jsonld(_article(headline=f'Couvreur {value}'))
            self.assertIssue(issues, ERROR, '$.headline', 'placeholder')

    def test_detects_interpolation_syntaxes(self):
        for value in ('{{name}}', '${city}', '{slug}', '%CITY%', '<%= nom %>'):
            issues = validate_jsonld(_article(description=f'Service a {value}'))
            self.assertIssue(issues, ERROR, '$.description', 'placeholder')

    def test_detects_editorial_markers(self):
        for value in ('TODO relire', 'XXX a valider', 'FIXME', 'Lorem ipsum dolor sit amet',
                      'A REMPLIR', 'À COMPLÉTER'):
            issues = validate_jsonld(_article(description=value))
            self.assertIssue(issues, ERROR, '$.description', 'placeholder')

    def test_detects_sample_domains(self):
        for value in ('https://example.com/a', 'https://exemple.com/a',
                      'https://votresite.ca/a'):
            issues = validate_jsonld(_article(image=value))
            self.assertIssue(issues, ERROR, '$.image', 'placeholder')

    def test_placeholder_found_deep_in_the_tree(self):
        node = _article(publisher={'@type': 'Organization', 'name': '[Business Name]',
                                   'url': 'https://gridar.app'})
        self.assertIssue(validate_jsonld(node), ERROR, '$.publisher.name', 'placeholder')

    def test_ordinary_french_copy_is_not_flagged(self):
        """The rules are uppercase-anchored so real copy survives them."""
        for value in (
            'Un formulaire a remplir en ligne, sans frais.',
            'Nous allons remplacer votre toiture avant l hiver.',
            'Votre nom apparait sur la soumission [voir plus bas].',
            'Il faut compter environ 3 semaines.',
        ):
            node = {
                '@context': 'https://schema.org',
                '@type': 'Answer',
                'text': value,
            }
            self.assertNoIssueMatching(validate_jsonld(node), 'placeholder')


class DeadTypeTests(ValidatorTestCase):
    def test_retired_types_are_errors(self):
        for dead in ('HowTo', 'SpecialAnnouncement', 'ClaimReview',
                     'VehicleListing', 'EstimatedSalary', 'LearningVideo',
                     'CourseInfo'):
            issues = validate_jsonld({'@context': 'https://schema.org', '@type': dead,
                                      'name': 'Test'})
            self.assertIssue(issues, ERROR, '$', 'mort en 2026')

    def test_faqpage_is_a_warning_with_the_may_2026_context(self):
        """FAQPage lost its rich result, not its usefulness for AI answers."""
        payload = {
            '@context': 'https://schema.org',
            '@type': 'FAQPage',
            'inLanguage': 'fr-CA',
            'mainEntity': [{
                '@type': 'Question',
                'name': 'Combien coute un debouchage de drain?',
                'acceptedAnswer': {'@type': 'Answer', 'text': 'Entre 200 et 400 dollars.'},
            }],
        }
        issues = validate_jsonld(payload)
        self.assertNoError(issues)
        issue = self.assertIssue(issues, WARNING, '$', '7 mai 2026')
        self.assertIn('IA', issue['message'])

    def test_dataset_is_a_warning(self):
        issues = validate_jsonld({'@context': 'https://schema.org', '@type': 'Dataset',
                                  'name': 'Donnees'})
        self.assertNoError(issues)
        self.assertIssue(issues, WARNING, '$', 'Dataset Search')


class RequiredFieldTests(ValidatorTestCase):
    def test_article_required_fields(self):
        for field in ('headline', 'author', 'datePublished'):
            node = _article()
            del node[field]
            self.assertIssue(validate_jsonld(node), ERROR, f'$.{field}', 'requis')

    def test_product_required_fields(self):
        base = {
            '@context': 'https://schema.org',
            '@type': 'Product',
            'name': 'Tuque en laine',
            'image': 'https://boutique.ca/tuque.jpg',
            'description': 'Tuque tricotee au Quebec.',
            'brand': {'@type': 'Brand', 'name': 'Nordik'},
            'sku': 'TUQ-01',
            'offers': {'@type': 'Offer', 'price': '29.99', 'priceCurrency': 'CAD',
                       'availability': 'https://schema.org/InStock',
                       'url': 'https://boutique.ca/tuque'},
        }
        self.assertNoError(validate_jsonld(base))
        for field in ('name', 'image', 'offers'):
            node = dict(base)
            del node[field]
            self.assertIssue(validate_jsonld(node), ERROR, f'$.{field}', 'requis')

    def test_product_offers_must_be_an_offer(self):
        node = {
            '@context': 'https://schema.org',
            '@type': 'Product',
            'name': 'Tuque',
            'image': 'https://boutique.ca/t.jpg',
            'offers': {'@type': 'Thing', 'price': '10.00', 'priceCurrency': 'CAD'},
        }
        self.assertIssue(validate_jsonld(node), ERROR, '$.offers', 'Offer')

    def test_local_business_required_fields(self):
        for field in ('name', 'address', 'telephone'):
            node = _local_business()
            del node[field]
            self.assertIssue(validate_jsonld(node), ERROR, f'$.{field}', 'requis')

    def test_faqpage_required_fields(self):
        node = {'@context': 'https://schema.org', '@type': 'FAQPage', 'inLanguage': 'fr-CA'}
        self.assertIssue(validate_jsonld(node), ERROR, '$.mainEntity', 'requis')

    def test_faqpage_with_empty_question_list(self):
        node = {'@context': 'https://schema.org', '@type': 'FAQPage',
                'inLanguage': 'fr-CA', 'mainEntity': []}
        self.assertIssue(validate_jsonld(node), ERROR, '$.mainEntity')

    def test_faqpage_entries_must_be_questions(self):
        node = {
            '@context': 'https://schema.org', '@type': 'FAQPage', 'inLanguage': 'fr-CA',
            'mainEntity': [{'@type': 'Thing', 'name': 'Pas une question'}],
        }
        self.assertIssue(validate_jsonld(node), ERROR, '$.mainEntity[0]', 'Question')

    def test_question_needs_an_answer(self):
        node = {
            '@context': 'https://schema.org', '@type': 'FAQPage', 'inLanguage': 'fr-CA',
            'mainEntity': [{'@type': 'Question', 'name': 'Combien ca coute?'}],
        }
        self.assertIssue(validate_jsonld(node), ERROR,
                         '$.mainEntity[0].acceptedAnswer', 'requis')

    def test_answer_needs_text(self):
        node = {
            '@context': 'https://schema.org', '@type': 'FAQPage', 'inLanguage': 'fr-CA',
            'mainEntity': [{'@type': 'Question', 'name': 'Combien?',
                            'acceptedAnswer': {'@type': 'Answer'}}],
        }
        self.assertIssue(validate_jsonld(node), ERROR,
                         '$.mainEntity[0].acceptedAnswer.text', 'requis')

    def test_service_required_fields(self):
        base = {
            '@context': 'https://schema.org',
            '@type': 'Service',
            'name': 'Deneigement residentiel',
            'description': 'Deneigement d entrees a Quebec.',
            'areaServed': {'@type': 'City', 'name': 'Quebec'},
            'provider': {'@type': 'LocalBusiness', 'name': 'Neige Pro',
                         'telephone': '+1 418 555-0110',
                         'address': {'@type': 'PostalAddress',
                                     'streetAddress': '5 rue Blanche',
                                     'addressLocality': 'Quebec',
                                     'addressRegion': 'QC',
                                     'postalCode': 'G1K 1A1',
                                     'addressCountry': 'CA'},
                         'url': 'https://neigepro.ca',
                         'image': 'https://neigepro.ca/p.jpg',
                         'priceRange': '$$',
                         'geo': {'@type': 'GeoCoordinates', 'latitude': 46.8,
                                 'longitude': -71.2},
                         'openingHoursSpecification': []},
        }
        for field in ('name', 'provider'):
            node = dict(base)
            del node[field]
            self.assertIssue(validate_jsonld(node), ERROR, f'$.{field}', 'requis')

    def test_breadcrumblist_required_fields(self):
        node = {'@context': 'https://schema.org', '@type': 'BreadcrumbList'}
        self.assertIssue(validate_jsonld(node), ERROR, '$.itemListElement', 'requis')

    def test_empty_string_counts_as_missing(self):
        self.assertIssue(validate_jsonld(_article(headline='')), ERROR, '$.headline', 'vide')

    def test_optional_empty_field_is_only_a_warning(self):
        issues = validate_jsonld(_article(articleSection=''))
        self.assertNoError(issues)
        self.assertIssue(issues, WARNING, '$.articleSection', 'vide')

    def test_subtype_inherits_the_parent_rules(self):
        node = _local_business(**{'@type': 'Restaurant'})
        del node['telephone']
        self.assertIssue(validate_jsonld(node), ERROR, '$.telephone', 'requis')

    def test_recommended_fields_are_warnings_only(self):
        node = _article()
        del node['image']
        issues = validate_jsonld(node)
        self.assertNoError(issues)
        self.assertIssue(issues, WARNING, '$.image', 'recommande')

    def test_untyped_nested_object_is_flagged(self):
        node = _article(author={'name': 'Darius Tokam'})
        self.assertIssue(validate_jsonld(node), WARNING, '$.author', '@type')


class UrlTests(ValidatorTestCase):
    def test_empty_url_is_an_error(self):
        issues = validate_jsonld(_local_business(url=''))
        self.assertIssue(issues, ERROR, '$.url', 'vide')

    def test_relative_url_is_an_error(self):
        issues = validate_jsonld(_article(image='/img/couvreur.jpg'))
        self.assertIssue(issues, ERROR, '$.image', 'relative')

    def test_protocol_relative_url_is_an_error(self):
        issues = validate_jsonld(_article(image='//cdn.gridar.app/a.jpg'))
        self.assertIssue(issues, ERROR, '$.image', 'sans protocole')

    def test_data_uri_is_an_error(self):
        issues = validate_jsonld(_article(image='data:image/png;base64,iVBORw0KGgo='))
        self.assertIssue(issues, ERROR, '$.image', 'data:')

    def test_non_http_scheme_is_an_error(self):
        issues = validate_jsonld(_local_business(url='ftp://plomberie-rive-sud.ca'))
        self.assertIssue(issues, ERROR, '$.url', 'protocole')

    def test_hostname_without_a_dot_is_an_error(self):
        issues = validate_jsonld(_local_business(url='https://localhost/page'))
        self.assertIssue(issues, ERROR, '$.url', 'domaine')

    def test_http_url_is_a_warning(self):
        issues = validate_jsonld(_local_business(url='http://plomberie-rive-sud.ca'))
        self.assertNoError(issues)
        self.assertIssue(issues, WARNING, '$.url', 'http')

    def test_url_list_is_checked_element_by_element(self):
        node = _local_business(sameAs=['https://facebook.com/prs', 'www.instagram.com/prs'])
        self.assertIssue(validate_jsonld(node), ERROR, '$.sameAs[1]', 'relative')

    def test_bare_fragment_id_is_a_warning(self):
        node = _local_business(**{'@id': '#business'})
        self.assertNoError(validate_jsonld(node))
        self.assertIssue(validate_jsonld(node), WARNING, '$.@id', 'fragment')

    def test_absolute_id_passes(self):
        node = _local_business(**{'@id': 'https://plomberie-rive-sud.ca/#business'})
        self.assertEqual([], validate_jsonld(node))


class DateTests(ValidatorTestCase):
    def test_accepts_iso_8601_forms(self):
        for value in ('2026-08-14', '2026-08-14T09:30:00-04:00',
                      '2026-08-14T09:30:00Z', '2026-08-14T09:30'):
            node = _article(datePublished=value, dateModified=value)
            self.assertNoError(validate_jsonld(node))

    def test_rejects_malformed_dates(self):
        for value in ('14/08/2026', '14 aout 2026', '2026-13-45', '08-14-2026',
                      'hier', '2026/08/14'):
            issues = validate_jsonld(_article(datePublished=value))
            self.assertIssue(issues, ERROR, '$.datePublished', 'ISO 8601')

    def test_modified_before_published_is_an_error(self):
        node = _article(datePublished='2026-08-10', dateModified='2026-08-01')
        self.assertIssue(validate_jsonld(node), ERROR, '$.dateModified', 'anterieure')

    def test_future_publication_date_is_a_warning(self):
        future = (datetime.now(timezone.utc) + timedelta(days=90)).strftime('%Y-%m-%d')
        node = _article(datePublished=future, dateModified=future)
        issues = validate_jsonld(node)
        self.assertNoError(issues)
        self.assertIssue(issues, WARNING, '$.datePublished', 'futur')


class QuebecTests(ValidatorTestCase):
    """The half upstream has no reason to carry."""

    def test_french_price_formatting_is_rejected(self):
        node = {
            '@context': 'https://schema.org', '@type': 'Product',
            'name': 'Tuque', 'image': 'https://boutique.ca/t.jpg',
            'offers': {'@type': 'Offer', 'price': '19,99 $', 'priceCurrency': 'CAD'},
        }
        self.assertIssue(validate_jsonld(node), ERROR, '$.offers.price', '19.99')

    def test_currency_must_be_iso_4217(self):
        node = {
            '@context': 'https://schema.org', '@type': 'Product',
            'name': 'Tuque', 'image': 'https://boutique.ca/t.jpg',
            'offers': {'@type': 'Offer', 'price': '19.99', 'priceCurrency': 'dollars'},
        }
        self.assertIssue(validate_jsonld(node), ERROR, '$.offers.priceCurrency', 'ISO 4217')

    def test_phone_without_country_code_is_a_warning(self):
        issues = validate_jsonld(_local_business(telephone='450 555-0142'))
        self.assertNoError(issues)
        self.assertIssue(issues, WARNING, '$.telephone', 'E.164')

    def test_truncated_phone_is_a_warning(self):
        issues = validate_jsonld(_local_business(telephone='555-0142'))
        self.assertIssue(issues, WARNING, '$.telephone', 'incomplet')

    def test_bare_fr_language_tag_suggests_fr_ca(self):
        issues = validate_jsonld(_article(inLanguage='fr'))
        self.assertNoError(issues)
        self.assertIssue(issues, WARNING, '$.inLanguage', 'fr-CA')

    def test_malformed_language_tag_is_a_warning(self):
        for value in ('Français', 'fr_CA', 'francais-quebec-canada-extra-long-tag'):
            issues = validate_jsonld(_article(inLanguage=value))
            self.assertIssue(issues, WARNING, '$.inLanguage')

    def test_quebec_address_without_country(self):
        node = _local_business()
        del node['address']['addressCountry']
        issues = validate_jsonld(node)
        self.assertIssue(issues, WARNING, '$.address.addressCountry', 'CA')

    def test_address_as_free_text_is_a_warning(self):
        node = _local_business(address='120 rue Saint-Charles, Longueuil, QC')
        issues = validate_jsonld(node)
        self.assertIssue(issues, WARNING, '$.address', 'PostalAddress')


class BreadcrumbTests(ValidatorTestCase):
    def _crumbs(self, elements):
        return {'@context': 'https://schema.org', '@type': 'BreadcrumbList',
                'itemListElement': elements}

    def test_positions_must_run_from_one_without_gaps(self):
        payload = self._crumbs([
            {'@type': 'ListItem', 'position': 1, 'name': 'Accueil', 'item': 'https://x.ca/'},
            {'@type': 'ListItem', 'position': 3, 'name': 'Toiture'},
        ])
        self.assertIssue(validate_jsonld(payload), ERROR, '$.itemListElement', 'sequentiel')

    def test_position_as_string_is_a_warning(self):
        payload = self._crumbs([
            {'@type': 'ListItem', 'position': '1', 'name': 'Accueil', 'item': 'https://x.ca/'},
            {'@type': 'ListItem', 'position': '2', 'name': 'Toiture'},
        ])
        issues = validate_jsonld(payload)
        self.assertNoError(issues)
        self.assertIssue(issues, WARNING, '$.itemListElement[0].position', 'entier')

    def test_missing_position_is_an_error(self):
        payload = self._crumbs([{'@type': 'ListItem', 'name': 'Accueil',
                                 'item': 'https://x.ca/'}])
        self.assertIssue(validate_jsonld(payload), ERROR,
                         '$.itemListElement[0].position', 'position')

    def test_intermediate_crumb_needs_an_item(self):
        payload = self._crumbs([
            {'@type': 'ListItem', 'position': 1, 'name': 'Accueil'},
            {'@type': 'ListItem', 'position': 2, 'name': 'Toiture'},
        ])
        self.assertIssue(validate_jsonld(payload), ERROR, '$.itemListElement[0].item', 'item')

    def test_last_crumb_may_omit_its_item(self):
        payload = self._crumbs([
            {'@type': 'ListItem', 'position': 1, 'name': 'Accueil', 'item': 'https://x.ca/'},
            {'@type': 'ListItem', 'position': 2, 'name': 'Toiture'},
        ])
        self.assertNoError(validate_jsonld(payload))

    def test_entries_must_be_list_items(self):
        payload = self._crumbs([{'@type': 'Thing', 'position': 1, 'name': 'Accueil',
                                 'item': 'https://x.ca/'}])
        self.assertIssue(validate_jsonld(payload), ERROR, '$.itemListElement[0]', 'ListItem')


class PayloadShapeTests(ValidatorTestCase):
    def test_accepts_a_list_of_blocks(self):
        issues = validate_jsonld([
            _article(),
            {'@context': 'https://schema.org', '@type': 'HowTo', 'name': 'Poser une tuile'},
        ])
        self.assertIssue(issues, ERROR, '$[1]', 'mort en 2026')

    def test_accepts_a_graph_wrapper(self):
        payload = {
            '@context': 'https://schema.org',
            '@graph': [
                {'@type': 'Organization', 'name': 'Gridar', 'url': 'https://gridar.app',
                 'logo': 'https://gridar.app/logo.png'},
                {'@type': 'WebPage', 'name': 'Accueil', 'description': 'x',
                 'inLanguage': 'fr-CA'},
            ],
        }
        self.assertEqual([], validate_jsonld(payload))

    def test_graph_nodes_do_not_need_their_own_context(self):
        payload = {'@context': 'https://schema.org',
                   '@graph': [{'@type': 'WebSite', 'name': 'Gridar',
                               'url': 'https://gridar.app'}]}
        self.assertNoIssueMatching(validate_jsonld(payload), '@context')

    def test_graph_node_without_type_is_an_error(self):
        payload = {'@context': 'https://schema.org', '@graph': [{'name': 'Gridar'}]}
        self.assertIssue(validate_jsonld(payload), ERROR, '$.@graph[0].@type')

    def test_accepts_raw_json_text(self):
        self.assertNoError(validate_jsonld(
            '{"@context": "https://schema.org", "@type": "Answer", "text": "Oui."}'
        ))

    def test_malformed_json_text_is_reported(self):
        issues = validate_jsonld('{"@type": "Article",}')
        self.assertIssue(issues, ERROR, '$', 'JSON invalide')

    def test_empty_payloads_are_reported(self):
        for payload in (None, {}, [], '', '   '):
            issues = validate_jsonld(payload)
            self.assertEqual(1, len(issues))
            self.assertEqual(ERROR, issues[0]['level'])

    def test_non_object_payload_is_reported(self):
        self.assertIssue(validate_jsonld(42), ERROR, '$', 'objet')

    def test_deeply_nested_payload_stops_cleanly(self):
        """A runaway structure must not blow the stack on its way to a verdict."""
        node = {'@context': 'https://schema.org', '@type': 'Thing', 'name': 'racine'}
        cursor = node
        for depth in range(40):
            child = {'@type': 'Thing', 'name': f'niveau {depth}'}
            cursor['about'] = child
            cursor = child
        issues = validate_jsonld(node)
        self.assertIssue(issues, WARNING, '$', 'Analyse interrompue')

    def test_issue_shape_is_stable(self):
        for issue in validate_jsonld(_article(headline='[Ville]')):
            self.assertEqual({'level', 'path', 'message'}, set(issue))
            self.assertIn(issue['level'], (ERROR, WARNING))

    def test_errors_are_listed_before_warnings(self):
        node = _article(headline='[Ville]', inLanguage='fr')
        levels = [i['level'] for i in validate_jsonld(node)]
        self.assertEqual(sorted(levels, key=lambda l: l != ERROR), levels)


class HtmlEntryPointTests(ValidatorTestCase):
    def test_extracts_and_validates_every_block(self):
        html = (
            '<html><head>'
            '<script type="application/ld+json">'
            '{"@context":"https://schema.org","@type":"HowTo","name":"Poser une tuile"}'
            '</script>'
            '<script type="application/ld+json">'
            '{"@context":"https://schema.org","@type":"Answer","text":"Oui."}'
            '</script>'
            '</head><body>x</body></html>'
        )
        issues = validate_html_jsonld(html)
        self.assertIssue(issues, ERROR, '$.script[0]', 'mort en 2026')
        self.assertNoIssueMatching(issues, 'script[1]')

    def test_malformed_block_is_reported_with_its_index(self):
        html = ('<script type="application/ld+json">{ oups </script>')
        self.assertIssue(validate_html_jsonld(html), ERROR, '$.script[0]', 'JSON invalide')

    def test_page_without_structured_data_is_a_warning(self):
        issues = validate_html_jsonld('<html><body>rien</body></html>')
        self.assertNoError(issues)
        self.assertIssue(issues, WARNING, '$', 'ld+json')


class BlockingDecisionTests(ValidatorTestCase):
    def test_errors_block_publication(self):
        self.assertTrue(has_blocking_errors(validate_jsonld(_article(headline='[Ville]'))))

    def test_warnings_alone_do_not_block(self):
        self.assertFalse(has_blocking_errors(validate_jsonld(_article(inLanguage='fr'))))

    def test_clean_payload_does_not_block(self):
        self.assertFalse(has_blocking_errors(validate_jsonld(_local_business())))
