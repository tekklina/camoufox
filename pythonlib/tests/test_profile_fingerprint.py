import os

import pytest

from camoufox import utils
from camoufox.profile import (
    PROFILE_FINGERPRINT_FILE,
    load_profile_fingerprint,
    save_profile_fingerprint,
)


def valid_config(seed):
    return {
        'navigator.userAgent': 'Mozilla/5.0 Test',
        'navigator.hardwareConcurrency': 8,
        'canvas:seed': seed,
        'audio:seed': seed + 1,
        'fonts:spacing_seed': seed + 2,
    }


def test_profile_fingerprint_round_trip(tmp_path):
    profile = tmp_path / 'profile'
    config = valid_config(1234) | {'webGl:renderer': 'Test GPU'}

    saved_path = save_profile_fingerprint(profile, config)

    assert saved_path == profile / PROFILE_FINGERPRINT_FILE
    assert load_profile_fingerprint(profile) == config
    if os.name != 'nt':
        assert saved_path.stat().st_mode & 0o777 == 0o600


def test_missing_profile_fingerprint_returns_none(tmp_path):
    assert load_profile_fingerprint(tmp_path / 'missing') is None


def test_profiles_have_independent_fingerprints(tmp_path):
    first = tmp_path / 'first'
    second = tmp_path / 'second'
    first_config = valid_config(111)
    second_config = valid_config(222)
    save_profile_fingerprint(first, first_config)
    save_profile_fingerprint(second, second_config)

    assert load_profile_fingerprint(first) == first_config
    assert load_profile_fingerprint(second) == second_config


def test_launch_options_reuses_generated_profile_identity(tmp_path, monkeypatch):
    profile = tmp_path / 'profile'
    generation = {'count': 0}

    def fake_generate_fingerprint(**_kwargs):
        generation['count'] += 1
        return object()

    def fake_from_browserforge(_fingerprint, _ff_version):
        count = generation['count']
        return {
            'navigator.userAgent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'Gecko/20100101 Firefox/152.0',
            'navigator.platform': 'Win32',
            'navigator.hardwareConcurrency': count * 4,
            'screen.width': 1920,
            'screen.height': 1080,
        }

    monkeypatch.setattr(utils, 'add_default_addons', lambda *_args: None)
    monkeypatch.setattr(utils, 'generate_fingerprint', fake_generate_fingerprint)
    monkeypatch.setattr(utils, 'from_browserforge', fake_from_browserforge)
    monkeypatch.setattr(utils, 'installed_verstr', lambda: '152.0.4')
    monkeypatch.setattr(utils, 'launch_path', lambda: '/fake/camoufox')
    monkeypatch.setattr(utils, 'validate_config', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(utils, 'get_env_vars', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(utils, '_generate_random_font_subset', lambda _os: ['Test Font'])
    monkeypatch.setattr(utils, '_generate_random_voice_subset', lambda _os: ['Test Voice'])
    monkeypatch.setattr(
        utils,
        'sample_webgl',
        lambda *_args: {
            'webGl:vendor': 'Test Vendor',
            'webGl:renderer': 'Test Renderer',
            'webGl2Enabled': True,
        },
    )

    utils.launch_options(
        _persistent_profile_dir=profile,
        executable_path='/fake/camoufox',
        env={},
    )
    first = load_profile_fingerprint(profile)

    utils.launch_options(
        _persistent_profile_dir=profile,
        executable_path='/fake/camoufox',
        env={},
    )
    second = load_profile_fingerprint(profile)

    assert generation['count'] == 1
    assert first == second
    assert second['navigator.hardwareConcurrency'] == 4
    assert second['canvas:seed'] == first['canvas:seed']
    assert second['audio:seed'] == first['audio:seed']
    assert second['fonts:spacing_seed'] == first['fonts:spacing_seed']

    utils.launch_options(
        config={'navigator.hardwareConcurrency': 12},
        _persistent_profile_dir=profile,
        executable_path='/fake/camoufox',
        env={},
        i_know_what_im_doing=True,
    )
    overridden = load_profile_fingerprint(profile)

    assert generation['count'] == 1
    assert overridden['navigator.hardwareConcurrency'] == 12
    assert overridden['canvas:seed'] == first['canvas:seed']


@pytest.mark.parametrize(
    'contents',
    [
        b'not json',
        b'{}',
        b'{"schema_version": 1, "config": []}',
        b'{"schema_version": 1, "config": {}}',
        b'{"schema_version": 999, "config": {}}',
    ],
)
def test_invalid_profile_fingerprint_fails_closed(tmp_path, contents):
    profile = tmp_path / 'profile'
    profile.mkdir()
    (profile / PROFILE_FINGERPRINT_FILE).write_bytes(contents)

    with pytest.raises(ValueError, match='fingerprint state'):
        load_profile_fingerprint(profile)
