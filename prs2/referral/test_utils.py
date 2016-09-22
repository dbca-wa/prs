from django.db.models.base import ModelBase
from django.db.models.query import QuerySet
from django.test import RequestFactory
from referral.models import Referral, Task
from referral.test_models import PrsTestCase
from referral.utils import (
    is_model_or_string, smart_truncate, breadcrumbs_li, slugify,
    update_revision_history, filter_queryset, user_task_history,
    dewordify_text)


WORD_HTML_SAMPLE = '''<div class=Section1>
<p>Hi Joe</p>\r\n<p>\u0xe2Just following up on the clearance of the remaining
conditions.  Did the additional information supplied recently meet the
Department\u2019s requirements?</p>\r\n<p>Regards</p>\r\n<p>John</p>\r\n
<p style='margin-top:3.0pt;margin-right:0in;margin-bottom:0in;margin-left:.2in;
margin-bottom:.0001pt;text-indent:-.2in'><a name=a.1></a><b>a</b><b><sup><span
style='font-size:10.0pt'>1</span></sup></b> (&lt; PPN *'a) <i>[personal pronoun
and proper name marker] </i>a marker appearing optionally: (1) before sentence
initial pronouns and personal names, and (2) after transitive verbs; and occurring
obligatorily after the prepositions <i>i</i> and <i>ki</i>. <i>A Sina ni
tautali i a Puna</i>, 'Sina followed Puna'. </p>
<p style='margin-top:3.0pt;margin-right:0in;margin-bottom:0in;margin-left:.2in;
margin-bottom:.0001pt;text-indent:-.2in'><a name=a.2></a><b>a</b><b><sup><span
style='font-size:10.0pt'>2</span></sup></b> <i>[preposition, marking 'a' class
alienable possession] </i>of, belonging to. <i>te kapu a Sina</i>, 'the cup of
Sina'; <i>te tama a Puna</i>, 'the (genetic) child of Puna'. See also: <i>o</i><i><sup><span
style='font-size:10.0pt'>2</span></sup></i><i><span style='font-size:10.0pt'>.</span></i></p>
<p style='margin-top:3.0pt;margin-right:0in;margin-bottom:0in;margin-left:.2in;
margin-bottom:.0001pt;text-indent:-.2in'><a name=a.laa></a><b>a laa</b> <i>[nq,
preceding noun, plural] </i>other, some other. <i>I te puina, maatou ni nnoho i
Muli Akau ia, a laa tama ni nnoho i Hale</i>, 'during the <i>puina,</i> we
stayed at the outer islands, the other people stayed on the main island'. See
also: <i>laa</i><i><sup><span style='font-size:10.0pt'>5</span></sup></i><i><span
style='font-size:10.0pt'>.</span></i></p>
<p style='margin-top:3.0pt;margin-right:0in;margin-bottom:0in;margin-left:.2in;
margin-bottom:.0001pt;text-indent:-.2in'><a name=aa></a><b>aa</b> <i>[interrogative
pronoun] </i>what?. <i>aa</i> replaces nouns and verbs in interrogative
statements. <i>Te aa ku tele?</i>, 'what is running?'; <i>te vaka ku aa?</i>,
'what is the ship doing?' or, 'what is happening about the ship?'; <i>ee aa?</i>,
'what is going on?' or, 'what are you up to?'; <i>a koe ku aa?</i>, 'how are
you feeling?' or, 'what are you doing at this specific moment?'; <i>koe e noho
ki aa?</i>, 'you are staying for what purpose?'. </p>
</div>
'''


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
        self.assertIs(type(crumbs), unicode)

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

    def test_dewordify_text(self):
        """Test the dewordify_text utility function.
        """
        self.assertTrue(isinstance(dewordify_text(None), unicode))
        self.assertTrue(isinstance(dewordify_text(''), unicode))
        self.assertTrue(isinstance(dewordify_text(u''), unicode))
        self.assertTrue(isinstance(dewordify_text('Short test'), unicode))
        self.assertTrue(isinstance(dewordify_text(u'Short test'), unicode))
        self.assertTrue(isinstance(dewordify_text(WORD_HTML_SAMPLE), unicode))
        self.assertTrue(isinstance(dewordify_text(unicode(WORD_HTML_SAMPLE)), unicode))
