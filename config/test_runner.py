import shutil
import tempfile

from django.conf import settings
from django.test.runner import DiscoverRunner


class TempMediaRunner(DiscoverRunner):
    """Testlerde yüklenen CSV arşivini geçici klasöre yazar, sonra siler.

    HTTPS yönlendirmesi kapatılır: testler uygulama mantığını sınar, sonuç
    DJANGO_HTTPS ortam değişkenine bağlı olmamalı.
    """

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._media = tempfile.mkdtemp(prefix="israf-test-")
        self._original = (settings.MEDIA_ROOT, settings.SECURE_SSL_REDIRECT)
        settings.MEDIA_ROOT = self._media
        settings.SECURE_SSL_REDIRECT = False

    def teardown_test_environment(self, **kwargs):
        settings.MEDIA_ROOT, settings.SECURE_SSL_REDIRECT = self._original
        shutil.rmtree(self._media, ignore_errors=True)
        super().teardown_test_environment(**kwargs)
