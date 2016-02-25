from django.conf import settings
from datetime import date
from django.contrib.auth import get_user_model

from django.test import LiveServerTestCase
from selenium.webdriver.firefox.webdriver import WebDriver
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from referral.models import UserProfile
from mixer.backend.django import mixer
from taggit.models import Tag

from referral.models import (
    DopTrigger, Region, OrganisationType, Organisation, TaskType, TaskState,
    NoteType, ReferralType, Referral, Task, Record, Note, Condition, Location,
    Bookmark, Clearance, Agency, ConditionCategory, UserProfile, ModelCondition)

User = get_user_model()

READONLY_MSG = 'You do not have Add/Update Permissions. Please contact the Application Administrator'


class PrsSeleniumTests(LiveServerTestCase):
    fixtures = ['groups.json', 'test-users.json']

    def __init__(self, *args, **kwargs):
        super(PrsSeleniumTests, self).__init__(*args, **kwargs)
        if not settings.DEBUG:
            settings.DEBUG = True
        self.logged_in = False

    def setUp(self):
        self.selenium = WebDriver()
        # Need to reset user passwords to enable test db re-use.
        self.admin_user = User.objects.get(username='admin')
        self.admin_user.is_superuser = True
        self.admin_user.set_password('pass')
        self.admin_user.save()
        profile, c = UserProfile.objects.get_or_create(user=self.admin_user)
        self.p_user = User.objects.get(username='poweruser')
        self.p_user.set_password('pass')
        self.p_user.save()
        profile, c = UserProfile.objects.get_or_create(user=self.p_user)
        self.n_user = User.objects.get(username='normaluser')
        self.n_user.set_password('pass')
        self.n_user.save()
        profile, c = UserProfile.objects.get_or_create(user=self.n_user)
        self.r_user = User.objects.get(username='readonlyuser')
        self.r_user.set_password('pass')
        self.r_user.save()
        profile, c = UserProfile.objects.get_or_create(user=self.r_user)

        if not DopTrigger.objects.exists():
            # Create some random lookup data
            mixer.cycle(2).blend(DopTrigger)
            mixer.cycle(2).blend(Region)
            #mixer.cycle(2).blend(Organisation, name='western australian planning commission')
            mixer.cycle(2).blend(OrganisationType)
            mixer.cycle(2).blend(ConditionCategory)
            mixer.cycle(2).blend(Organisation, type=mixer.SELECT)
            #mixer.cycle(2).blend(Organisation, name='Western Australian Planning Commission')
        if not TaskState.objects.exists():
            # Ensure that required TaskState objects exist.
            mixer.blend(TaskState, name='Stopped')
            mixer.blend(TaskState, name='In progress')
            mixer.blend(TaskState, name='Completed')
        if not TaskType.objects.exists():
            mixer.cycle(2).blend(TaskType, initial_state=mixer.SELECT)
            mixer.cycle(2).blend(ReferralType, initial_task=mixer.SELECT)
            mixer.cycle(2).blend(NoteType)
            mixer.cycle(2).blend(Agency)
            mixer.cycle(2).blend(Tag)

        if not Referral.objects.exists():
            # Create some referral data
            mixer.cycle(2).blend(
                Referral, type=mixer.SELECT, agency=mixer.SELECT,
                referring_org=mixer.SELECT, referral_date=date.today())
            mixer.cycle(2).blend(
                Task, type=mixer.SELECT, referral=mixer.SELECT, state=mixer.SELECT)
            mixer.cycle(2).blend(Note, referral=mixer.SELECT, type=mixer.SELECT)
            mixer.cycle(2).blend(Record, referral=mixer.SELECT)
            mixer.cycle(2).blend(ModelCondition, category=mixer.SELECT)
            mixer.cycle(2).blend(
                Condition, referral=mixer.SELECT, category=mixer.SELECT,
                model_condition=mixer.SELECT)
            mixer.cycle(2).blend(
                Clearance, condition=mixer.SELECT, task=mixer.SELECT)
            mixer.cycle(2).blend(Location, referral=mixer.SELECT)
            mixer.cycle(2).blend(Bookmark, referral=mixer.SELECT, user=mixer.SELECT)

        super(PrsSeleniumTests, self).setUp()

    def tearDown(self):
        super(PrsSeleniumTests, self).tearDown()
        self.selenium.quit()

    def login(self, username='normaluser', password='pass'):
        self.selenium.get('{}{}'.format(self.live_server_url, '/login/'))
        username_input = self.selenium.find_element_by_name('username')
        username_input.send_keys(username)
        password_input = self.selenium.find_element_by_name('password')
        password_input.send_keys(password)
        self.selenium.find_element_by_xpath('//button[@class="btn btn-default" and contains(text(), "Log in")]').click()

        return True if self.selenium.find_element_by_xpath(
            "//div/h1[1]").text == 'ONGOING TASKS' else False


