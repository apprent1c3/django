from django.contrib.admin.tests import AdminSeleniumTestCase
from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse

from .models import CamelCaseModel


@override_settings(ROOT_URLCONF="admin_views.urls")
class SeleniumTests(AdminSeleniumTestCase):
    available_apps = ["admin_views"] + AdminSeleniumTestCase.available_apps

    def setUp(self):
        """
        Sets up the test environment by creating a superuser and logs them in to the admin interface.

        This method is used to prepare the test setup, creating a superuser with default credentials and then logging them in to the admin interface, allowing subsequent tests to be run with elevated privileges.

        The superuser is created with the username 'super', password 'secret', and email 'super@example.com'. The login URL used is the admin index page, obtained by reversing the 'admin:index' URL pattern.
        """
        self.superuser = User.objects.create_superuser(
            username="super", password="secret", email="super@example.com"
        )
        self.admin_login(
            username="super", password="secret", login_url=reverse("admin:index")
        )

    def test_related_object_link_images_attributes(self):
        """

        Tests the image attributes of related object links in the admin views album add page.

        Verifies that the image tags of related object links have the correct attributes,
        specifically:
            - alt text is empty
            - width is 20 pixels
            - height is 20 pixels

        The test covers links for adding, changing, deleting, and viewing album owners.

        """
        from selenium.webdriver.common.by import By

        album_add_url = reverse("admin:admin_views_album_add")
        self.selenium.get(self.live_server_url + album_add_url)

        tests = [
            "add_id_owner",
            "change_id_owner",
            "delete_id_owner",
            "view_id_owner",
        ]
        for link_id in tests:
            with self.subTest(link_id):
                link_image = self.selenium.find_element(
                    By.XPATH, f'//*[@id="{link_id}"]/img'
                )
                self.assertEqual(link_image.get_attribute("alt"), "")
                self.assertEqual(link_image.get_attribute("width"), "20")
                self.assertEqual(link_image.get_attribute("height"), "20")

    def test_related_object_lookup_link_initial_state(self):
        """
        Tests the initial state of related object lookup links on the album add page in the admin interface.

        Verifies that links for changing, deleting, and viewing an album's owner are disabled by default when the page is first loaded.

        Checks the 'aria-disabled' attribute of each link to confirm they are in the expected state, ensuring accessibility and usability standards are met for users with disabilities.
        """
        from selenium.webdriver.common.by import By

        album_add_url = reverse("admin:admin_views_album_add")
        self.selenium.get(self.live_server_url + album_add_url)

        tests = [
            "change_id_owner",
            "delete_id_owner",
            "view_id_owner",
        ]
        for link_id in tests:
            with self.subTest(link_id):
                link = self.selenium.find_element(By.XPATH, f'//*[@id="{link_id}"]')
                self.assertEqual(link.get_attribute("aria-disabled"), "true")

    def test_related_object_lookup_link_enabled(self):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.select import Select

        album_add_url = reverse("admin:admin_views_album_add")
        self.selenium.get(self.live_server_url + album_add_url)

        select_element = self.selenium.find_element(By.XPATH, '//*[@id="id_owner"]')
        option = Select(select_element).options[-1]
        self.assertEqual(option.text, "super")
        select_element.click()
        option.click()

        tests = [
            "add_id_owner",
            "change_id_owner",
            "delete_id_owner",
            "view_id_owner",
        ]
        for link_id in tests:
            with self.subTest(link_id):
                link = self.selenium.find_element(By.XPATH, f'//*[@id="{link_id}"]')
                self.assertIsNone(link.get_attribute("aria-disabled"))

    def test_related_object_update_with_camel_casing(self):
        from selenium.webdriver.common.by import By

        add_url = reverse("admin:admin_views_camelcaserelatedmodel_add")
        self.selenium.get(self.live_server_url + add_url)
        interesting_name = "A test name"

        # Add a new CamelCaseModel using the "+" icon next to the "fk" field.
        self.selenium.find_element(By.ID, "add_id_fk").click()

        # Switch to the add popup window.
        self.wait_for_and_switch_to_popup()

        # Find the "interesting_name" field and enter a value, then save it.
        self.selenium.find_element(By.ID, "id_interesting_name").send_keys(
            interesting_name
        )
        self.selenium.find_element(By.NAME, "_save").click()

        # Return to the main window.
        self.wait_until(lambda d: len(d.window_handles) == 1, 1)
        self.selenium.switch_to.window(self.selenium.window_handles[0])

        id_value = CamelCaseModel.objects.get(interesting_name=interesting_name).id

        # Check that both the "Available" m2m box and the "Fk" dropdown now
        # include the newly added CamelCaseModel instance.
        fk_dropdown = self.selenium.find_element(By.ID, "id_fk")
        self.assertHTMLEqual(
            fk_dropdown.get_attribute("innerHTML"),
            f"""
            <option value="" selected="">---------</option>
            <option value="{id_value}" selected>{interesting_name}</option>
            """,
        )
        # Check the newly added instance is not also added in the "to" box.
        m2m_to = self.selenium.find_element(By.ID, "id_m2m_to")
        self.assertHTMLEqual(m2m_to.get_attribute("innerHTML"), "")
        m2m_box = self.selenium.find_element(By.ID, "id_m2m_from")
        self.assertHTMLEqual(
            m2m_box.get_attribute("innerHTML"),
            f"""
            <option title="{interesting_name}" value="{id_value}">
            {interesting_name}</option>
            """,
        )

    def test_related_object_add_js_actions(self):
        """
        Tests the JavaScript actions for adding related objects in the admin interface.

        This test case covers the functionality of adding a related object to a many-to-many field and a foreign key field.
        It verifies that the added object appears in the correct dropdown and many-to-many field, and that the \"add\" and \"remove\" links work correctly.
        The test simulates user interactions in the admin interface, including clicking on links, filling out forms, and switching between windows.
        It checks the expected HTML output of the many-to-many and foreign key fields after each action, ensuring that the interface updates correctly.
        The test covers the entire lifecycle of adding a related object, from creating the object to adding and removing it from the many-to-many field.
        """
        from selenium.webdriver.common.by import By

        add_url = reverse("admin:admin_views_camelcaserelatedmodel_add")
        self.selenium.get(self.live_server_url + add_url)
        m2m_to = self.selenium.find_element(By.ID, "id_m2m_to")
        m2m_box = self.selenium.find_element(By.ID, "id_m2m_from")
        fk_dropdown = self.selenium.find_element(By.ID, "id_fk")

        # Add new related entry using +.
        name = "Bergeron"
        self.selenium.find_element(By.ID, "add_id_m2m").click()
        self.wait_for_and_switch_to_popup()
        self.selenium.find_element(By.ID, "id_interesting_name").send_keys(name)
        self.selenium.find_element(By.NAME, "_save").click()
        self.wait_until(lambda d: len(d.window_handles) == 1, 1)
        self.selenium.switch_to.window(self.selenium.window_handles[0])

        id_value = CamelCaseModel.objects.get(interesting_name=name).id

        # Check the new value correctly appears in the "to" box.
        self.assertHTMLEqual(
            m2m_to.get_attribute("innerHTML"),
            f"""<option title="{name}" value="{id_value}">{name}</option>""",
        )
        self.assertHTMLEqual(m2m_box.get_attribute("innerHTML"), "")
        self.assertHTMLEqual(
            fk_dropdown.get_attribute("innerHTML"),
            f"""
            <option value="" selected>---------</option>
            <option value="{id_value}">{name}</option>
            """,
        )

        # Move the new value to the from box.
        self.selenium.find_element(By.XPATH, "//*[@id='id_m2m_to']/option").click()
        self.selenium.find_element(By.XPATH, "//*[@id='id_m2m_remove_link']").click()

        self.assertHTMLEqual(
            m2m_box.get_attribute("innerHTML"),
            f"""<option title="{name}" value="{id_value}">{name}</option>""",
        )
        self.assertHTMLEqual(m2m_to.get_attribute("innerHTML"), "")

        # Move the new value to the to box.
        self.selenium.find_element(By.XPATH, "//*[@id='id_m2m_from']/option").click()
        self.selenium.find_element(By.XPATH, "//*[@id='id_m2m_add_link']").click()

        self.assertHTMLEqual(m2m_box.get_attribute("innerHTML"), "")
        self.assertHTMLEqual(
            m2m_to.get_attribute("innerHTML"),
            f"""<option title="{name}" value="{id_value}">{name}</option>""",
        )
