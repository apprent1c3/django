from django.contrib.auth.models import Group
from django.test import SimpleTestCase, override_settings

from ..utils import setup


@override_settings(DEBUG=True)
class DebugTests(SimpleTestCase):
    @override_settings(DEBUG=False)
    @setup({"non_debug": "{% debug %}"})
    def test_non_debug(self):
        output = self.engine.render_to_string("non_debug", {})
        self.assertEqual(output, "")

    @setup({"modules": "{% debug %}"})
    def test_modules(self):
        output = self.engine.render_to_string("modules", {})
        self.assertIn(
            "&#x27;django&#x27;: &lt;module &#x27;django&#x27; ",
            output,
        )

    @setup({"plain": "{% debug %}"})
    def test_plain(self):
        output = self.engine.render_to_string("plain", {"a": 1})
        self.assertTrue(
            output.startswith(
                "{&#x27;a&#x27;: 1}"
                "{&#x27;False&#x27;: False, &#x27;None&#x27;: None, "
                "&#x27;True&#x27;: True}\n\n{"
            )
        )

    @setup({"non_ascii": "{% debug %}"})
    def test_non_ascii(self):
        group = Group(name="清風")
        output = self.engine.render_to_string("non_ascii", {"group": group})
        self.assertTrue(output.startswith("{&#x27;group&#x27;: &lt;Group: 清風&gt;}"))

    @setup({"script": "{% debug %}"})
    def test_script(self):
        """
        檢查模板渲染的安全性和行為，透過測試對具有危險內容的輸入的轉義，確保輸出結果正確且安全。 

        本函数測試模板引擎是否正確地轉義特殊字符，預防潛在的XSS攻擊。返回的輸出被驗證是否以預期的字串開頭，這表明引擎成功地把輸入的内容轉換成安全的形式。
        """
        output = self.engine.render_to_string("script", {"frag": "<script>"})
        self.assertTrue(
            output.startswith("{&#x27;frag&#x27;: &#x27;&lt;script&gt;&#x27;}")
        )