class PrsSeleniumNormalUserTests(PrsSeleniumTests):
    """
    Test PRS user
    """
    def setUp(self):
        super(PrsSeleniumNormalUserTests, self).setUp()
        self.fullname = User.objects.get(username='normaluser').get_full_name()

    def referral_create(self):
        self.selenium.find_element_by_link_text('Create').click()
        self.selenium.find_element_by_id('id_reference').send_keys('My Referrers Reference')
        self.selenium.find_element_by_id('id_description').send_keys('My Description')
        self.selenium.find_element_by_id('id_referral_date').send_keys('30/11/2016')
        Select(self.selenium.find_element_by_id("id_type")).select_by_index(1)
        Select(self.selenium.find_element_by_id("id_task_type")).select_by_index(1)
        Select(self.selenium.find_element_by_id("id_assigned_user")).select_by_index(1)
        Select(self.selenium.find_element_by_id("id_agency")).select_by_index(1)
        Select(self.selenium.find_element_by_id("id_region")).select_by_index(1)

    def test_referral_create(self):
        """ Test the Creation of a New Referral (Save and Cancel buttons)
        """

        if not self.logged_in:
            self.login()
        # Save Button
        self.referral_create()
        self.selenium.find_element_by_id('submit-id-save').click()
        self.assertEqual(self.selenium.find_element_by_css_selector('div.alert-success').text,
                         'New referral created successfully.')

        # Cancel Button
        self.referral_create()
        self.selenium.find_element_by_id('submit-id-cancel').click()
        self.assertEqual(self.selenium.find_element_by_xpath("//div/h1[1]").text, 'ONGOING TASKS')

        # 'Save and Add a Location' Button
        # TODO the below code requires user input - GeoServer Realm username and password during the unittest
        # self.referral_create()
        # self.selenium.find_element_by_id('submit-id-saveaddlocation').click()
        # self.assertEqual(self.selenium.find_element_by_css_selector('div.alert-success').text,
        #                 'New referral created successfully.')
        #self.assertEqual(self.selenium.find_element_by_xpath("//div/h1[1]").text, 'CREATE LOCATION(s)')

    def referral_menus(self, dropdown, menu_item=None, tag_item=None):
        """ Test the dropdown items and sub-menu items

            dropdown  --> 'Search'
            menu-item --> 'Referrals'
        """
        if not self.logged_in:
            self.login()

        search = self.selenium.find_element_by_link_text(dropdown)
        search.click()
        if menu_item:
            referrals = search.find_element_by_xpath("//a[@title='{}']".format(menu_item))
            referrals.click()
            if menu_item == 'Log out':
                xpath = "//div/h4[1]"
            else:
                xpath = "//div/h1[1]"
            self.assertEqual(
                self.selenium.find_element_by_xpath(xpath).text,
                tag_item if tag_item else menu_item.upper())
        else:
            search = self.selenium.find_element_by_link_text(dropdown)

    def test_01_login(self):
        if not self.logged_in:
            self.login()

        fullname = self.selenium.find_element_by_link_text(self.fullname)
        fullname.click()
        self.assertEqual(fullname.find_element_by_xpath("//a[@title='Log out']").text, 'Log out')

    def test_02_referral_create(self):
        """ Test the Creation of a New Referral (Save and Cancel buttons)
        """

        if not self.logged_in:
            self.login()
        # Save Button
        self.referral_create()
        self.selenium.find_element_by_id('submit-id-save').click()
        self.assertEqual(self.selenium.find_element_by_css_selector('div.alert-success').text,
                         'New referral created successfully.')

        # Cancel Button
        self.referral_create()
        self.selenium.find_element_by_id('submit-id-cancel').click()
        self.assertEqual(self.selenium.find_element_by_xpath("//div/h1[1]").text, 'ONGOING TASKS')

    def test_03_referral_menu(self):
        self.referral_menus('Search', 'Referrals')

    def test_04_tasks_menu(self):
        self.referral_menus('Search', 'Tasks')

    def test_05_notes_menu(self):
        self.referral_menus('Search', 'Notes')

    def test_06_conditions_menu(self):
        self.referral_menus('Search', 'Conditions')

    def test_07_records_menu(self):
        self.referral_menus('Search', 'Records')

    def test_08_locations_menu(self):
        self.referral_menus('Search', 'Locations')

    def test_09_clearances_menu(self):
        self.referral_menus('Search', 'Clearances')

    def test_10_search_menu(self):
        self.referral_menus('Search', 'Search all', 'SEARCH EVERYTHING')

    def test_11_recent_menu(self):
        self.referral_menus(self.fullname, 'Recent referrals', 'RECENTLY OPENED REFERRALS')

    def test_12_bookmarks_menu(self):
        self.referral_menus(self.fullname, 'Bookmarks')

    def test_13_stopped_menu(self):
        self.referral_menus(self.fullname, 'Stopped tasks')

    def test_14_help_menu(self):
        self.referral_menus(self.fullname, 'Help')

    def test_15_logout_menu(self):
        self.referral_menus(self.fullname, 'Log out', 'You are now logged out.')

    def test_16_reports_menu(self):
        self.referral_menus('Reports')


