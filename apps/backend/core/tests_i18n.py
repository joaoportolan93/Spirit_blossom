from pathlib import Path

import polib
from django.conf import settings
from django.test import TestCase
from django.utils import translation


class TestI18nBackend(TestCase):
    def test_po_and_mo_files_integrity(self):
        """Verifica se os arquivos .po e .mo existem e são válidos."""
        locale_dir = Path(settings.BASE_DIR) / "locale"
        for lang in ["pt_BR", "en"]:
            po_path = locale_dir / lang / "LC_MESSAGES" / "django.po"
            mo_path = locale_dir / lang / "LC_MESSAGES" / "django.mo"

            self.assertTrue(po_path.exists(), f"Arquivo {po_path} deve existir")
            self.assertTrue(mo_path.exists(), f"Arquivo {mo_path} deve existir")

            po = polib.pofile(str(po_path))
            self.assertGreater(len(po), 0, f"O arquivo {po_path} não deve estar vazio")

    def test_translation_override_context_manager(self):
        """Valida que translation.override altera o idioma adequadamente."""
        with translation.override("pt-br"):
            msg_pt = translation.gettext("Invalid credentials.")
            self.assertEqual(msg_pt, "Credenciais inválidas.")

        with translation.override("en"):
            msg_en = translation.gettext("Invalid credentials.")
            self.assertEqual(msg_en, "Invalid credentials.")
