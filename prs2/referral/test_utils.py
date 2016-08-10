from django.db.models.base import ModelBase
from django.test import TestCase

from referral.models import Referral
from referral.utils import is_model_or_string, smart_truncate, breadcrumbs_li, slugify


class UtilsTest(TestCase):

    def test_is_model_or_string(self):
        """Test is_model_or_string with a string and a model class
        """
        self.assertTrue(isinstance(is_model_or_string('referral'), ModelBase))
        self.assertTrue(isinstance(is_model_or_string(Referral), ModelBase))

    def test_is_model_or_string_plural_string(self):
        """Test is_model_or_string with a plural string
        """
        self.assertTrue(isinstance(is_model_or_string('referrals'), ModelBase))

    def test_is_model_or_string_nonsense_model(self):
        """Test is_model_or_string with a nonsense string
        """
        self.assertIsNone(is_model_or_string('foobar'))

    def test_smart_truncate_long(self):
        """Test smart_truncate utility function with a long string
        """
        s = """Cosby sweater iphone artisan, squid trust fund photo booth twee
            shoreditch single-origin coffee aesthetic jean shorts messenger bag
            brooklyn butcher. Iphone fap banksy next level put a bird on it,
            letterpress photo booth thundercats biodiesel fanny pack."""
        trunc = smart_truncate(s)
        self.assertTrue(trunc.endswith('(more)'), s)

    def test_smart_truncate_new_suffix(self):
        """Test smart_truncate utility function with a defined suffix
        """
        s = """Cosby sweater iphone artisan, squid trust fund photo booth twee
            shoreditch single-origin coffee aesthetic jean shorts messenger bag
            brooklyn butcher. Iphone fap banksy next level put a bird on it,
            letterpress photo booth thundercats biodiesel fanny pack."""
        trunc = smart_truncate(content=s, suffix='...MORE')
        self.assertTrue(trunc.endswith('...MORE'), s)

    def test_smart_truncate_short(self):
        """Test smart_truncate utility function with a short string
        """
        s = 'Quinoa cred brooklyn, sartorial letterpress.'
        trunc = smart_truncate(s)
        self.assertTrue(trunc.endswith('letterpress.'))

    def test_html_breadcrumbs(self):
        """Test the breadcrumbs_li utility function
        """
        l = [('/A', 'A'), ('/A/B', 'B'), ('', 'C',)]
        crumbs = breadcrumbs_li(l)
        self.assertIs(type(crumbs), str)

    def test_slugify(self):
        """Test the customised slugify function
        """
        self.assertEqual('test', slugify('Test'))
        self.assertEqual('test-value', slugify('Test Value'))