class PrsSeleniumReadOnlyUserTests(PrsSeleniumTests):
    """
    Test Read-Only user
    """
    def setUp(self):
        super(PrsSeleniumReadOnlyUserTests, self).setUp()
        self.fullname = User.objects.get(username='readonlyuser').get_full_name()

    def referral_menus_readonly(self, dropdown, menu_item=None, tag_item=None):
        """ Test the dropdown items and sub-menu items

            dropdown  --> 'Search'
            menu-item --> 'Referrals'
        """
        if not self.logged_in:
            self.login('readonlyuser', 'pass')

        # navigate to a specific referrals url eg. ../referrals/3
        ref = Referral.objects.all()[0]
        url = '{}/referrals/{}'.format(self.live_server_url, ref.id)
        self.selenium.get('{}'.format(url))

        self.selenium.implicitly_wait(5)
        search = self.selenium.find_element_by_link_text(dropdown)
        search.click()

        try:
            item = WebDriverWait(self.selenium, 10).until(
                EC.element_to_be_clickable((By.LINK_TEXT, menu_item))
            )
            item.click()
            self.assertEqual(self.selenium.current_url, '{}/{}'.format(url, '#'))
        except TimeoutException:
            print('\nError: Element not found {}'.format(menu_item))
        finally:
            pass

    def referral_child_menus_readonly(self, tab_name, menu, menu_item):
        """ Test the dropdown items and sub-menu items

            dropdown  --> 'Search'
            menu-item --> 'Referrals'
        """
        if not self.logged_in:
            self.login('readonlyuser', 'pass')

        # navigate to a specific referrals url eg. ../referrals/3
        url = '{}/referrals/{}'.format(self.live_server_url, Referral.objects.all()[0].id)
        self.selenium.get('{}'.format(url))

        # select the tab
        tab = self.selenium.find_element_by_xpath("//a[@href='#{}']".format(tab_name)).click()

        # click the first row in the tab table
        try:
            self.selenium.find_element_by_xpath("//div[@id='{}']/table/tbody/tr[1]/td/a".format(tab_name)).click()
        except NoSuchElementException:
            # No objects of type tab_name exist eg. there are no 'Tasks' or 'Notes' etc
            #print('ERROR: Failed to create {}'.format(menu.split()[0].capitalize()))
            return

        # select menu
        id_menu = 'id-menu-{}'.format(menu.lower().split()[0])
        self.selenium.find_element_by_id(id_menu).click()
        orig_url = self.selenium.current_url
        self.selenium.find_element_by_link_text(menu_item).click()
        self.assertEqual(self.selenium.current_url, '{}{}'.format(orig_url, '#'))

    def test_01_login(self):
        if not self.logged_in:
            self.login('readonlyuser', 'pass')

        fullname = self.selenium.find_element_by_link_text(self.fullname)
        fullname.click()
        self.assertEqual(fullname.find_element_by_xpath("//a[@title='Log out']").text, 'Log out')

    def test__02_referral_create(self):
        """ Test the attempted Creation of a New Referral by a ReadOnly User"""
        if not self.logged_in:
            self.login('readonlyuser', 'pass')

        orig_url = self.selenium.current_url
        self.selenium.find_element_by_link_text('Create').click()
        self.assertEqual(self.selenium.current_url, '{}{}'.format(orig_url, '#'))

    def test_03_referral_menus(self):
        menu_items = [
             'Add a note',
             'Add a record',
             'Add a task',
             'Add a condition',
             'Create location(s)',
             'Add a related referral',
             'Edit this referral',
             'Export locations to QGIS',
             'Bookmark this referral',
        ]

        ref = Referral.objects.all()[0]
        for menu_item in menu_items:
            # the following menus will only exist if the ref.location contains polygon data
            if menu_item=='Export locations to QGIS':
                if not any([l.poly for l in ref.location_set.current()]):
                    continue

            if menu_item=='Bookmark this referral' and Bookmark.objects.filter(referral=ref, user=self.r_user).exists():
                menu_item = 'Remove bookmark'

            self.referral_menus_readonly('Referral', menu_item)

    def test_04_note(self):
        menu_items = [
             'Edit note',
             'Delete note',
             'Add a new record to this note',
             'Add existing record(s) to this note',
        ]
        for menu_item in menu_items:
            self.referral_child_menus_readonly('tab_note', 'Note', menu_item)

    def test_05_task(self):
        menu_items = [
             'Edit task',
             'Stop task',
             'Complete task',
             'Cancel task',
             'Reassign task',
             'Inherit task',
             'Add a new record to this task',
             'Add existing record(s) to this task',
             'Add a new note to this task',
             'Add existing note(s) to this task',
             'Delete task',
        ]
        for menu_item in menu_items:
            self.referral_child_menus_readonly('tab_task', 'Task Tools', menu_item)

    def test_06_record(self):
        menu_items = [
             'Edit record',
             'Delete record',
             'Add a new note to this record',
             'Add existing note(s) to this record',
        ]
        for menu_item in menu_items:
            self.referral_child_menus_readonly('tab_record', 'Record', menu_item)

    def test_07_condition(self):
        menu_items = [
             'Edit condition',
             'Delete condition',
             'Add a clearance request',
        ]
        for menu_item in menu_items:
            self.referral_child_menus_readonly('tab_condition', 'Condition', menu_item)

#    def test_08_location(self):
#        """
#         Commented out because the test prompts for a login to KMI
#        """
#        pass
#        menu_items = [
#             'Edit location',
#             'Delete location',
#        ]
#        for menu_item in menu_items:
#            self.referral_child_menus_readonly('tab_location', 'Location', menu_item)
