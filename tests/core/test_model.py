import os
import tempfile
import time

import pytest

import rasa
import rasa.data as data
import rasa.core
import rasa_nlu
from rasa.constants import (
    DEFAULT_CONFIG_PATH, DEFAULT_DATA_PATH, DEFAULT_DOMAIN_PATH)
from rasa.model import (
    FINGERPRINT_CONFIG_KEY, FINGERPRINT_CORE_VERSION_KEY,
    FINGERPRINT_DOMAIN_KEY, FINGERPRINT_FILE_PATH, FINGERPRINT_NLU_DATA_KEY,
    FINGERPRINT_NLU_VERSION_KEY, FINGERPRINT_RASA_VERSION_KEY,
    FINGERPRINT_STORIES_KEY, FINGERPRINT_TRAINED_AT_KEY,
    core_fingerprint_changed, create_package_rasa, get_latest_model, get_model,
    get_model_subdirectories, model_fingerprint, nlu_fingerprint_changed)


def test_get_latest_model(trained_model):
    import shutil
    path_of_latest = os.path.join(os.path.dirname(trained_model),
                                  "latest.tar.gz")
    shutil.copy(trained_model, path_of_latest)

    model_directory = os.path.dirname(path_of_latest)

    assert get_latest_model(model_directory) == path_of_latest


def test_get_model_from_directory(trained_model):
    unpacked = get_model(trained_model)

    assert os.path.exists(os.path.join(unpacked, "core"))
    assert os.path.exists(os.path.join(unpacked, "nlu"))


def test_get_model_from_directory_with_subdirectories(trained_model):
    unpacked = get_model(trained_model)
    unpacked_core, unpacked_nlu = get_model_subdirectories(unpacked)

    assert os.path.exists(unpacked_core)
    assert os.path.exists(unpacked_nlu)


def _fingerprint(config=["test"], domain=["test"],
                 rasa_version="1.0", core_version="1.0",
                 nlu_version="1.0", stories=["test"], nlu=["test"]):
    return {
        FINGERPRINT_CONFIG_KEY: config,
        FINGERPRINT_DOMAIN_KEY: domain,
        FINGERPRINT_NLU_VERSION_KEY: nlu_version,
        FINGERPRINT_CORE_VERSION_KEY: core_version,
        FINGERPRINT_TRAINED_AT_KEY: time.time(),
        FINGERPRINT_RASA_VERSION_KEY: rasa_version,
        FINGERPRINT_STORIES_KEY: stories,
        FINGERPRINT_NLU_DATA_KEY: nlu
    }


def test_persist_and_load_fingerprint():
    from rasa.model import persist_fingerprint, fingerprint_from_path

    fingerprint = _fingerprint()
    output_directory = tempfile.mkdtemp()

    persist_fingerprint(output_directory, fingerprint)
    actual = fingerprint_from_path(output_directory)

    assert actual == fingerprint


def test_core_fingerprint_unchanged():
    fingerprint1 = _fingerprint()
    fingerprint2 = _fingerprint(nlu_version="other", nlu=[])

    assert core_fingerprint_changed(fingerprint1, fingerprint2) is False


def test_nlu_fingerprint_unchanged():
    fingerprint1 = _fingerprint()
    fingerprint2 = _fingerprint(core_version="other", stories=[])

    assert nlu_fingerprint_changed(fingerprint1, fingerprint2) is False


@pytest.mark.parametrize("fingerprint2", [
    _fingerprint(config=["other"]),
    _fingerprint(domain=["other"]),
    _fingerprint(stories=["test", "other"]),
    _fingerprint(rasa_version="100"),
    _fingerprint(config=["other"], domain=["other"])])
def test_core_fingerprint_changed(fingerprint2):
    fingerprint1 = _fingerprint()
    assert core_fingerprint_changed(fingerprint1, fingerprint2)


@pytest.mark.parametrize("fingerprint2", [
    _fingerprint(config=["other"]),
    _fingerprint(nlu=["test", "other"]),
    _fingerprint(nlu_version="100"),
    _fingerprint(nlu_version="100", config=["other"])])
def test_nlu_fingerprint_changed(fingerprint2):
    fingerprint1 = _fingerprint()
    assert nlu_fingerprint_changed(fingerprint1, fingerprint2)


def _project_files(project, config_file=DEFAULT_CONFIG_PATH,
                   domain=DEFAULT_DOMAIN_PATH,
                   training_files=DEFAULT_DATA_PATH):

    if training_files is None:
        core_directory = None
        nlu_directory = None
    else:
        core_directory, nlu_directory = data.get_core_nlu_directories(
            training_files)
    paths = {"config_file": config_file,
             "domain_file": domain,
             "nlu_data": core_directory,
             "stories": nlu_directory}

    return {k: v if v is None else os.path.join(project, v)
            for k, v in paths.items()}


def test_create_fingerprint_from_paths(project):
    project_files = _project_files(project)

    assert model_fingerprint(**project_files)


@pytest.mark.parametrize("project_files", [
    ["invalid", "invalid", "invalid"],
    [None, None, None]])
def test_create_fingerprint_from_invalid_paths(project, project_files):
    project_files = _project_files(project, *project_files)

    expected = _fingerprint([], [], rasa_version=rasa.__version__,
                            core_version=rasa.__version__,
                            nlu_version=rasa_nlu.__version__, stories=[],
                            nlu=[])

    actual = model_fingerprint(**project_files)
    assert actual[FINGERPRINT_TRAINED_AT_KEY] is not None

    del actual[FINGERPRINT_TRAINED_AT_KEY]
    del expected[FINGERPRINT_TRAINED_AT_KEY]

    assert actual == expected


@pytest.mark.parametrize("use_fingerprint", [True, False])
def test_rasa_packaging(trained_model, project, use_fingerprint):
    unpacked_model_path = get_model(trained_model)

    os.remove(os.path.join(unpacked_model_path, FINGERPRINT_FILE_PATH))
    if use_fingerprint:
        fingerprint = model_fingerprint(**_project_files(project))
    else:
        fingerprint = None

    tempdir = tempfile.mkdtemp()
    output_path = os.path.join(tempdir, "test.tar.gz")

    create_package_rasa(unpacked_model_path, output_path, fingerprint)

    unpacked = get_model(output_path)

    assert os.path.exists(
        os.path.join(unpacked, FINGERPRINT_FILE_PATH)) == use_fingerprint
    assert os.path.exists(os.path.join(unpacked, "core"))
    assert os.path.exists(os.path.join(unpacked, "nlu"))

    assert not os.path.exists(unpacked_model_path)
