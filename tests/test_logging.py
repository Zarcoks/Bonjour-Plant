"""The logger of the Logging package, and its access path through the application object."""
from core.app import app
from Logging import Logger
from plant_management.models import AppLog


def test_the_application_exposes_a_logger():
    assert isinstance(app.logger, Logger)


def test_logger_info_writes_a_row(db):
    app.logger.info("ma log")
    written = AppLog.objects.get()
    assert written.message == "ma log"
    assert written.type == "INFO"
    assert written.time is not None


def test_every_level_is_stored(db):
    app.logger.debug("une trace")
    app.logger.info("une information")
    app.logger.warning("un avertissement")
    app.logger.error("une erreur")
    assert list(AppLog.objects.order_by('id').values_list('type', flat=True)) == \
        ["DEBUG", "INFO", "WARNING", "ERROR"]


def test_extra_fields_are_appended_to_the_message(db):
    app.logger.info("type de plante créé", plant="Menthe")
    assert AppLog.objects.get().message == "type de plante créé plant=Menthe"


def test_module_logger_keeps_writing_to_the_same_table(db):
    page_logger = app.module_logger("plant_types")
    assert page_logger.module_name == "bonjour_plant.plant_types"
    page_logger.info("depuis la page")
    assert AppLog.objects.get().message == "depuis la page"


def test_a_log_is_truncated_to_what_the_table_accepts(db):
    app.logger.info("a" * 800)
    assert len(AppLog.objects.get().message) == 500


def test_every_record_goes_to_the_database(db):
    # There is no console-only logger: a record always lands in the table.
    assert app.logger.info("dans la base").pk is not None
    assert app.module_logger("mqtt").warning("dans la base aussi").pk is not None

