# from django.test import TestCase

# from django.contrib.staticfiles.testing import StaticLiveServerTestCase
# from selenium.webdriver.common.by import By
# from selenium import webdriver
# from selenium.webdriver.firefox.service import Service as FirefoxService
# from webdriver_manager.firefox import GeckoDriverManager


# class MySeleniumTests(StaticLiveServerTestCase):
#     @classmethod
#     def setUpClass(cls):
#         super().setUpClass()
#         cls.selenium = webdriver.Firefox(
#             service=FirefoxService(GeckoDriverManager().install())
#         )
#         cls.selenium.implicitly_wait(10)

#     @classmethod
#     def tearDownClass(cls):
#         cls.selenium.quit()
#         super().tearDownClass()

#     def test_login(self):
#         self.selenium.get("%s%s" % (self.live_server_url, "/404/"))
#         username_input = self.selenium.find_element(By.NAME, "username")
#         username_input.send_keys("myuser")
#         password_input = self.selenium.find_element(By.NAME, "password")
#         password_input.send_keys("secret")
#         self.selenium.find_element(By.XPATH, '//input[@value="Log in"]').click()
