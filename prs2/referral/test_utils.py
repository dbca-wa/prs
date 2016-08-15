from django.db.models.base import ModelBase
from django.db.models.query import QuerySet
from django.test import RequestFactory
from referral.models import Referral, Task
from referral.test_models import PrsTestCase
from referral.utils import (
    is_model_or_string, smart_truncate, breadcrumbs_li, slugify,
    update_revision_history, filter_queryset, user_task_history)


class UtilsTest(PrsTestCase):

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

    def test_update_revision_history(self):
        """Test update_revision_history, for coverage :P
        """
        r = Referral.objects.first()
        r.description = 'Update description'
        r.save()
        r.description = 'Update description again'
        r.save()
        update_revision_history(Referral)

    def test_filter_queryset(self):
        """Test that filter_queryset returns the correct things
        """
        r = RequestFactory()
        get = r.get('/filter', {'q': "test filter  string  to 'normalise'"})
        ret = filter_queryset(get, Referral, Referral.objects.all())
        self.assertTrue(isinstance(ret[0], QuerySet))
        self.assertTrue(isinstance(ret[1], unicode))

    def test_user_task_history(self):
        """Test the user_task_history inserts correct data to a user profile
        """
        # Ensure that normaluser has a task assigned.
        task = Task.objects.first()
        task.assigned_user = self.n_user
        task.save()
        user_task_history(self.n_user, task, 'Test task history')
        self.assertTrue('Test task history' in self.n_user.userprofile.task_history)
        self.assertTrue(str(task.pk) in self.n_user.userprofile.task_history)
        user_task_history(self.n_user, task, 'More task history')
        self.assertTrue('More task history' in self.n_user.userprofile.task_history)
